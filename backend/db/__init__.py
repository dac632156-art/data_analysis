"""
数据访问层（DAL）包入口。
封装 SQLite 连接管理、建表与 CRUD，供 SessionManager 调用。
业务代码不应直接写 SQL，统一走本包与 crud.py。
"""
from .connection import get_connection, init_db, close_connection

__all__ = ["get_connection", "init_db", "close_connection"]
