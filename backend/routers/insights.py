"""
AI 洞察和 AI 对话 API 路由
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import asyncio
import json as _json
import re as _re
from concurrent.futures import ThreadPoolExecutor

from backend.services.session_manager import manager
from src.ai_agent.agent import DataAnalysisAgent
from src.planner import Planner

router = APIRouter()

# Planner 实例（用于 fallback intents 生成）
_PLANNER = Planner()


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


def _extract_json_by_brace_balance(text: str) -> str:
    """从文本中提取最长的平衡花括号 JSON 片段。
    
    使用括号深度计数法，而非简单的 find/rfind，
    避免 insights 字段内部的花括号导致提取到错误的闭合位置。
    """
    start = text.find('{')
    if start == -1:
        return text
    depth = 0
    for i in range(start, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
        if depth == 0:
            return text[start:i+1]
    # 未平衡，返回从第一个 { 到末尾
    return text[start:]


def _parse_ai_result_to_intents(result: str, df=None) -> dict:
    """三层解析 AI 输出 → 确保 intents 永不为空
    
    Step 1: 正则提取 ```json...``` → json.loads
    Step 2: 括号平衡提取 → json.loads
    Step 3: Planner 纯规则兜底生成 default intents
    """
    raw = result.strip()

    # ---- Step 1: 正则提取 markdown 包裹的 JSON ----
    json_match = _re.search(r'```(?:json)?\s*\n?(.*?)\n?```', raw, _re.DOTALL)
    if json_match:
        candidate = json_match.group(1).strip()
        try:
            data = _json.loads(candidate)
            intents = data.get("intents", [])
            if isinstance(intents, list) and len(intents) > 0:
                print(f"[insights] Step 1 成功: 正则提取 → intents {len(intents)} 个")
                return {"success": True, "insights": data.get("insights", result), "intents": intents}
            print(f"[insights] Step 1: 正则提取成功但 intents 为空，继续 Step 2")
        except _json.JSONDecodeError as e:
            print(f"[insights] Step 1 失败: 正则提取后 JSON 解析错误 ({e})，继续 Step 2")

    # ---- Step 2: 括号平衡提取 → json.loads ----
    balanced = _extract_json_by_brace_balance(raw)
    if balanced != raw:
        # 说明提取了一段子串，尝试解析
        try:
            data = _json.loads(balanced)
            intents = data.get("intents", [])
            if isinstance(intents, list) and len(intents) > 0:
                print(f"[insights] Step 2 成功: 括号平衡提取 → intents {len(intents)} 个")
                return {"success": True, "insights": data.get("insights", result), "intents": intents}
            print(f"[insights] Step 2: 括号平衡提取成功但 intents 为空，继续 Step 3")
        except _json.JSONDecodeError as e:
            print(f"[insights] Step 2 失败: 括号平衡提取后 JSON 解析错误 ({e})，继续 Step 3")
    else:
        # balanced == raw，尝试直接解析整段
        try:
            data = _json.loads(raw)
            intents = data.get("intents", [])
            if isinstance(intents, list) and len(intents) > 0:
                print(f"[insights] Step 2 成功: 直接解析 → intents {len(intents)} 个")
                return {"success": True, "insights": data.get("insights", result), "intents": intents}
            print(f"[insights] Step 2: 直接解析成功但 intents 为空，继续 Step 3")
        except _json.JSONDecodeError:
            print(f"[insights] Step 2 失败: 直接解析 JSON 错误，继续 Step 3")

    # ---- Step 3: Planner 纯规则兜底 ----
    default_intents = _PLANNER.generate_default_intents(df) if df is not None else []
    print(f"[insights] Step 3 兜底: Planner 生成 {len(default_intents)} 个 default intents")
    # insights 文本仍保留 AI 返回的原始内容（即使不是 JSON）
    return {
        "success": True,
        "insights": result,
        "intents": default_intents,
        "is_fallback": True,  # 标记这是兜底生成，前端可据此调整 UI
    }


@router.post("/insights/generate")
async def api_generate_insights(req: InsightsRequest):
    """生成 AI 数据洞察报告 + 分析意图列表（三层防御：AI JSON → AI 文本解析 → Planner 兜底）"""
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
        
        # 三层解析：确保 intents 永不为空
        if isinstance(result, str):
            return _parse_ai_result_to_intents(result, df)
        
        # 非 string 结果（极端情况）
        default_intents = _PLANNER.generate_default_intents(df)
        return {"success": True, "insights": str(result), "intents": default_intents, "is_fallback": True}
    except Exception as e:
        # AI 完全失败 → Planner 兜底生成 intents，不让用户看到空白
        default_intents = _PLANNER.generate_default_intents(df)
        return {
            "success": True,
            "insights": f"⚠️ AI 调用失败：{str(e)}，已自动生成推荐分析计划",
            "intents": default_intents,
            "is_fallback": True,
        }


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
        
        # 尝试解析 intents（同首次洞察的逻辑）
        parsed = _parse_ai_result_to_intents(answer)
        if parsed["success"] and parsed.get("intents"):
            return {"success": True, "answer": parsed.get("insights", answer), "intents": parsed["intents"]}
        return {"success": True, "answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 回答失败: {str(e)}")
