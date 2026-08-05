"""
CRUD 封装：所有对 SQLite 的读写集中于此，业务代码（SessionManager）不直接写 SQL。

约定：
- sessions.state_json：会话可序列化的全部轻量状态（JSON 字符串）。
- datasets：记录 DataFrame 落盘 pickle 的持久化路径 + 元信息。
- analysis_packages：AnalysisPackage 完整 JSON。

线程安全：调用方（SessionManager）已用 RLock 串行化；本层每次操作取连接执行，
连接本身为线程局部，避免 sqlite 跨线程错误。
"""
import json
import logging
import sqlite3
from typing import Optional, Dict, Any, List

from .connection import get_connection

logger = logging.getLogger(__name__)


def _to_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def _from_json(text: str) -> Any:
    return json.loads(text)


# ===================== sessions =====================

def save_session_state(session_id: str, state: Dict[str, Any], created_at: float,
                       last_access: float) -> None:
    """写入/更新会话状态（UPSERT）。"""
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO sessions (session_id, state_json, created_at, last_access)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(session_id) DO UPDATE SET
            state_json = excluded.state_json,
            last_access = excluded.last_access
        """,
        (session_id, _to_json(state), created_at, last_access),
    )
    conn.commit()


def load_session_state(session_id: str) -> Optional[Dict[str, Any]]:
    """读取会话状态；不存在返回 None。"""
    conn = get_connection()
    row = conn.execute(
        "SELECT state_json, created_at, last_access FROM sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    if row is None:
        return None
    state = _from_json(row["state_json"])
    state["_created_at"] = row["created_at"]
    state["_last_access"] = row["last_access"]
    return state


def touch_session(session_id: str, last_access: float) -> None:
    """仅更新会话最后访问时间。"""
    conn = get_connection()
    conn.execute(
        "UPDATE sessions SET last_access = ? WHERE session_id = ?",
        (last_access, session_id),
    )
    conn.commit()


def delete_session(session_id: str) -> None:
    """删除会话及其全部数据集、分析包（级联清理）。"""
    conn = get_connection()
    conn.execute("DELETE FROM analysis_packages WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM datasets WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
    conn.commit()


def clear_all_data() -> None:
    """清空全部上传数据（sessions / datasets / analysis_packages 三表全清）。

    用途：后端冷启动时释放所有历史数据，恢复到空白状态。幂等、不依赖内存状态。
    """
    conn = get_connection()
    conn.execute("DELETE FROM analysis_packages")
    conn.execute("DELETE FROM datasets")
    conn.execute("DELETE FROM sessions")
    conn.commit()


def list_expired_sessions(timeout: float, now: float) -> List[str]:
    """返回最后访问距 now 超过 timeout 秒的会话 ID 列表。"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT session_id FROM sessions WHERE ? - last_access > ?",
        (now, timeout),
    ).fetchall()
    return [r["session_id"] for r in rows]


# ===================== datasets =====================

def save_dataset(session_id: str, dataset_id: str, meta: Dict[str, Any],
                 original_path: str, is_active: bool, created_at: float) -> None:
    """写入/更新数据集记录。"""
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO datasets (dataset_id, session_id, meta_json, original_path, is_active, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(dataset_id) DO UPDATE SET
            meta_json = excluded.meta_json,
            original_path = excluded.original_path,
            is_active = excluded.is_active
        """,
        (dataset_id, session_id, _to_json(meta), original_path,
         1 if is_active else 0, created_at),
    )
    conn.commit()


def _all_dataset_metas(session_id: str) -> List[Dict[str, Any]]:
    """读取某会话全部数据集的元信息（含 dataset_id / 落盘路径）。仅供 SessionManager 内部 hydrate 使用。"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT dataset_id, meta_json, original_path, is_active FROM datasets WHERE session_id = ?",
        (session_id,),
    ).fetchall()
    result = []
    for r in rows:
        meta = _from_json(r["meta_json"])
        meta["dataset_id"] = r["dataset_id"]
        meta["original_path"] = r["original_path"]
        meta["is_active"] = bool(r["is_active"])
        result.append(meta)
    return result


def load_dataset_meta(dataset_id: str) -> Optional[Dict[str, Any]]:
    """读取数据集元信息 + 落盘路径。"""
    conn = get_connection()
    row = conn.execute(
        "SELECT meta_json, original_path, is_active FROM datasets WHERE dataset_id = ?",
        (dataset_id,),
    ).fetchone()
    if row is None:
        return None
    meta = _from_json(row["meta_json"])
    meta["original_path"] = row["original_path"]
    meta["is_active"] = bool(row["is_active"])
    return meta


def set_dataset_active(session_id: str, dataset_id: str) -> None:
    """将某数据集设为该会话 active，其余置为非 active。"""
    conn = get_connection()
    conn.execute("UPDATE datasets SET is_active = 0 WHERE session_id = ?", (session_id,))
    conn.execute(
        "UPDATE datasets SET is_active = 1 WHERE dataset_id = ? AND session_id = ?",
        (dataset_id, session_id),
    )
    conn.commit()


def delete_dataset(session_id: str, dataset_id: str) -> None:
    conn = get_connection()
    conn.execute(
        "DELETE FROM analysis_packages WHERE dataset_id = ? AND session_id = ?",
        (dataset_id, session_id),
    )
    conn.execute(
        "DELETE FROM datasets WHERE dataset_id = ? AND session_id = ?",
        (dataset_id, session_id),
    )
    conn.commit()


# ===================== analysis_packages =====================

def save_package(package_id: str, session_id: str, dataset_id: str,
                 payload: Dict[str, Any], saved_at: Optional[str],
                 created_at: float) -> None:
    """写入/更新分析包。"""
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO analysis_packages (package_id, session_id, dataset_id, payload_json, saved_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(package_id) DO UPDATE SET
            payload_json = excluded.payload_json,
            saved_at = excluded.saved_at,
            dataset_id = excluded.dataset_id
        """,
        (package_id, session_id, dataset_id, _to_json(payload),
         saved_at, created_at),
    )
    conn.commit()


def load_package(package_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    row = conn.execute(
        "SELECT payload_json FROM analysis_packages WHERE package_id = ?",
        (package_id,),
    ).fetchone()
    return _from_json(row["payload_json"]) if row else None


def load_packages_by_session(session_id: str) -> List[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT package_id, dataset_id, payload_json, saved_at FROM analysis_packages WHERE session_id = ?",
        (session_id,),
    ).fetchall()
    result = []
    for r in rows:
        pkg = _from_json(r["payload_json"])
        pkg["_dataset_id"] = r["dataset_id"]
        pkg["_saved_at"] = r["saved_at"]
        result.append(pkg)
    return result


def load_packages_by_dataset(session_id: str, dataset_id: str) -> List[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT payload_json FROM analysis_packages WHERE session_id = ? AND dataset_id = ?",
        (session_id, dataset_id),
    ).fetchall()
    return [_from_json(r["payload_json"]) for r in rows]


def delete_package(package_id: str) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM analysis_packages WHERE package_id = ?", (package_id,))
    conn.commit()
