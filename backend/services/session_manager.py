"""
会话管理器 - 替代 Streamlit session_state
使用 UUID 作为 session_id，DataFrame 存储在内存中
"""

import os
import uuid
import time
import tempfile
import dataclasses
import pandas as pd
from typing import Dict, Optional, List, Any
from threading import RLock, Thread
from config import QUOTA_BYTES


@dataclasses.dataclass
class Dataset:
    """单个数据集（每张上传的报表对应一个）"""
    dataset_id: str
    file_name: str
    file_size_bytes: int
    df: Optional[pd.DataFrame] = None          # 非 active 数据集可为 None（pickle 保留，按需 reload）
    df_original: Optional[pd.DataFrame] = None  # 仅落盘失败时的兜底内存副本；正常为 None
    original_path: Optional[str] = None        # 原始数据落盘路径(pickle)，释放内存时保留
    rows: int = 0
    columns: List[str] = dataclasses.field(default_factory=list)
    column_info: List[dict] = dataclasses.field(default_factory=list)
    preview: List[dict] = dataclasses.field(default_factory=list)
    uploaded_at: float = 0.0
    # 多表合并标记（合并宽表专用）
    is_merged: bool = False                    # 是否为合并生成的宽表
    sources: List[str] = dataclasses.field(default_factory=list)   # 来源 dataset_id 列表
    merge_keys: List[str] = dataclasses.field(default_factory=list) # 实际使用的关联键列名


def _parse_missing_rate(row) -> float:
    """从 column_info 行解析缺失率（兼容百分比字符串 '12.3%' 与纯数字）。"""
    try:
        v = row.get("缺失率")
        if v is None:
            return 0.0
        if isinstance(v, str):
            return float(v.replace("%", "").strip()) / 100.0
        return float(v)
    except Exception:
        return 0.0


class SessionData:
    """单个会话的数据（支持多数据集）"""
    def __init__(self):
        # ===== 多数据集存储 =====
        self.datasets: Dict[str, Dataset] = {}        # key=dataset_id
        self.active_dataset_id: Optional[str] = None  # 当前分析对象
        self.uploaded_bytes: int = 0                  # 累计已上传字节（=Σ file_size_bytes）
        self.dataset_packages: Dict[str, Dict[str, Any]] = {}  # dataset_id→{pkg_id:pkg}
        # 向后兼容：df / df_original / original_path 改为委托到 active 数据集的属性（见下方 property）
        self.df_undo_stack: List[pd.DataFrame] = []  # 撤销栈（最多保存 20 步）
        self.cleaning_history: List[Dict] = []
        self.analysis_history: List[Dict] = []
        self.saved_charts: List[Dict[str, Any]] = []  # 用户从分析页保存的图表 [{"title":..., "option":..., "saved_at":...}, ...]
        self.analysis_packages: Dict[str, Any] = {}     # 临时分析结果（key=pkg_id, value=AnalysisPackage）
        self.saved_packages: List[Dict[str, Any]] = []   # 用户保存的分析包
        self.api_key: str = ""
        self.custom_title: str = ""          # 用户手动编辑的仪表盘标题
        self.holds_slot: bool = False        # 是否已占用"数据插槽"（限流=持有数据的会话，上限 max_sessions）
        self.reserved_at: float = 0.0         # 占用插槽的时间戳（用于预约超时释放）
        self.created_at: float = time.time()
        self.last_access: float = time.time()

    # ===== df / df_original / original_path 委托到 active 数据集（向后兼容下游 ~30 处 get_data 调用）=====
    def _active_dataset(self) -> Optional["Dataset"]:
        if self.active_dataset_id is not None:
            return self.datasets.get(self.active_dataset_id)
        return None

    @property
    def df(self) -> Optional[pd.DataFrame]:
        ds = self._active_dataset()
        return ds.df if ds else None

    @df.setter
    def df(self, value: Optional[pd.DataFrame]):
        ds = self._active_dataset()
        if ds is not None:
            ds.df = value

    @property
    def df_original(self) -> Optional[pd.DataFrame]:
        ds = self._active_dataset()
        return ds.df_original if ds else None

    @df_original.setter
    def df_original(self, value: Optional[pd.DataFrame]):
        ds = self._active_dataset()
        if ds is not None:
            ds.df_original = value

    @property
    def original_path(self) -> Optional[str]:
        ds = self._active_dataset()
        return ds.original_path if ds else None

    @original_path.setter
    def original_path(self, value: Optional[str]):
        ds = self._active_dataset()
        if ds is not None:
            ds.original_path = value


class SessionManager:
    """会话管理器，线程安全的内存存储"""
    
    def __init__(self, max_sessions: int = 5, session_timeout: int = 3600):
        self._sessions: Dict[str, SessionData] = {}
        self._lock = RLock()
        self._max_sessions = max_sessions
        self._session_timeout = session_timeout
        # 原始数据落盘目录（临时盘，重启即丢 —— 属预期的优雅降级）
        self._original_dir = os.path.join(tempfile.gettempdir(), "datamind_original")
        os.makedirs(self._original_dir, exist_ok=True)
        # P2（内存画像结论五）：后台定时清理线程，主动回收过期会话（弥补惰性清理短板）。
        # 间隔跟随 timeout：max(60, timeout//12) → 默认 3600//12 = 300s。
        # 最坏滞后 = 间隔，过期会话最多比 timeout 多赖 300s，内存卫生足够及时且不浪费 0.1 CPU。
        self._cleanup_interval = max(60, session_timeout // 12)
        # 排队队列与已晋升映射（限流相关，均在锁内访问）
        self._queue: List[Dict[str, Any]] = []          # FIFO: {ticket_id, session_id, created_at}
        self._promoted: Dict[str, str] = {}             # ticket_id -> session_id（已晋升等待上传）
        self._QUEUE_TTL = 300                           # 排队票据最长等待（秒），超时丢弃
        self._RESERVE_TTL = 120                         # 预约插槽但未上传的最长保留（秒），超时释放
        self._slot_idle_timeout = 600                   # 已加载数据的插槽空闲超时（秒）：释放 df + 内存，腾位给排队者
        self._start_background_cleanup()
    
    # ===== 限流：数据插槽预约 / 排队 / 晋升 =====
    def _slot_count(self) -> int:
        """当前已占用数据插槽的会话数（锁内调用）"""
        return sum(1 for s in self._sessions.values() if s.holds_slot)

    def acquire_for_upload(self, session_id: str) -> Dict[str, Any]:
        """预约数据插槽；满员则把该会话入队。

        返回 {'granted': bool, 'session_id'?, 'ticket_id'?, 'position'?}
        - granted=True：已预约（或已有数据），可立即上传，附 session_id
        - granted=False：已满员，附 ticket_id 与当前排队位次 position（1 起）
        """
        with self._lock:
            self._cleanup_sync()
            session = self._sessions.get(session_id)
            if session is None:
                session = SessionData()
                self._sessions[session_id] = session
            # 已占插槽或已有数据 → 直接放行（幂等，避免重复预约）
            if session.holds_slot or session.active_dataset_id is not None:
                return {"granted": True, "session_id": session_id,
                        "used_bytes": session.uploaded_bytes, "quota_bytes": QUOTA_BYTES}
            # 有空位 → 预约该会话
            if self._slot_count() < self._max_sessions:
                session.holds_slot = True
                session.reserved_at = time.time()
                session.last_access = time.time()
                return {"granted": True, "session_id": session_id,
                        "used_bytes": session.uploaded_bytes, "quota_bytes": QUOTA_BYTES}
            # 满员 → 入队，返回位次
            ticket_id = str(uuid.uuid4())
            self._queue.append({
                "ticket_id": ticket_id,
                "session_id": session_id,
                "created_at": time.time(),
            })
            return {"granted": False, "ticket_id": ticket_id, "position": len(self._queue)}

    def queue_status(self, ticket_id: str) -> Dict[str, Any]:
        """查询排队状态。

        返回 {'status': 'ready'|'queued'|'expired', 'session_id'?, 'position'?}
        - ready：已晋升，附可上传的 session_id
        - queued：仍在等待，附当前位次 position（1 起）
        - expired：票据不存在或已失效（会话丢失）
        """
        with self._lock:
            for i, item in enumerate(self._queue):
                if item["ticket_id"] == ticket_id:
                    return {"status": "queued", "position": i + 1}
            if ticket_id in self._promoted:
                sid = self._promoted[ticket_id]
                sess = self._sessions.get(sid)
                if sess is not None and sess.holds_slot:
                    return {"status": "ready", "session_id": sid, "position": 0}
                # 晋升后会话丢失 → 视为过期
                self._promoted.pop(ticket_id, None)
            return {"status": "expired"}

    def cancel_queue(self, ticket_id: str) -> None:
        """从等待队列移除票据（尽力而为；已晋升项无法撤回上传，仅移除映射）。"""
        with self._lock:
            self._queue = [it for it in self._queue if it["ticket_id"] != ticket_id]
            self._promoted.pop(ticket_id, None)

    def _promote_head(self) -> None:
        """晋升队首到就绪（锁内调用）。循环 drained 直至无队首或无空位。"""
        while self._queue and self._slot_count() < self._max_sessions:
            item = self._queue.pop(0)
            sid = item["session_id"]
            session = self._sessions.get(sid)
            if session is None:
                # 队首会话已不存在 → 新建会话承接票据，避免丢票
                sid = str(uuid.uuid4())
                session = SessionData()
                self._sessions[sid] = session
            session.holds_slot = True
            session.reserved_at = time.time()
            session.last_access = time.time()
            self._promoted[item["ticket_id"]] = sid

    def reserve_session(self, session_id: str) -> None:
        """为已有会话占用一个数据插槽（上传兜底路径用，正常前端已预占必有空位）。"""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                session = SessionData()
                self._sessions[session_id] = session
            if not session.holds_slot and session.df is None:
                session.holds_slot = True
                session.reserved_at = time.time()
                session.last_access = time.time()

    def _release_slot_inner(self, session_id: str) -> bool:
        """锁内复用：释放某会话的数据插槽（丢弃 df 与落盘原文件，但保留会话对象）。

        不含晋升，由调用方在持锁状态下统一调 _promote_head，避免重复加锁。
        返回是否真的释放了一个插槽。
        """
        session = self._sessions.get(session_id)
        if session is None or not session.holds_slot:
            return False
        self._remove_original_file(session_id)
        session.df = None
        session.holds_slot = False
        return True

    def release_slot(self, session_id: str) -> bool:
        """释放某会话的数据插槽（保留会话对象以便重新上传，但丢弃 DataFrame 与原文件以释放内存）。

        释放后自动晋升队首。返回是否真的释放了一个插槽。
        这是「自动入队」的现实触发点之一：手动释放（API/按钮）与服务端
        空闲超时（_slot_idle_timeout）都会经此路径腾出插槽。
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None or not session.holds_slot:
                return False
            self._release_slot_inner(session_id)
            session.last_access = time.time()
            self._promote_head()
            return True

    def create_session(self) -> str:
        """创建新会话，返回 session_id（不再淘汰最老会话，限流改为按数据插槽）。"""
        session_id = str(uuid.uuid4())
        with self._lock:
            # 清理过期会话
            self._cleanup_sync()
            self._sessions[session_id] = SessionData()
        return session_id
    
    def get_session(self, session_id: str) -> Optional[SessionData]:
        """获取会话数据"""
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.last_access = time.time()
            return session
    
    def add_dataset(self, session_id: str, df: pd.DataFrame, *, file_name: str,
                    file_size_bytes: int, rows: int, columns: List[str],
                    column_info: List[dict], preview: List[dict],
                    dataset_id: Optional[str] = None, set_active: bool = True,
                    account_quota: bool = True) -> str:
        """新增一个数据集（不覆盖旧表）。返回 dataset_id。

        原始数据落盘(pickle)以释放内存；非 active 数据集仅保留 pickle、释放内存 df（防 OOM）。
        落盘失败(磁盘满/权限)时兜底保留内存副本，保证功能不丢。
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                session = SessionData()
                self._sessions[session_id] = session
            # 去除重复列名，避免后续 df[col] 返回 DataFrame 而非 Series
            if df.columns.duplicated().any():
                dup_cols = df.columns[df.columns.duplicated()].unique().tolist()
                import logging as _logging; _logging.getLogger("session").warning(f"removing duplicate columns: {dup_cols}")
                df = df.loc[:, ~df.columns.duplicated()]
            did = dataset_id or str(uuid.uuid4())
            if did in session.datasets:
                did = str(uuid.uuid4())  # 重名则重新生成，避免覆盖
            path = os.path.join(self._original_dir, f"{session_id}_{did}.pkl")
            try:
                df.to_pickle(path)
                original_path = path
                df_original = None  # 正常路径不保留内存副本
            except Exception as e:  # 兜底：落盘失败则保留内存副本
                import logging as _logging
                _logging.getLogger("session").warning(f"原始数据落盘失败，回退内存保留: {e}")
                original_path = None
                df_original = df.copy()
            ds = Dataset(
                dataset_id=did, file_name=file_name, file_size_bytes=file_size_bytes,
                df=df.copy(), df_original=df_original, original_path=original_path,
                rows=rows, columns=list(columns), column_info=list(column_info),
                preview=list(preview), uploaded_at=time.time(),
            )
            session.datasets[did] = ds
            # account_quota=False 时只落库不累计额度（多 sheet 文件在首个 sheet 已计一次）
            session.uploaded_bytes += file_size_bytes if account_quota else 0
            if set_active:
                session.active_dataset_id = did
                # 修复一：驱逐其余非 active 数据集的内存 df（pickle 保留）
                for other in session.datasets.values():
                    if other.dataset_id != did and other.df is not None:
                        other.df = None
                # 闭环：新数据集成为 active，同步其（可能为空）产物
                session.analysis_packages = dict(session.dataset_packages.get(did, {}))
            session.last_access = time.time()
            return did

    def add_merged_dataset(self, session_id: str, df: pd.DataFrame,
                            sources: List[str], keys: List[str],
                            file_name: str = "合并宽表") -> str:
        """合并宽表入库：构造与上传一致的元信息，在锁内注册新数据集
        （set_active=False，不抢占当前视图），并补写 is_merged/sources/merge_keys，
        返回新 dataset_id。

        合并阶段在 process-datasets 流水线中调用，宽表一旦注册即可被下游
        列名映射与规则分析流水线正常识别。
        """
        import logging as _logging
        import numpy as np
        from src.data_loader import get_column_info, get_data_info

        # 先去除重复列名（合并可能引入同名非键列），再构造元信息
        if df.columns.duplicated().any():
            df = df.loc[:, ~df.columns.duplicated()]
        preview = df.head(100).replace({np.nan: None}).to_dict(orient="records")
        column_info_df = get_column_info(df)
        columns_list = []
        for _, row in column_info_df.iterrows():
            columns_list.append({
                "name": str(row.get("列名", row.get("column", ""))),
                "dtype": str(row.get("数据类型", row.get("dtype", ""))),
                "missing": int(row.get("缺失值", row.get("missing", 0)) or 0),
                "missing_rate": _parse_missing_rate(row),
                "unique": int(row.get("唯一值数", row.get("unique", 0)) or 0),
                "sample": str(row.get("示例值", row.get("sample", ""))),
            })
        data_info = get_data_info(df)
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                session = SessionData()
                self._sessions[session_id] = session
            did = str(uuid.uuid4())
            while did in session.datasets:
                did = str(uuid.uuid4())
            path = os.path.join(self._original_dir, f"{session_id}_{did}.pkl")
            try:
                df.to_pickle(path)
                original_path = path
                df_original = None
            except Exception as e:
                _logging.getLogger("session").warning(f"合并宽表落盘失败，回退内存保留: {e}")
                original_path = None
                df_original = df.copy()
            ds = Dataset(
                dataset_id=did, file_name=file_name,
                file_size_bytes=int(df.memory_usage(deep=True).sum()),
                df=df.copy(), df_original=df_original, original_path=original_path,
                rows=int(data_info.get("行数", len(df))),
                columns=list(df.columns), column_info=list(columns_list),
                preview=list(preview), uploaded_at=time.time(),
                is_merged=True, sources=list(sources), merge_keys=list(keys),
            )
            session.datasets[did] = ds
            # 不抢占当前 active 视图、不驱逐、不计额度
            session.last_access = time.time()
            return did

    def set_data(self, session_id: str, df: pd.DataFrame):
        """向后兼容：等价于新增一个默认 dataset（老调用方用）"""
        self.add_dataset(
            session_id, df,
            file_name="data",
            file_size_bytes=int(df.memory_usage(deep=True).sum()),
            rows=int(df.shape[0]), columns=list(df.columns),
            column_info=[], preview=[],
        )
    
    def get_data(self, session_id: str) -> Optional[pd.DataFrame]:
        """获取当前 DataFrame"""
        session = self.get_session(session_id)
        return session.df if session else None
    
    def get_original_data(self, session_id: str) -> Optional[pd.DataFrame]:
        """获取原始 DataFrame（从磁盘读取；不存在/损坏返回 None）。

        会话存在但文件已被重启清除 -> 返回 None，由调用方提示"原始数据已释放"。
        """
        session = self.get_session(session_id)
        if session is None:
            return None
        ds = session._active_dataset()
        if ds is None:
            return None
        # 兜底：落盘失败时的内存副本
        if ds.df_original is not None:
            return ds.df_original
        if ds.original_path and os.path.exists(ds.original_path):
            try:
                return pd.read_pickle(ds.original_path)
            except Exception:
                return None
        return None

    def _remove_original_file(self, session_id: str):
        """删除会话对应所有数据集的原始数据落盘文件（须在锁内调用；忽略异常）"""
        session = self._sessions.get(session_id)
        if session:
            self._clear_session_datasets(session)

    def _clear_session_datasets(self, session: SessionData):
        """清空会话全部数据集（删除落盘 + 释放内存 + 归零额度）；须在锁内"""
        for ds in list(session.datasets.values()):
            if ds.original_path and os.path.exists(ds.original_path):
                try:
                    os.remove(ds.original_path)
                except OSError:
                    pass
        session.datasets.clear()
        session.active_dataset_id = None
        session.uploaded_bytes = 0
        session.df = None
        session.df_original = None
        session.original_path = None

    # ===== 多数据集新方法 =====
    def get_dataset_df(self, session_id: str, dataset_id: str) -> Optional[pd.DataFrame]:
        """获取指定数据集的 df（缺失则从 pickle reload 回内存）"""
        session = self.get_session(session_id)
        if session is None:
            return None
        ds = session.datasets.get(dataset_id)
        if ds is None:
            return None
        if ds.df is not None:
            return ds.df
        if ds.original_path and os.path.exists(ds.original_path):
            try:
                ds.df = pd.read_pickle(ds.original_path)
                return ds.df
            except Exception:
                if ds.df_original is not None:
                    ds.df = ds.df_original
                    return ds.df
                return None
        if ds.df_original is not None:
            ds.df = ds.df_original
            return ds.df
        return None

    def select_dataset(self, session_id: str, dataset_id: str) -> bool:
        """切换当前分析对象（active）；按需 reload + 驱逐其余非 active 内存 df（修复一）"""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None or dataset_id not in session.datasets:
                return False
            session.active_dataset_id = dataset_id
            # 闭环：切换后把当前数据集的分析产物同步进 analysis_packages（看板/报告统一读取入口）
            session.analysis_packages = dict(session.dataset_packages.get(dataset_id, {}))
            ds = session.datasets[dataset_id]
            # 按需 reload 内存 df
            if ds.df is None:
                if ds.original_path and os.path.exists(ds.original_path):
                    try:
                        ds.df = pd.read_pickle(ds.original_path)
                    except Exception:
                        if ds.df_original is not None:
                            ds.df = ds.df_original
                elif ds.df_original is not None:
                    ds.df = ds.df_original
            # 驱逐其余非 active 数据集的内存 df（pickle 保留）
            for other in session.datasets.values():
                if other.dataset_id != dataset_id and other.df is not None:
                    other.df = None
            session.last_access = time.time()
            return True

    def get_datasets(self, session_id: str) -> List[Dict[str, Any]]:
        """返回全部数据集的元信息列表（供前端"已上传报表"列表 / 刷新拉回）"""
        session = self.get_session(session_id)
        if session is None:
            return []
        result = []
        for ds in session.datasets.values():
            result.append({
                "dataset_id": ds.dataset_id,
                "file_name": ds.file_name,
                "file_size_bytes": ds.file_size_bytes,
                "rows": ds.rows,
                "columns": ds.columns,
                "column_info": ds.column_info,
                "preview": ds.preview,
                "uploaded_at": ds.uploaded_at,
                "is_active": ds.dataset_id == session.active_dataset_id,
                "is_merged": ds.is_merged,
                "sources": ds.sources,
                "merge_keys": ds.merge_keys,
            })
        # 按上传时间倒序（最新在前）
        result.sort(key=lambda x: x.get("uploaded_at", 0), reverse=True)
        return result

    def remove_dataset(self, session_id: str, dataset_id: str) -> bool:
        """删除指定数据集（删落盘 + 减额度 + 回退 active）"""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None or dataset_id not in session.datasets:
                return False
            ds = session.datasets.pop(dataset_id)
            # 删落盘
            if ds.original_path and os.path.exists(ds.original_path):
                try:
                    os.remove(ds.original_path)
                except OSError:
                    pass
            # 减额度
            session.uploaded_bytes = max(0, session.uploaded_bytes - ds.file_size_bytes)
            # 若该表原是 active，回退到最近剩余表的 active 并 reload
            if session.active_dataset_id == dataset_id:
                if session.datasets:
                    # 选 uploaded_at 最大的剩余表
                    next_id = max(session.datasets.values(),
                                  key=lambda d: d.uploaded_at).dataset_id
                    session.active_dataset_id = next_id
                    session.analysis_packages = dict(session.dataset_packages.get(next_id, {}))
                    nd = session.datasets[next_id]
                    if nd.df is None:
                        if nd.original_path and os.path.exists(nd.original_path):
                            try:
                                nd.df = pd.read_pickle(nd.original_path)
                            except Exception:
                                if nd.df_original is not None:
                                    nd.df = nd.df_original
                        elif nd.df_original is not None:
                            nd.df = nd.df_original
                else:
                    session.active_dataset_id = None
                    session.analysis_packages = {}
            session.last_access = time.time()
            return True

    def set_dataset_packages(self, session_id: str, dataset_id: str, package_map: Dict[str, Any]):
        """按 dataset_id 分桶保存分析产物（修复三）"""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                session = SessionData()
                self._sessions[session_id] = session
            session.dataset_packages[dataset_id] = package_map
            # 修复三闭环：若正好是 active 数据集，同步进 session.analysis_packages 供看板/报告直接读取
            if session.active_dataset_id == dataset_id:
                session.analysis_packages = dict(package_map)
            session.last_access = time.time()

    def get_dataset_packages(self, session_id: str, dataset_id: str) -> Dict[str, Any]:
        """获取指定数据集的分析产物（分桶）"""
        session = self.get_session(session_id)
        if session is None:
            return {}
        return dict(session.dataset_packages.get(dataset_id, {}))

    def update_data(self, session_id: str, df: pd.DataFrame):
        """更新当前 DataFrame（清洗后），如果 session 不存在则自动创建"""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                session = SessionData()
                self._sessions[session_id] = session
            session.df = df.copy()
            session.last_access = time.time()
    
    def add_cleaning_step(self, session_id: str, step: Dict):
        """添加清洗记录"""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                session = SessionData()
                self._sessions[session_id] = session
            session.cleaning_history.append(step)
            session.last_access = time.time()
    
    def get_cleaning_history(self, session_id: str) -> List[Dict]:
        """获取清洗历史"""
        session = self.get_session(session_id)
        return session.cleaning_history if session else []
    
    def set_api_key(self, session_id: str, api_key: str):
        """设置 API Key"""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                session = SessionData()
                self._sessions[session_id] = session
            session.api_key = api_key
            session.last_access = time.time()
    
    def get_api_key(self, session_id: str) -> str:
        """获取 API Key"""
        session = self.get_session(session_id)
        return session.api_key if session else ""

    def set_custom_title(self, session_id: str, title: str):
        """设置用户手动编辑的仪表盘标题"""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                session = SessionData()
                self._sessions[session_id] = session
            session.custom_title = title
            session.last_access = time.time()

    def get_custom_title(self, session_id: str) -> str:
        """获取用户手动编辑的仪表盘标题"""
        session = self.get_session(session_id)
        return session.custom_title if session else ""

    def set_analysis_packages(self, session_id: str, packages: dict):
        """暂存分析结果（/analysis/run 后调用）"""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                session = SessionData()
                self._sessions[session_id] = session
            session.analysis_packages = packages
            # 闭环：把结果同时写进当前 active 数据集的桶，避免切换回来后丢失
            if session.active_dataset_id:
                session.dataset_packages[session.active_dataset_id] = packages
            session.last_access = time.time()
    
    def push_undo_state(self, session_id: str):
        """保存当前状态到撤销栈（最多 20 步）"""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None or session.df is None:
                return
            session.df_undo_stack.append(session.df.copy())
            # 限制栈大小
            if len(session.df_undo_stack) > 20:
                session.df_undo_stack.pop(0)
            session.last_access = time.time()

    def undo_last_action(self, session_id: str) -> Optional[pd.DataFrame]:
        """撤销上一步操作，返回恢复后的 DataFrame"""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None or len(session.df_undo_stack) == 0:
                return None
            prev_df = session.df_undo_stack.pop()
            session.df = prev_df.copy()
            session.last_access = time.time()
            return session.df

    def get_undo_count(self, session_id: str) -> int:
        """获取可撤销步数"""
        session = self.get_session(session_id)
        return len(session.df_undo_stack) if session else 0

    def save_chart(self, session_id: str, chart: Dict[str, Any]):
        """保存图表到仪表盘收藏"""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                session = SessionData()
                self._sessions[session_id] = session
            chart["saved_at"] = time.time()
            session.saved_charts.append(chart)
            session.last_access = time.time()

    def get_saved_charts(self, session_id: str) -> List[Dict[str, Any]]:
        """获取所有已保存的图表"""
        session = self.get_session(session_id)
        return session.saved_charts if session else []

    def delete_saved_chart(self, session_id: str, index: int) -> bool:
        """删除指定索引的已保存图表"""
        with self._lock:
            session = self._sessions.get(session_id)
            if session and 0 <= index < len(session.saved_charts):
                session.saved_charts.pop(index)
                session.last_access = time.time()
                return True
            return False

    def clear_saved_charts(self, session_id: str):
        """清空所有已保存图表"""
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.saved_charts.clear()
                session.last_access = time.time()

    # ===== V2 分析包操作 =====
    def save_packages(self, session_id: str, package_ids: List[str]):
        """从 analysis_packages 复制到 saved_packages"""
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return
            for pkg_id in package_ids:
                if pkg_id in session.analysis_packages:
                    pkg = dataclasses.asdict(session.analysis_packages[pkg_id])
                    pkg["saved_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                    # 去重：同一 ID 不重复保存
                    if not any(p.get("id") == pkg_id for p in session.saved_packages):
                        session.saved_packages.append(pkg)
            session.last_access = time.time()

    def get_saved_packages(self, session_id: str) -> List[Dict[str, Any]]:
        """获取所有已保存的分析包"""
        session = self.get_session(session_id)
        return session.saved_packages if session else []

    def get_saved_packages_full(self, session_id: str) -> List[Dict[str, Any]]:
        """获取已保存的分析包（含渲染后的 KPI/Table/Chart/Insight/Conclusion）

        使用 Renderer 层将 AnalysisPackage 的原始数据渲染为前端可消费格式。
        """
        from src.kpi_renderer import KPIRenderer
        from src.table_renderer import TableRenderer
        from src.insight_renderer import InsightRenderer
        from src.conclusion_renderer import ConclusionRenderer
        import dataclasses

        session = self.get_session(session_id)
        if not session:
            return []

        kpi_renderer = KPIRenderer()
        table_renderer = TableRenderer()
        insight_renderer = InsightRenderer()
        conclusion_renderer = ConclusionRenderer()

        full_packages = []
        for pkg in session.saved_packages:
            # 渲染各部分
            kpis_raw = pkg.get("kpis", [])
            tables_raw = pkg.get("tables", [])
            charts_raw = pkg.get("charts", [])
            insights_raw = pkg.get("insights", [])
            conclusions_raw = pkg.get("conclusions", [])
            chart_data_raw = pkg.get("chart_data", [])

            # KPI 渲染
            rendered_kpis = []
            for k in kpis_raw:
                if isinstance(k, dict):
                    from src.analysis_templates.base import KPIItem
                    item = KPIItem(**k) if "label" in k else None
                    if item:
                        rendered_kpis.append(dataclasses.asdict(kpi_renderer.render(item)))

            # Table 渲染
            rendered_tables = []
            for t in tables_raw:
                if isinstance(t, dict) and "title" in t:
                    from src.analysis_templates.base import TableData
                    table_data = TableData(**{k: t[k] for k in ("title","table_type","columns","rows") if k in t})
                    rendered_tables.append(dataclasses.asdict(table_renderer.render(table_data)))

            # Insight 渲染
            rendered_insights = []
            if isinstance(insights_raw, list):
                rendered_insights = [
                    dataclasses.asdict(r) for r in insight_renderer.render_all(insights_raw)
                ]

            # Conclusion 渲染
            rendered_conclusion = dataclasses.asdict(
                conclusion_renderer.render(conclusions_raw if isinstance(conclusions_raw, list) else [])
            )

            full_pkg = dict(pkg)
            full_pkg["rendered_kpis"] = rendered_kpis
            full_pkg["rendered_tables"] = rendered_tables
            full_pkg["rendered_charts"] = charts_raw
            full_pkg["rendered_insights"] = rendered_insights
            full_pkg["rendered_conclusion"] = rendered_conclusion
            full_packages.append(full_pkg)

        return full_packages

    def clear_data(self, session_id: str):
        """清除会话数据（同步删除落盘的原始文件）；释放插槽后晋升队首"""
        with self._lock:
            self._remove_original_file(session_id)
            self._sessions.pop(session_id, None)
            self._promote_head()
    
    def _cleanup_sync(self):
        """清理过期会话（非线程安全，需在锁中调用）。

        同时处理限流相关释放：预约超时未上传的占槽空会话、
        排队票据超时，并在腾出插槽后晋升队首。
        """
        now = time.time()
        # 1) 过期会话（含已占插槽但整体超时的数据会话）
        expired = [
            sid for sid, sdata in self._sessions.items()
            if now - sdata.last_access > self._session_timeout
        ]
        for sid in expired:
            self._remove_original_file(sid)
            del self._sessions[sid]
        # 2) 预约超时未上传（占槽空会话）：释放插槽，避免长期占槽
        for sid, sdata in list(self._sessions.items()):
            if sdata.holds_slot and sdata.df is None and (now - sdata.reserved_at) > self._RESERVE_TTL:
                self._remove_original_file(sid)
                del self._sessions[sid]
        # 2.5) 已加载数据但空闲超时（_slot_idle_timeout）的插槽：释放 df + 内存，腾出插槽给排队者
        # 仅释放插槽、保留会话对象，待整体超时 _session_timeout 才删除，避免丢失用户配置。
        for sid, sdata in list(self._sessions.items()):
            if sdata.holds_slot and sdata.df is not None and (now - sdata.last_access) > self._slot_idle_timeout:
                self._release_slot_inner(sid)
        # 3) 排队票据超时丢弃
        self._queue = [it for it in self._queue if now - it["created_at"] <= self._QUEUE_TTL]
        # 4) 腾出插槽后晋升队首
        self._promote_head()
    
    def cleanup(self):
        """清理过期会话（线程安全）"""
        with self._lock:
            self._cleanup_sync()

    def _start_background_cleanup(self):
        """启动后台守护线程，定时主动回收过期会话。

        弥补 request 触发的惰性清理（结论五）：无此后台线程时，过期会话要等到
        「下次请求触发 _cleanup_sync」或「超 max_sessions」才删，可能远超时 timeout。
        线程仅在持锁调用 cleanup()，而 _cleanup_sync 内不二次加锁、_remove_original_file
        亦设计为锁内调用，故无死锁风险。Python 引用语义保证清理瞬间正在使用的会话对象不被释放。
        """
        def _loop():
            while True:
                time.sleep(self._cleanup_interval)
                try:
                    self.cleanup()
                except Exception:
                    # 单轮清理异常不影响后续周期
                    pass
        t = Thread(target=_loop, name="session-cleanup", daemon=True)
        t.start()


# 全局单例
manager = SessionManager()
