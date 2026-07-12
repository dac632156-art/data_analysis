"""
数据清洗 API 路由
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Any, Dict, Tuple
import pandas as pd
import numpy as np
import asyncio
from concurrent.futures import ThreadPoolExecutor

from backend.services.session_manager import manager
from backend.utils.ai_error import enhance_ai_error
from src.data_cleaner import (
    get_missing_value_report, handle_missing_values,
    detect_data_type_issues, convert_column_type,
    detect_outliers, handle_outliers, drop_duplicate_rows
)

router = APIRouter()


class SessionRequest(BaseModel):
    session_id: str


@router.post("/clean/missing-report")
async def api_missing_report(req: SessionRequest):
    """获取缺失值报告"""
    df = manager.get_data(req.session_id)
    if df is None:
        raise HTTPException(status_code=404, detail="未找到数据")
    report = get_missing_value_report(df)
    return {"success": True, "report": report}


@router.post("/clean/handle-missing")
async def api_handle_missing(req: SessionRequest, column: str, method: str):
    """处理缺失值"""
    df = manager.get_data(req.session_id)
    if df is None:
        raise HTTPException(status_code=404, detail="未找到数据")
    valid_methods = ['drop', 'drop_column', 'fill_mean', 'fill_median', 'fill_mode', 'fill_0', 'fill_unknown']
    if method not in valid_methods:
        raise HTTPException(status_code=400, detail=f"无效的方法: {method}")
    if column not in df.columns:
        raise HTTPException(status_code=400, detail=f"无效的列名: {column}")
    try:
        df_clean = handle_missing_values(df, column, method)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    manager.push_undo_state(req.session_id)  # 保存撤销点
    manager.update_data(req.session_id, df_clean)
    manager.add_cleaning_step(req.session_id, {"action": f"处理缺失值 - {column}", "method": method})
    return {
        "success": True,
        "preview": df_clean.head(100).replace({np.nan: None}).to_dict(orient="records"),
        "rows": len(df_clean),
        "columns": list(df_clean.columns),
    }


@router.post("/clean/detect-types")
async def api_detect_types(req: SessionRequest):
    """检测数据类型问题"""
    df = manager.get_data(req.session_id)
    if df is None:
        raise HTTPException(status_code=404, detail="未找到数据")
    issues = detect_data_type_issues(df)
    return {"success": True, "issues": issues}


@router.post("/clean/convert-type")
async def api_convert_type(req: SessionRequest, column: str, target_type: str):
    """转换列数据类型"""
    df = manager.get_data(req.session_id)
    if df is None:
        raise HTTPException(status_code=404, detail="未找到数据")
    valid_types = ['datetime', 'numeric', 'string', 'category']
    if target_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"无效的目标类型: {target_type}")
    try:
        df_converted = convert_column_type(df, column, target_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    manager.push_undo_state(req.session_id)  # 保存撤销点
    manager.update_data(req.session_id, df_converted)
    manager.add_cleaning_step(req.session_id, {"action": f"转换类型 - {column}", "target_type": target_type})
    return {
        "success": True,
        "preview": df_converted.head(100).replace({np.nan: None}).to_dict(orient="records"),
        "dtype": str(df_converted[column].dtype),
    }


@router.post("/clean/detect-outliers")
async def api_detect_outliers(req: SessionRequest, method: str = "iqr"):
    """检测异常值"""
    df = manager.get_data(req.session_id)
    if df is None:
        raise HTTPException(status_code=404, detail="未找到数据")
    result = detect_outliers(df, method)
    return {"success": True, "outliers": result}


@router.post("/clean/handle-outliers")
async def api_handle_outliers(req: SessionRequest, column: str, method: str = "iqr", action: str = "remove"):
    """处理异常值"""
    df = manager.get_data(req.session_id)
    if df is None:
        raise HTTPException(status_code=404, detail="未找到数据")
    df_clean = handle_outliers(df, column, method, action)
    manager.push_undo_state(req.session_id)  # 保存撤销点
    manager.update_data(req.session_id, df_clean)
    manager.add_cleaning_step(req.session_id, {"action": f"处理异常值 - {column}", "method": method, "sub_action": action})
    return {
        "success": True,
        "preview": df_clean.head(100).replace({np.nan: None}).to_dict(orient="records"),
        "rows": len(df_clean),
    }


@router.post("/clean/drop-duplicates")
async def api_drop_duplicates(req: SessionRequest):
    """删除重复行"""
    df = manager.get_data(req.session_id)
    if df is None:
        raise HTTPException(status_code=404, detail="未找到数据")
    df_clean, dropped = drop_duplicate_rows(df)
    manager.push_undo_state(req.session_id)  # 保存撤销点
    manager.update_data(req.session_id, df_clean)
    manager.add_cleaning_step(req.session_id, {"action": "删除重复行", "dropped": dropped})
    return {
        "success": True,
        "preview": df_clean.head(100).replace({np.nan: None}).to_dict(orient="records"),
        "rows_dropped": dropped,
        "rows": len(df_clean),
    }


@router.post("/clean/reset")
async def api_reset_data(req: SessionRequest):
    """恢复数据到原始状态"""
    session = manager.get_session(req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="未找到原始数据，请先上传文件")
    df_orig = manager.get_original_data(req.session_id)
    if df_orig is None:
        raise HTTPException(status_code=404, detail="原始数据已释放，请重新上传")
    manager.update_data(req.session_id, df_orig)
    return {
        "success": True,
        "preview": df_orig.head(100).replace({np.nan: None}).to_dict(orient="records"),
        "rows": len(df_orig),
        "columns": list(df_orig.columns),
    }


@router.post("/clean/undo")
async def api_undo(req: SessionRequest):
    """撤销上一步清洗操作"""
    undone = manager.undo_last_action(req.session_id)
    if undone is None:
        raise HTTPException(status_code=400, detail="没有可撤销的操作")
    remain = manager.get_undo_count(req.session_id)
    return {
        "success": True,
        "preview": undone.head(100).replace({np.nan: None}).to_dict(orient="records"),
        "rows": len(undone),
        "columns": list(undone.columns),
        "remain_undo": remain,
    }


@router.post("/clean/history")
async def api_cleaning_history(req: SessionRequest):
    """获取清洗历史"""
    history = manager.get_cleaning_history(req.session_id)
    return {"success": True, "history": history}


@router.post("/clean/compare")
async def api_compare(req: SessionRequest):
    """获取清洗前后对比"""
    df = manager.get_data(req.session_id)
    df_orig = manager.get_original_data(req.session_id)
    if df is None:
        raise HTTPException(status_code=404, detail="未找到数据")
    if df_orig is None:
        raise HTTPException(status_code=404, detail="原始数据已释放，请重新上传")
    return {
        "success": True,
        "before": {
            "rows": len(df_orig) if df_orig is not None else 0,
            "columns": list(df_orig.columns) if df_orig is not None else [],
        },
        "after": {
            "rows": len(df),
            "columns": list(df.columns),
        },
    }


# ====== AI 智能清洗 API ======

class AICleanRequest(BaseModel):
    session_id: str
    request: str  # 用户的自然语言清洗需求
    api_key: Optional[str] = ""
    base_url: Optional[str] = None
    model: Optional[str] = None


@router.post("/clean/ai-clean")
async def api_ai_clean(req: AICleanRequest):
    """AI 智能清洗：用户描述清洗需求，AI 自动分析并执行清洗"""
    df = manager.get_data(req.session_id)
    if df is None:
        raise HTTPException(status_code=404, detail="未找到数据")

    # 获取 API Key 和模型配置
    api_key = req.api_key or manager.get_api_key(req.session_id)
    if not api_key:
        raise HTTPException(status_code=400, detail="请先在左上角配置 AI API Key")

    if req.api_key:
        manager.set_api_key(req.session_id, req.api_key)

    # 使用前端传来的 provider 配置，如果没传则报错
    base_url = req.base_url
    model = req.model
    if not base_url or not model:
        raise HTTPException(status_code=400, detail="请在页面左上角选择 AI 模型提供商")

    # 先对大规模 DataFrame 做采样，避免上下文过大
    # Use to_csv with UTF-8 to avoid GBK encoding issues on Windows
    import io
    buf = io.StringIO()
    df.head(20).to_csv(buf, index=False, encoding='utf-8')
    data_preview = buf.getvalue()
    original_rows = len(df)

    # 构建数据摘要
    missing_report = {}
    for col in df.columns:
        miss = df[col].isna().sum()
        if miss > 0:
            missing_report[col] = int(miss)

    dup_count = int(df.duplicated().sum())

    prompt = f"""你是一个专业的数据清洗助手。用户上传了一份数据，需要你帮TA清洗。

【数据信息】
- 行数: {len(df)}
- 列名和类型: {dict(df.dtypes.astype(str))}
- 含缺失值的列: {missing_report if missing_report else '无'}
- 完全重复行: {dup_count} 行
- 前20行预览:
{data_preview}

【用户清洗需求】
{req.request}

【你的任务】
分析数据并根据用户需求，返回一个 JSON 格式的清洗计划。JSON 格式如下：
{{
    "explanation": "用中文简短说明你打算怎么做（2-3句话）",
    "steps": [
        {{"action": "fill_missing", "column": "列名", "method": "fill_mean|fill_median|fill_mode|fill_0|fill_unknown|drop", "reason": "原因"}},
        {{"action": "drop_duplicates", "reason": "原因"}},
        {{"action": "handle_outliers", "column": "列名", "method": "iqr|zscore", "do": "remove|cap", "reason": "原因"}},
        {{"action": "convert_type", "column": "列名", "target_type": "numeric|datetime|string|category", "reason": "原因"}}
    ]
}}

注意：
- 只返回 JSON，不要有任何其他文字
- action 必须是: fill_missing / drop_duplicates / handle_outliers / convert_type 之一
- 如果用户没有明确说明，不要随意删除数据
- 如果清洗步骤不适用于数据（比如没有缺失值），就不要包含那个步骤
- 优先使用 fill_mean（均值填充），如果是分类列则用 fill_mode（众数填充）"""

    import json
    try:
        import openai

        llm_kwargs = {
            "api_key": api_key,
            "base_url": base_url,
            "timeout": 90.0,  # AI 清洗需要 LLM 返回结构化 JSON + 可能含执行步骤说明，90 秒足够
        }
        client = openai.OpenAI(**llm_kwargs)

        def _call_llm():
            return client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=1024,
            )

        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, _call_llm)

        text = response.choices[0].message.content.strip()
        # 提取 JSON
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        plan = json.loads(text)
        explanation = plan.get("explanation", "AI 清洗完成")
        steps = plan.get("steps", [])

        # 执行清洗步骤
        applied = []
        for step in steps:
            action = step.get("action", "")
            column = step.get("column", "")
            reason = step.get("reason", "")

            try:
                manager.push_undo_state(req.session_id)  # 保存撤销点
                df_backup = df.copy()  # 步骤失败时恢复

                if action == "fill_missing" and column:
                    method = step.get("method", "fill_mean")
                    df_before = df.copy()
                    df = handle_missing_values(df, column, method)
                    change = len(df_before) - len(df)
                    desc = f"填充缺失值 [{column}] 方法={method}"
                    if change > 0:
                        desc += f"（删除了 {change} 行）"
                    applied.append({"step": desc, "reason": reason, "success": True})
                    manager.add_cleaning_step(req.session_id, {"type": "ai_fill_missing", "column": column, "method": method, "reason": reason})

                elif action == "drop_duplicates":
                    before = len(df)
                    df, dropped = drop_duplicate_rows(df)
                    applied.append({"step": f"删除重复行（删除了 {dropped} 行）", "reason": reason, "success": True})
                    manager.add_cleaning_step(req.session_id, {"type": "ai_drop_dupes", "dropped": int(dropped), "reason": reason})

                elif action == "handle_outliers" and column:
                    method = step.get("method", "iqr")
                    do = step.get("do", "remove")
                    df = handle_outliers(df, column, method, do)
                    desc = f"处理异常值 [{column}] 检测={method} 操作={do}"
                    applied.append({"step": desc, "reason": reason, "success": True})
                    manager.add_cleaning_step(req.session_id, {"type": "ai_outliers", "column": column, "method": method, "action": do, "reason": reason})

                elif action == "convert_type" and column:
                    target = step.get("target_type", "string")
                    df = convert_column_type(df, column, target)
                    applied.append({"step": f"转换类型 [{column}] → {target}", "reason": reason, "success": True})
                    manager.add_cleaning_step(req.session_id, {"type": "ai_convert_type", "column": column, "target_type": target, "reason": reason})

            except Exception as e:
                df = df_backup  # 恢复备份，防止数据损坏
                applied.append({"step": f"跳过 [{action}] {column}", "reason": f"执行失败: {str(e)}", "success": False})

        # 更新数据
        manager.update_data(req.session_id, df)
        preview = df.head(50).replace({np.nan: None, np.inf: None, -np.inf: None}).to_dict(orient="records")

        return {
            "success": True,
            "explanation": explanation,
            "steps_applied": applied,
            "preview": preview,
            "rows": len(df),
            "rows_change": len(df) - original_rows,
            "columns": list(df.columns),
        }

    except json.JSONDecodeError:
        return {
            "success": True,
            "explanation": text[:500] if len(text) > 500 else text,
            "steps_applied": [],
            "preview": df.head(50).replace({np.nan: None}).to_dict(orient="records"),
            "rows": len(df),
            "rows_change": 0,
            "columns": list(df.columns),
            "note": "AI 返回的建议无法自动执行，已展示给用户参考"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=enhance_ai_error(e, model=req.model or "", base_url=req.base_url or ""))
