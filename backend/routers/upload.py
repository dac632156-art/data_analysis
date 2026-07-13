"""
文件上传 API 路由
"""
import io
import asyncio
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Body
from pydantic import BaseModel
from typing import Dict, Any
import pandas as pd
import numpy as np

from src.data_loader import load_csv, load_excel, load_json, load_sqlite, get_data_info, get_column_info
from backend.services.session_manager import manager
from config import MAX_FILE_SIZE_BYTES, MAX_UPLOAD_SIZE_MB

router = APIRouter()

# P0（内存画像结论三）：限制并发文件解析，避免 XLSX 解析瞬时 RSS 尖峰（×3.9）叠加导致 OOM。
# 解析从事件循环移入线程池（asyncio.to_thread），既释放事件循环避免大文件卡住其他请求，
# 又通过信号量把「同时解析」限制为小并发，使 xlsx 尖峰重叠 ≤ 3×33MB，远低于 350MB 可用池。
# 仅对尖峰风险高的 xlsx / sqlite 限流；csv / json 膨胀低（×1.1）直接线程池解析，不占信号量。
_PARSE_SEMAPHORE = asyncio.Semaphore(3)


def _parse_missing_rate(row) -> float:
    """解析缺失率，兼容字符串 '0.0%' 和数字格式"""
    val = row.get("缺失率", row.get("missing_rate", 0))
    if isinstance(val, str):
        val = val.replace("%", "")
        try:
            return float(val) / 100.0
        except ValueError:
            return 0.0
    return float(val)


class UploadResponse(BaseModel):
    session_id: str
    success: bool
    file_name: str
    rows: int
    columns: int
    preview: list
    column_info: list


@router.post("/upload/gate")
async def upload_gate(session_id: str = Body(..., embed=True)):
    """预约数据插槽闸门：在真正传文件前调用。

    - 有空位：返回 {"granted": true, "session_id"}，前端直接上传。
    - 满员：返回 {"granted": false, "ticket_id", "position"}，前端进入排队弹窗并轮询。
    统一用 200 + 结构化 JSON，避免触发响应拦截器对 429 结构的破坏。
    """
    if not session_id:
        raise HTTPException(status_code=400, detail="缺少 session_id")
    return manager.acquire_for_upload(session_id)


@router.get("/upload/queue/{ticket_id}")
async def queue_status(ticket_id: str):
    """查询排队状态：ready（附 session_id）/ queued（附 position）/ expired。"""
    return manager.queue_status(ticket_id)


@router.post("/upload/queue/cancel")
async def cancel_queue(ticket_id: str = Body(..., embed=True)):
    """取消排队：尽力从等待队列移除票据。"""
    if not ticket_id:
        raise HTTPException(status_code=400, detail="缺少 ticket_id")
    manager.cancel_queue(ticket_id)
    return {"success": True}


@router.post("/upload/release")
async def release_slot(session_id: str = Body(..., embed=True)):
    """释放某会话的数据插槽（丢弃 DataFrame/原文件以释放内存），并自动晋升队首。

    这是「自动入队」的关键触发点：某用户结束使用、离开或清空数据后调用，
    排队中的用户即可获得空位并开始上传。
    """
    if not session_id:
        raise HTTPException(status_code=400, detail="缺少 session_id")
    released = manager.release_slot(session_id)
    return {"success": True, "released": released}


@router.post("/upload")
async def upload_file(file: UploadFile = File(...), session_id: str = Form("")):
    """
    上传数据文件
    支持 CSV/Excel/JSON/SQLite 格式
    返回数据预览和字段信息
    """
    # 验证文件大小
    content = await file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=413, detail=f"文件大小超过 {MAX_UPLOAD_SIZE_MB}MB 限制")

    # 验证文件格式
    filename = file.filename.lower()
    ext = filename.rsplit('.', 1)[-1] if '.' in filename else ''
    supported = {'csv', 'xlsx', 'xls', 'json', 'db', 'sqlite'}
    if ext not in supported:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: .{ext}。支持: CSV, Excel, JSON, SQLite"
        )

    # 创建或使用已有会话
    if not session_id:
        # 正常路径前端必带 sessionId（已预占插槽），此兜底理论不触发；仍计入上限以保一致
        session_id = manager.create_session()
        manager.reserve_session(session_id)

    try:
        # 加载数据（解析移入线程池 + 信号量限流，见 _PARSE_SEMAPHORE 说明）
        if ext == 'csv':
            df = await asyncio.to_thread(load_csv, content, file.filename)
        elif ext in ('xlsx', 'xls'):
            async with _PARSE_SEMAPHORE:
                df = await asyncio.to_thread(load_excel, content)
        elif ext == 'json':
            df = await asyncio.to_thread(load_json, content)
        elif ext in ('db', 'sqlite'):
            async with _PARSE_SEMAPHORE:
                tables = await asyncio.to_thread(load_sqlite, content)
            # 取第一个表作为数据
            if isinstance(tables, dict):
                first_table = list(tables.keys())[0]
                df = tables[first_table]
            else:
                df = tables
        else:
            raise HTTPException(status_code=400, detail="不支持的文件格式")

        if df is None or df.empty:
            raise HTTPException(status_code=400, detail="文件内容为空或无法读取")

        # 存储数据到会话
        manager.set_data(session_id, df)

        # 获取预览和数据信息（将 NaN 替换为 None 以确保 JSON 可序列化）
        preview = df.head(100).replace({np.nan: None}).to_dict(orient="records")
        column_info = get_column_info(df)
        data_info = get_data_info(df)

        # 转换列信息为列表
        columns_list = []
        for _, row in column_info.iterrows():
            columns_list.append({
                "name": str(row.get("列名", row.get("column", ""))),
                "dtype": str(row.get("数据类型", row.get("dtype", ""))),
                "missing": int(row.get("缺失值", row.get("missing", 0))),
                "missing_rate": _parse_missing_rate(row),
                "unique": int(row.get("唯一值数", row.get("unique", 0))),
                "sample": str(row.get("示例值", row.get("sample", ""))),
            })

        return {
            "session_id": session_id,
            "success": True,
            "file_name": file.filename,
            "rows": int(data_info.get("行数", len(df))),
            "columns": int(data_info.get("列数", len(df.columns))),
            "memory_usage": str(data_info.get("内存占用", data_info.get("memory_usage", ""))),
            "total_missing": int(data_info.get("缺失值总数", data_info.get("total_missing", 0))),
            "duplicate_rows": int(data_info.get("重复行数", data_info.get("duplicate_rows", 0))),
            "preview": preview,
            "column_info": columns_list,
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback as _traceback
        import logging as _logging
        tb = _traceback.format_exc()
        _logging.getLogger("uvicorn.error").error(f"Upload error: {type(e).__name__}: {e}\n{tb}")
        raise HTTPException(status_code=500, detail=f"文件处理失败: {str(e)}")
