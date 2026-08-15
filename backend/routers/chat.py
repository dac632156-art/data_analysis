"""
聊天路由（智能体版）：将用户消息交给 DataAnalysisAgent 的 agentic_chat 做
function calling 循环，支持多轮 choice 选择、工具执行、清洗后自动分析。

链路：
上传即侦察 → 用户发消息 → agentic_chat（LLM 调工具直到给出最终回答）
→ 结构化响应 {kind, content, choices, tool_results, data_preview}
→ 前端渲染（text / choice 按钮 / 工具执行状态 / 数据预览）
"""
import traceback
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from backend.services.session_manager import manager
from src.ai_agent.agent import DataAnalysisAgent
from src.utils.json_serializer import sanitize_json

router = APIRouter()


def _sanitize_history(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """写回 session 前净化历史：剥离工具调用痕迹，只保留纯文字对话。

    保留：system / user / assistant（去掉 tool_calls 字段）消息。
    剥离：role=="tool" 的回灌消息，以及 assistant 消息里的 tool_calls 键。

    这样下一轮 agentic_chat 读 history 时，LLM 看不到上一轮的工具链，
    不会误判为"未完成任务"而重调工具（切断大类 B 死循环源）。
    注意：clean_data 体检态的弹框依赖 tool_results + await_choice 字段返回给前端，
    不依赖写回 history 的 tool 消息，故剥离不影响前端交互。
    """
    cleaned: List[Dict[str, Any]] = []
    for m in messages:
        role = m.get("role")
        if role == "tool":
            continue  # 丢弃工具回灌消息
        if role == "assistant":
            # 复制并去掉 tool_calls 字段（保留 content 文字）
            item = {k: v for k, v in m.items() if k != "tool_calls"}
            cleaned.append(item)
        else:
            # system / user 原样保留
            cleaned.append(m)
    return cleaned


class ChatRequest(BaseModel):
    session_id: str
    message: str
    choice: Optional[str] = None   # 用户点击的清洗方案 id（多轮续接时带）


# 合法清洗方法集合，必须与 src/tools_registry.py 的 _FIVE_METHODS_META[].method 及
# clean_data 工具 schema 的 enum 保持一致；新增清洗方法时需同步更新此处。
LEGAL_METHODS = {"fill_mean", "fill_median", "fill_mode", "fill_0"}


@router.post("/chat/send")
async def api_chat_send(req: ChatRequest):
    """聊天接口：POST /api/chat/send {session_id, message, choice?}
    → {kind, content, choices, tool_results, data_preview}
    """
    # choice 续接场景下 message 可为空（内容由下方拼接生成）
    if (not req.message or not req.message.strip()) and not req.choice:
        raise HTTPException(status_code=400, detail="消息不能为空")

    session = manager.get_session(req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    if not session.datasets:
        raise HTTPException(status_code=404, detail="请先上传数据：当前会话没有可用数据集")

    # 上传即侦察：若未侦察过则补扫（确保 data_profile 已存）
    if not session.data_profile:
        try:
            from src.data_recon import scan
            df = manager.get_data(req.session_id)
            if df is not None:
                session.data_profile = scan(df)
        except Exception:
            pass

    try:
        agent = DataAnalysisAgent()
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

    # 多轮：若用户点了 choice，把选择拼进消息；并恢复历史
    # 防御：只有属于 LEGAL_METHODS 的合法 method 才走"选择续接 + 执行清洗"分支；
    # 其余（含 [object Object] 等垃圾字符串）一律当普通消息处理，避免误执行清洗。
    choice = req.choice if (isinstance(req.choice, str) and req.choice in LEGAL_METHODS) else None
    message = req.message or '分析'
    if choice:
        message = f"我选择执行：{choice}（请调用 clean_data 工具执行该清洗方法）"
    history = session.messages if session.messages else None

    try:
        result = agent.agentic_chat(message, req.session_id, history=history)
    except Exception as e:
        print("[chat/send] EXCEPTION traceback:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"AI 调用失败：{str(e)}")

    # 写回对话历史，供下一轮续接。
    # 关键：剥离本轮内部的 tool_calls 与 role:"tool" 回灌消息，只保留
    # system/user/assistant 纯文字对话。否则下一轮 LLM 会把上一轮未完成的
    # 工具链误判为"待办任务"而反复重调工具，导致撑满 max_rounds 被强制截断。
    session.messages = _sanitize_history(result.get("messages", []))

    # 若清洗后返回了数据预览占位，回填 head（取最新 merged/active df 前 5 行）
    data_preview = result.get("data_preview")
    if data_preview:
        try:
            df = manager.get_data(req.session_id)
            # 优先取 merged 宽表
            for did, ds in session.datasets.items():
                if getattr(ds, "is_merged", False):
                    mdf = manager.get_dataset_df(req.session_id, did)
                    if mdf is not None:
                        df = mdf
                        break
            if df is not None:
                data_preview["head"] = df.head(5).replace({float("nan"): None}).to_dict(orient="records")
        except Exception:
            pass

    return sanitize_json({
        "success": True,
        "kind": result.get("kind", "text"),
        "content": result.get("content", ""),
        "choices": result.get("choices", []),
        "tool_results": result.get("tool_results", []),
        "data_preview": data_preview,
    })
