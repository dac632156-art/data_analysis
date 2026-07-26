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
from backend.utils.ai_error import enhance_ai_error
from src.ai_agent.agent import DataAnalysisAgent
import logging
_log = logging.getLogger("insights")

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


def _extract_json_string_value(text: str, key: str):
    """从文本中抽取 `"key": "..."` 的 JSON 字符串值（正确处理转义），失败返回 None。

    逐字符扫描以处理值内部的转义引号/反斜杠，比正则更可靠。
    """
    pattern = r'"' + _re.escape(key) + r'"\s*:\s*"'
    m = _re.search(pattern, text)
    if not m:
        return None
    i = m.end()  # 指向起始引号后的第一个字符（值的开始）
    n = len(text)
    out = []
    esc_map = {'n': '\n', 't': '\t', 'r': '\r', '"': '"', '\\': '\\', '/': '/', 'b': '\b', 'f': '\f'}
    while i < n:
        c = text[i]
        if c == '\\' and i + 1 < n:
            out.append(esc_map.get(text[i + 1], text[i + 1]))
            i += 2
            continue
        if c == '"':
            return ''.join(out)  # 未转义的闭合引号 → 结束
        out.append(c)
        i += 1
    return ''.join(out)  # 未找到闭合引号（如截断）→ 返回已扫描内容


def _extract_insights_text(data: dict, raw: str) -> str:
    """兼容 'insights' / 'ins' 双 key 抽取洞察 Markdown；皆空则回退 raw。"""
    ins = data.get("insights")
    if isinstance(ins, str) and ins.strip():
        return ins
    ins2 = data.get("ins")
    if isinstance(ins2, str) and ins2.strip():
        return ins2
    return raw


def _extract_intents(data: dict) -> list:
    """兼容 'intents' / 'intent' 双 key 抽取意图列表；非 list 返回 []。"""
    intents = data.get("intents")
    if isinstance(intents, list):
        return intents
    intents2 = data.get("intent")
    if isinstance(intents2, list):
        return intents2
    return []


def _best_effort_extract_ins(raw: str) -> str:
    """json.loads 彻底失败时，尽力从原始文本抽取 ins/insights 字符串值；失败回退 raw。"""
    for key in ("insights", "ins"):
        val = _extract_json_string_value(raw, key)
        if val and val.strip():
            return val
    return raw


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
            intents = _extract_intents(data)
            if len(intents) > 0:
                _log.info(f"Step 1 成功: 正则提取 → intents {len(intents)} 个")
                return {"success": True, "insights": _extract_insights_text(data, result), "intents": intents}
            _log.info(f"Step 1: 正则提取成功但 intents 为空，继续 Step 2")
        except _json.JSONDecodeError as e:
            _log.info(f"Step 1 失败: 正则提取后 JSON 解析错误 ({e})，继续 Step 2")

    # ---- Step 2: 括号平衡提取 → json.loads ----
    balanced = _extract_json_by_brace_balance(raw)
    if balanced != raw:
        # 说明提取了一段子串，尝试解析
        try:
            data = _json.loads(balanced)
            intents = _extract_intents(data)
            if len(intents) > 0:
                _log.info(f"Step 2 成功: 括号平衡提取 → intents {len(intents)} 个")
                return {"success": True, "insights": _extract_insights_text(data, result), "intents": intents}
            _log.info(f"Step 2: 括号平衡提取成功但 intents 为空，继续 Step 3")
        except _json.JSONDecodeError as e:
            _log.info(f"Step 2 失败: 括号平衡提取后 JSON 解析错误 ({e})，继续 Step 3")
    else:
        # balanced == raw，尝试直接解析整段
        try:
            data = _json.loads(raw)
            intents = _extract_intents(data)
            if len(intents) > 0:
                _log.info(f"Step 2 成功: 直接解析 → intents {len(intents)} 个")
                return {"success": True, "insights": _extract_insights_text(data, result), "intents": intents}
            _log.info(f"Step 2: 直接解析成功但 intents 为空，继续 Step 3")
        except _json.JSONDecodeError:
            _log.info(f"Step 2 失败: 直接解析 JSON 错误，继续 Step 3")

    # ---- Step 3: Planner 纯规则兜底 ----
    default_intents = []  # 旧 Planner 兜底已移除，新流程由列名匹配引擎决定分析
    _log.info(f"Step 3 兜底: Planner 生成 {len(default_intents)} 个 default intents")
    # insights 文本尽力抽取（JSON 解析失败可能是 key 漂移/超长截断），
    # 抽取不到时再回退原始内容，避免向前端返回裸 JSON 字符串。
    return {
        "success": True,
        "insights": _best_effort_extract_ins(result),
        "intents": default_intents,
        "is_fallback": True,  # 标记这是兜底生成，前端可据此调整 UI
    }


@router.post("/insights/generate", deprecated=True)
async def api_generate_insights(req: InsightsRequest):
    """【已废弃】旧版 AI 洞察 + intents 接口。前端「生成数据洞察」已改为统一异步流水线
    （/analysis/process-datasets），由列名匹配引擎确定性产出分析包，不再依赖此接口的 intents。
    保留仅供兼容历史调用。"""
    _log.warning("[deprecated] /insights/generate 已被 /analysis/process-datasets 取代")
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
        default_intents = []  # 旧 Planner 兜底已移除，新流程由列名匹配引擎决定分析
        return {"success": True, "insights": str(result), "intents": default_intents, "is_fallback": True}
    except Exception as e:
        # AI 完全失败 → Planner 兜底生成 intents，不让用户看到空白
        # 但如果是 model_not_found 等明确错误，先增强提示再兜底
        enhanced_msg = enhance_ai_error(e, model=req.model or "", base_url=req.base_url or "")
        default_intents = []  # 旧 Planner 兜底已移除，新流程由列名匹配引擎决定分析
        return {
            "success": True,
            "insights": f"⚠️ AI 调用失败：{enhanced_msg}，已自动生成推荐分析计划",
            "intents": default_intents,
            "is_fallback": True,
        }


@router.post("/intents/default", deprecated=True)
async def api_get_default_intents(req: InsightsRequest):
    """【已废弃】旧版纯规则兜底 intents 接口。新流程由列名匹配引擎决定分析，
    前端不再展示 intents 勾选，故不再调用。保留仅供兼容。"""
    logger.warning("[deprecated] /intents/default 已不再被前端调用")
    df = manager.get_data(req.session_id)
    if df is None:
        raise HTTPException(status_code=404, detail="未找到数据，请先上传")
    try:
        intents = []  # 旧 Planner 兜底已移除，新流程由列名匹配引擎决定分析
        return {
            "success": True,
            "intents": intents,
            "is_fallback": True,
            "source": "rule",
        }
    except Exception as e:
        _log.exception("generate_default_intents failed: %s", e)
        raise HTTPException(status_code=500, detail=f"生成默认分析计划失败：{e}")


@router.post("/chat/analyze")
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
        
        # 尝试解析 intents（同首次洞察的逻辑，传入 df 使 Step 3 兜底生效）
        parsed = _parse_ai_result_to_intents(answer, df)
        if parsed["success"] and parsed.get("intents"):
            return {
                "success": True,
                "answer": parsed.get("insights", answer),
                "intents": parsed["intents"],
                "is_fallback": parsed.get("is_fallback", False),
            }
        return {"success": True, "answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=enhance_ai_error(e, model=req.model or "", base_url=req.base_url or ""))
