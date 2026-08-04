"""
分析执行与保存 API 路由

V2：模板通过 AnalysisLibrary + 动态导入管理。
分析执行逻辑抽到 backend.routers._analysis_pipeline（供 /analysis/run 与 /analysis/process-datasets 共用）。
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Set
import uuid
import asyncio
import threading
import time as _time
from concurrent.futures import ThreadPoolExecutor, as_completed

from backend.services.session_manager import manager
from src.utils.json_serializer import sanitize_json
from backend.routers._analysis_pipeline import run_df_to_packages
from src.mapping.column_mapper import map_dataset_columns
from src.merge.dataset_merger import build_analysis_units, AnalysisUnit
from src.analysis_engine.registry import get_models
from src.analysis_engine.llm_decision import llm_decision_path

import logging
logger = logging.getLogger("analysis")

router = APIRouter()

# ===== 请求模型 =====

class IntentItem(BaseModel):
    business_question: str
    analysis_goal: str
    priority: str
    reason: str


class AnalysisRunRequest(BaseModel):
    session_id: str
    intents: List[IntentItem]
    # 选填：LLM 兜底映射所需配置（缺省则降级为已有映射，不阻断分析）
    api_key: Optional[str] = ""
    base_url: Optional[str] = None
    model: Optional[str] = None


class AnalysisSaveRequest(BaseModel):
    session_id: str
    package_ids: List[str]


# ===== 分析执行（委托共享流水线，行为不变）=====

@router.post("/analysis/run")
async def api_analysis_run(req: AnalysisRunRequest):
    df = manager.get_data(req.session_id)
    if df is None:
        raise HTTPException(status_code=404, detail="会话数据不存在")

    # 列名映射（次路径无 dataset_id，传 None；指纹仅基于 columns 计算）
    llm_cfg = {
        "api_key": req.api_key,
        "base_url": req.base_url,
        "model": req.model,
    }
    df = map_dataset_columns(req.session_id, None, df, llm_cfg)

    # 新引擎（列名匹配）自动运行全部命中模型，忽略旧 intents 选择
    packages, package_map = run_df_to_packages(df)
    manager.set_analysis_packages(req.session_id, package_map)
    return {"packages": sanitize_json(packages)}


# ===== 分析保存 =====

@router.post("/analysis/save")
async def api_analysis_save(req: AnalysisSaveRequest):
    """从 session.analysis_packages 复制到 saved_packages"""
    try:
        manager.save_packages(req.session_id, req.package_ids)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")
    packages = manager.get_saved_packages(req.session_id)
    saved_ids = [p.get("id") for p in packages if p.get("id") in req.package_ids]
    return sanitize_json({"saved_count": len(saved_ids), "package_ids": saved_ids})


# ===== 后台多数据集并行处理（照搬 report.py 骨架，修复二/三/七）=====

_PROCESS_TASKS: Dict[str, dict] = {}
_PROCESS_TASKS_LOCK = threading.Lock()
_PROCESS_TTL = 900  # 任务内存表 TTL（秒），防泄漏
# 修复七：只留线程池控"同时 2 个"，不再另设信号量 / LLM 信号量
class ProcessDatasetsRequest(BaseModel):
    session_id: Optional[str] = None  # session_id 走路径，body 内不再必需
    dataset_ids: Optional[List[str]] = None  # 省略=处理全部
    # v1 不要求 api_key（规则意图）；保留字段供后续 LLM 增强
    api_key: Optional[str] = ""
    base_url: Optional[str] = None
    model: Optional[str] = None


def _cleanup_process_tasks():
    """清理过期任务内存表项（须在锁内调用）"""
    now = _time.time()
    expired = [tid for tid, t in _PROCESS_TASKS.items()
               if now - t.get("ts", 0) > _PROCESS_TTL]
    for tid in expired:
        _PROCESS_TASKS.pop(tid, None)


def _process_one(session_id: str, dataset_id: str, llm_cfg: dict = None) -> tuple:
    """处理单个数据集（双路）：
    规则引擎路径（确定性全跑命中模型）+ LLM 决策路径（一期预留，返回空包）。
    返回 (生成的包数量, 已渲染的包 dict 列表)。
    """
    df = manager.get_dataset_df(session_id, dataset_id)
    if df is None:
        raise RuntimeError("数据集为空或读取失败")
    # 短路优化：若「AI 智能清洗」流水线已对该单元做过「合表+映射+LLM 清洗」
    # （cleaned_mapped 标记为真），则跳过重复映射，省一次 LLM 调用。
    # 仅跳过映射；合表仍由 _resolve_process_items 幂等处理。未走清洗路径时缺省 False 照常映射。
    _sess = manager.get_session(session_id)
    _ds = _sess.datasets.get(dataset_id) if _sess else None
    _skip_map = bool(_ds and getattr(_ds, "cleaned_mapped", False))
    # 列名映射：统一为规范标准名，供下游图表生成使用一致语义列名
    if not _skip_map:
        _file_name = _ds.file_name if _ds else None
        df = map_dataset_columns(session_id, dataset_id, df, llm_cfg,
                                file_name=_file_name)
    # 规则引擎路径：新引擎（列名匹配）自动运行全部命中模型
    packages, package_map = run_df_to_packages(df)
    manager.set_dataset_packages(session_id, dataset_id, package_map)
    # LLM 决策路径（一期预留）：async stub，返回空包，仅记录决策日志
    try:
        registered = [m.name for m in get_models()]
        llm_pkgs = asyncio.run(llm_decision_path(df, registered, llm_cfg or {}))
    except Exception as e:
        logger.warning("LLM 决策路径异常(已忽略): %s", e)
        llm_pkgs = []
    # 合并两路（llm 本期恒为空）
    merged = list(packages) + list(llm_pkgs)
    return len(package_map), merged


def _resolve_process_items(session_id: str, dataset_ids: List[str],
                          llm_cfg: Optional[dict] = None) -> List[dict]:
    """载入各表 df → 研判合并 → 注册宽表 → 产出处理项列表。

    返回 [{"kind":"single"/"merged","dataset_id":str,
            "sources":[...],"merge_keys":[...]}, ...]。
    合并失败/异常一律降级为原多表单表项，保证端到端不阻断。

    合并阶段位于「数据清洗之后、列名映射之前」：进入本函数时数据集已是
    清洗后状态（清洗由用户在按开始分析前用 /clean/* 交互完成），不再触发清洗。
    """
    session = manager.get_session(session_id)
    file_names: Dict[str, str] = {}
    loaded = []
    merged_existing: List[str] = []   # 已是宽表的数据集，直接单表处理，不参与二次合并
    for did in dataset_ids:
        df = manager.get_dataset_df(session_id, did)
        if df is None:
            continue
        dsobj = session.datasets.get(did) if session else None
        file_names[did] = dsobj.file_name if dsobj else did
        if dsobj is not None and getattr(dsobj, "is_merged", False):
            merged_existing.append(did)
            continue
        loaded.append((did, df))
    if not loaded and not merged_existing:
        return []
    # 若本次选中的目标已含「合并宽表」：
    # - 旧宽表本身与它的「来源原表」直接单表重分析，不再二次合并
    #   （否则反复运行会把宽表与原始表再次连通，不断注册重复宽表）；
    # - 真正「新增且不属于任何旧宽表来源」的表，彼此间仍可正常合并成新宽表。
    if merged_existing:
        merged_sources: Set[str] = set()
        for mdid in merged_existing:
            mobj = session.datasets.get(mdid) if session else None
            if mobj is not None:
                merged_sources.update(getattr(mobj, "sources", []) or [])
        items = [{"kind": "single", "dataset_id": d} for d in merged_existing]
        for d, _ in loaded:
            if d in merged_sources:
                items.append({"kind": "single", "dataset_id": d})
        fresh = [(d, df) for d, df in loaded if d not in merged_sources]
        if fresh:
            try:
                fresh_units = build_analysis_units(fresh, file_names, llm_cfg)
            except Exception:
                fresh_units = [AnalysisUnit(kind="single", dataset_id=d,
                                            file_name=file_names.get(d, d)) for d, _ in fresh]
            for unit in fresh_units:
                if unit.kind == "single":
                    items.append({"kind": "single", "dataset_id": unit.dataset_id})
                else:
                    try:
                        new_did = manager.add_merged_dataset(
                            session_id, unit.df, unit.sources, unit.keys,
                            file_name=unit.file_name or "合并宽表")
                        items.append({
                            "kind": "merged", "dataset_id": new_did,
                            "sources": unit.sources, "merge_keys": unit.keys,
                        })
                    except Exception:
                        for sd in unit.sources:
                            items.append({"kind": "single", "dataset_id": sd})
        return items
    try:
        units = build_analysis_units(loaded, file_names, llm_cfg)
    except Exception:
        # 合并研判异常 → 降级为原多表单表
        units = [AnalysisUnit(kind="single", dataset_id=d,
                              file_name=file_names.get(d, d)) for d, _ in loaded]
    items: List[dict] = []
    for unit in units:
        if unit.kind == "single":
            items.append({"kind": "single", "dataset_id": unit.dataset_id})
        else:
            # 注册宽表入库（set_active=False，不抢占当前视图）
            try:
                new_did = manager.add_merged_dataset(
                    session_id, unit.df, unit.sources, unit.keys,
                    file_name=unit.file_name or "合并宽表")
                items.append({
                    "kind": "merged", "dataset_id": new_did,
                    "sources": unit.sources, "merge_keys": unit.keys,
                })
            except Exception:
                # 注册失败 → 来源表各自单表
                for sd in unit.sources:
                    items.append({"kind": "single", "dataset_id": sd})
    return items


def _run_process_task(task_id: str, session_id: str,
                      process_items: List[dict], llm_cfg: dict = None):
    # process_items: [{"kind":"single"/"merged","dataset_id":str,
    #                   "sources":[...],"merge_keys":[...]}, ...]
    total = len(process_items)
    datasets_status: Dict[str, dict] = {}
    for it in process_items:
        did = it["dataset_id"]
        extra = {}
        if it["kind"] == "merged":
            extra = {"kind": "merged",
                     "sources": it.get("sources", []),
                     "merge_keys": it.get("merge_keys", [])}
        datasets_status[did] = {"status": "pending", **extra}
    status = "running"
    try:
        futures = {}
        # 修复七：线程池 max_workers=2 限制同时并行数（防 512MB OOM）
        with ThreadPoolExecutor(max_workers=2) as ex:
            for it in process_items:
                did = it["dataset_id"]
                datasets_status[did] = {**datasets_status[did], "status": "running"}
                futures[ex.submit(_process_one, session_id, did, llm_cfg)] = did
            for fut in as_completed(futures):
                did = futures[fut]
                try:
                    pkg_count, merged = fut.result()
                    datasets_status[did] = {**datasets_status[did],
                                             "status": "done", "pkg_count": pkg_count,
                                             "packages": merged}
                except Exception as e:
                    datasets_status[did] = {**datasets_status[did],
                                             "status": "error", "error": str(e)}
        status = "done"
    except Exception as e:  # 顶层异常（如 executor 创建失败）
        status = "error"
        for did in list(datasets_status.keys()):
            if datasets_status[did].get("status") in ("pending", "running"):
                datasets_status[did] = {**datasets_status[did],
                                         "status": "error", "error": str(e)}
    finally:
        with _PROCESS_TASKS_LOCK:
            _PROCESS_TASKS[task_id].update({
                "status": status,
                "total": total,
                "completed": sum(1 for v in datasets_status.values()
                                  if v.get("status") == "done"),
                "datasets": datasets_status,
                "ts": _time.time(),
            })


@router.post("/analysis/process-datasets/{session_id}")
async def api_process_datasets(session_id: str, req: Optional[ProcessDatasetsRequest] = None):
    """提交后台并行处理任务，立即返回 task_id；前端轮询 status 获取进度。

    session_id 走路径（与前端轮询链路一致）；dataset_ids / LLM 映射配置走可选 body。
    """
    session = manager.get_session(session_id)
    if session is None or not session.datasets:
        raise HTTPException(status_code=404, detail="会话无数据集，请先上传")
    target = (req.dataset_ids if req and req.dataset_ids else list(session.datasets.keys()))
    target = [d for d in target if d in session.datasets]
    if not target:
        raise HTTPException(status_code=400, detail="指定的数据集不存在")

    # 组装 LLM 兜底映射所需配置（前端未传则留空，降级为已有映射）
    llm_cfg = {
        "api_key": req.api_key if req else "",
        "base_url": req.base_url if req else None,
        "model": req.model if req else None,
    }

    # 合并研判：数据清洗之后、列名映射之前。生成宽表并注册，产出处理项。
    # 无关联键 / 合并失败 → 自动降级为原多表分别处理（端到端不阻断）。
    process_items = _resolve_process_items(session_id, target, llm_cfg)
    if not process_items:
        raise HTTPException(status_code=400, detail="指定的数据集读取失败")

    task_id = str(uuid.uuid4())
    initial = {}
    for it in process_items:
        extra = {"kind": it["kind"]}
        if it["kind"] == "merged":
            extra["sources"] = it["sources"]
            extra["merge_keys"] = it["merge_keys"]
        initial[it["dataset_id"]] = {"status": "pending", **extra}
    with _PROCESS_TASKS_LOCK:
        _PROCESS_TASKS[task_id] = {
            "status": "running",
            "total": len(process_items),
            "completed": 0,
            "datasets": initial,
            "ts": _time.time(),
        }
    threading.Thread(
        target=_run_process_task, args=(task_id, session_id, process_items, llm_cfg),
        daemon=True,
    ).start()
    return {"task_id": task_id, "total": len(process_items)}


@router.get("/analysis/dataset-packages")
async def api_dataset_packages(session_id: str, dataset_id: str):
    """读取已落库的数据洞察分析包（process-datasets 生成的结果）。

    用于前端切换模块回来后，把当前数据集的数据洞察结果重新拉回渲染，
    无需用户重新生成、也无需点「保存到看板」。
    """
    pkgs = manager.get_dataset_packages(session_id, dataset_id)
    # 转为可序列化结构：{pkg_id: payload}
    result = {}
    for pid, pkg in (pkgs or {}).items():
        result[pid] = pkg.payload if hasattr(pkg, "payload") else pkg
    return {"packages": sanitize_json(result)}


@router.get("/analysis/process-datasets/status/{task_id}")
async def api_process_status(task_id: str):
    """轮询处理进度：running / done / error / 404(过期)"""
    with _PROCESS_TASKS_LOCK:
        _cleanup_process_tasks()
        task = _PROCESS_TASKS.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="任务不存在或已过期")
        return sanitize_json(dict(task))
