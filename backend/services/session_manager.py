"""
会话管理器 - 替代 Streamlit session_state
使用 UUID 作为 session_id，DataFrame 存储在内存中
"""

import uuid
import time
import pandas as pd
from typing import Dict, Optional, List, Any
from threading import Lock


class SessionData:
    """单个会话的数据"""
    def __init__(self):
        self.df: Optional[pd.DataFrame] = None
        self.df_original: Optional[pd.DataFrame] = None
        self.df_undo_stack: List[pd.DataFrame] = []  # 撤销栈（最多保存 20 步）
        self.cleaning_history: List[Dict] = []
        self.analysis_history: List[Dict] = []
        self.saved_charts: List[Dict[str, Any]] = []  # 用户从分析页保存的图表 [{"title":..., "option":..., "saved_at":...}, ...]
        self.api_key: str = ""
        self.created_at: float = time.time()
        self.last_access: float = time.time()


class SessionManager:
    """会话管理器，线程安全的内存存储"""
    
    def __init__(self, max_sessions: int = 50, session_timeout: int = 3600):
        self._sessions: Dict[str, SessionData] = {}
        self._lock = Lock()
        self._max_sessions = max_sessions
        self._session_timeout = session_timeout
    
    def create_session(self) -> str:
        """创建新会话，返回 session_id"""
        session_id = str(uuid.uuid4())
        with self._lock:
            # 清理过期会话
            self._cleanup_sync()
            # 检查会话数限制
            if len(self._sessions) >= self._max_sessions:
                oldest = min(self._sessions.keys(), 
                             key=lambda k: self._sessions[k].last_access)
                del self._sessions[oldest]
            self._sessions[session_id] = SessionData()
        return session_id
    
    def get_session(self, session_id: str) -> Optional[SessionData]:
        """获取会话数据"""
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.last_access = time.time()
            return session
    
    def set_data(self, session_id: str, df: pd.DataFrame):
        """设置 DataFrame，如果 session 不存在则自动创建"""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                # 自动创建 session（前端可能用旧的 session_id 重连）
                session = SessionData()
                self._sessions[session_id] = session
            session.df_original = df.copy()
            session.df = df.copy()
            session.last_access = time.time()
    
    def get_data(self, session_id: str) -> Optional[pd.DataFrame]:
        """获取当前 DataFrame"""
        session = self.get_session(session_id)
        return session.df if session else None
    
    def get_original_data(self, session_id: str) -> Optional[pd.DataFrame]:
        """获取原始 DataFrame"""
        session = self.get_session(session_id)
        return session.df_original if session else None
    
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

    def clear_data(self, session_id: str):
        """清除会话数据"""
        with self._lock:
            self._sessions.pop(session_id, None)
    
    def _cleanup_sync(self):
        """清理过期会话（非线程安全，需在锁中调用）"""
        now = time.time()
        expired = [
            sid for sid, sdata in self._sessions.items()
            if now - sdata.last_access > self._session_timeout
        ]
        for sid in expired:
            del self._sessions[sid]
    
    def cleanup(self):
        """清理过期会话（线程安全）"""
        with self._lock:
            self._cleanup_sync()


# 全局单例
manager = SessionManager()
