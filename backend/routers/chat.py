"""
AI 对话 API 路由（兼容 chat 端点）
"""
from fastapi import APIRouter, Depends
from .insights import router as insights_router, api_chat_analyze, ChatRequest

router = APIRouter()


@router.post("/chat")
async def chat_analyze(req: ChatRequest):
    """AI 对话分析（兼容端点）
    
    等同于 /api/insights/chat 端点
    """
    return await api_chat_analyze(req)
