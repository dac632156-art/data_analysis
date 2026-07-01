"""
AI 洞察和 AI 对话 API 路由
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor

from backend.services.session_manager import manager
from src.ai_agent.agent import DataAnalysisAgent

router = APIRouter()


class InsightsRequest(BaseModel):
    session_id: str
    api_key: Optional[str] = ""
    base_url: Optional[str] = None
    model: Optional[str] = None


class ChatRequest(BaseModel):
    session_id: str
    question: str
    api_key: Optional[str] = ""
    base_url: Optional[str] = None
    model: Optional[str] = None


def _get_api_key(session_id: str, req_key: str) -> str:
    """获取 API Key（优先用请求中的，其次用会话中的）"""
    if req_key:
        return req_key
    return manager.get_api_key(session_id)


@router.post("/insights/generate")
async def api_generate_insights(req: InsightsRequest):
    """生成 AI 数据洞察报告 + 分析意图列表"""
    df = manager.get_data(req.session_id)
    if df is None:
        raise HTTPException(status_code=404, detail="未找到数据")
    
    api_key = _get_api_key(req.session_id, req.api_key)
    if not api_key:
        raise HTTPException(status_code=400, detail="需要 DeepSeek API Key")
    
    try:
        kwargs = {"api_key": api_key}
        if req.base_url:
            kwargs["base_url"] = req.base_url
        if req.model:
            kwargs["model"] = req.model
        agent = DataAnalysisAgent(**kwargs)
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=1) as executor:
            result = await loop.run_in_executor(executor, agent.generate_insights, df)
        
        # 尝试解析 JSON（Structured Output）
        import json as _json
        if isinstance(result, str):
            try:
                data = _json.loads(result)
                return {"success": True, "insights": data.get("insights", result), "intents": data.get("intents", [])}
            except _json.JSONDecodeError:
                return {"success": True, "insights": result, "intents": []}
        
        return {"success": True, "insights": str(result), "intents": []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 分析失败: {str(e)}")


@router.post("/chat/analyze")
@router.post("/chat")
async def api_chat_analyze(req: ChatRequest):
    """AI 对话分析"""
    df = manager.get_data(req.session_id)
    if df is None:
        raise HTTPException(status_code=404, detail="未找到数据")
    
    api_key = _get_api_key(req.session_id, req.api_key)
    if not api_key:
        raise HTTPException(status_code=400, detail="需要 API Key")
    
    # 保存 API Key 到会话
    if req.api_key:
        manager.set_api_key(req.session_id, req.api_key)
    
    try:
        kwargs = {"api_key": api_key}
        if req.base_url:
            kwargs["base_url"] = req.base_url
        if req.model:
            kwargs["model"] = req.model
        agent = DataAnalysisAgent(**kwargs)
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=1) as executor:
            answer = await loop.run_in_executor(executor, agent.analyze, req.question, df)
        return {"success": True, "answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 回答失败: {str(e)}")
