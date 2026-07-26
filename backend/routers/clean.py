"""
数据清洗 API 路由
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import pandas as pd
import numpy as np
import asyncio
import json
import threading
import time as _time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

from backend.services.session_manager import manager
from backend.utils.ai_error import enhance_ai_error
from src.data_cleaner import (
    get_missing_value_report, handle_missing_values,
    detect_data_type_issues, convert_column_type,
    detect_outliers, handle_outliers
)
from src.mapping.column_mapper import map_dataset_columns
from src.merge.dataset_merger import build_analysis_units, AnalysisUnit
from src.utils.json_serializer import sanitize_json

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


# ====== AI 智能清洗 API（合表 → 映射 → 并行统计 → 一次LLM → 按列套用）======

class AICleanRequest(BaseModel):
    session_id: str
    request: str                      # 用户的自然语言清洗需求
    api_key: Optional[str] = ""
    base_url: Optional[str] = None
    model: Optional[str] = None
    dataset_ids: Optional[List[str]] = None   # 省略=处理全部表


# ── 任务状态字典（照搬 analysis 的 _PROCESS_TASKS 范式）──
_CLEAN_TASKS: Dict[str, dict] = {}
_CLEAN_TASKS_LOCK = threading.Lock()
_CLEAN_TTL = 900  # 秒，防内存泄漏


def _cleanup_clean_tasks():
    now = _time.time()
    expired = [tid for tid, t in list(_CLEAN_TASKS.items()) if now - t.get("ts", 0) > _CLEAN_TTL]
    for tid in expired:
        _CLEAN_TASKS.pop(tid, None)


def _resolve_clean_items(session_id: str, dataset_ids: List[str],
                         llm_cfg: Optional[dict] = None) -> List[dict]:
    """载入各表 df → 研判合并 → 注册宽表 → 产出清洗处理项列表。

    完全镜像 analysis._resolve_process_items 的「合表范式」，覆盖
    「部分表能合、部分合不了」的混合场景，每个单元后续各自清洗。
    """
    session = manager.get_session(session_id)
    file_names: Dict[str, str] = {}
    loaded = []
    merged_existing = []
    for did in dataset_ids:
        df = manager.get_dataset_df(session_id, did)
        if df is None:
            continue
        dsobj = session.datasets.get(did) if session else None
        file_names[did] = dsobj.file_name if dsobj else did
        if dsobj is not None and getattr(dsobj, "is_merged", False):
            merged_existing.append(did)
            continue
        loaded.append((did, df))
    if not loaded and not merged_existing:
        return []
    if merged_existing:
        merged_sources = set()
        for mdid in merged_existing:
            mobj = session.datasets.get(mdid) if session else None
            if mobj is not None:
                merged_sources.update(getattr(mobj, "sources", []) or [])
        items = [{"kind": "single", "dataset_id": did} for did in merged_existing]
        for did, _ in loaded:
            if did in merged_sources:
                items.append({"kind": "single", "dataset_id": did})
        fresh = [(did, df) for did, df in loaded if did not in merged_sources]
        if fresh:
            try:
                fresh_units = build_analysis_units(fresh, file_names, llm_cfg)
            except Exception:
                fresh_units = [AnalysisUnit(kind="single", dataset_id=d, file_name=file_names.get(d, d)) for d, _ in fresh]
            for unit in fresh_units:
                if unit.kind == "single":
                    items.append({"kind": "single", "dataset_id": unit.dataset_id})
                else:
                    try:
                        new_did = manager.add_merged_dataset(
                            session_id, unit.df, unit.sources, unit.keys,
                            file_name=unit.file_name or "合并宽表")
                        items.append({"kind": "merged", "dataset_id": new_did,
                                      "sources": unit.sources, "merge_keys": unit.keys})
                    except Exception:
                        for sd in unit.sources:
                            items.append({"kind": "single", "dataset_id": sd})
        return items
    try:
        units = build_analysis_units(loaded, file_names, llm_cfg)
    except Exception:
        units = [AnalysisUnit(kind="single", dataset_id=d, file_name=file_names.get(d, d)) for d, _ in loaded]
    items = []
    for unit in units:
        if unit.kind == "single":
            items.append({"kind": "single", "dataset_id": unit.dataset_id})
        else:
            try:
                new_did = manager.add_merged_dataset(
                    session_id, unit.df, unit.sources, unit.keys,
                    file_name=unit.file_name or "合并宽表")
                items.append({"kind": "merged", "dataset_id": new_did,
                              "sources": unit.sources, "merge_keys": unit.keys})
            except Exception:
                for sd in unit.sources:
                    items.append({"kind": "single", "dataset_id": sd})
    return items


def _compute_stats(df: pd.DataFrame) -> dict:
    """对单张表算统计（本地、无LLM）：行数 / 类型 / 缺失 / 前20行。

    供 ThreadPoolExecutor 并行调用。
    """
    import io
    missing_report = {}
    for col in df.columns:
        miss = int(df[col].isna().sum())
        if miss > 0:
            missing_report[str(col)] = miss
    buf = io.StringIO()
    df.head(20).to_csv(buf, index=False, encoding="utf-8")
    data_review = buf.getvalue()
    return {
        "rows": int(len(df)),
        "dtypes": {str(c): str(t) for c, t in df.dtypes.astype(str).items()},
        "missing": missing_report,
        "sample": data_review,
    }


def _build_ai_clean_prompt(all_stats: Dict[str, dict], request: str) -> str:
    """聚合所有单元的统计信息，构建一次 LLM 的提示词。"""
    blocks = []
    for did, st in all_stats.items():
        blocks.append(
            f"【表 {did}】\n"
            f"- 行数: {st['rows']}\n"
            f"- 列名与类型: {st['dtypes']}\n"
            f"- 含缺失值的列: {st['missing'] if st['missing'] else '无'}\n"
            f"- 前20行:\n{st['sample']}"
        )
    stats_text = "\n\n".join(blocks)
    return f"""你是一个专业的数据清洗助手。用户上传了多张数据表（已统一为标准列名），需要你给出每列的清洗建议。

【全部表的统计信息】
{stats_text}

【用户清洗需求】
{request}

【你的任务】
分析数据并根据用户需求，返回一份 JSON 格式的清洗计划。要求：
- 以「标准列名」为键，给出每一列的清洗建议（不区分它属于哪张表，同名列视为同一含义）；
- 优先使用 fill_mean（均值填充），分类列用 fill_mode（众数填充）；
- JSON 格式如下：
{{
    "explanation": "用中文简短说明整体清洗思路（2-3句话）",
    "steps": [
        {{"column": "标准列名", "action": "fill_missing", "method": "fill_mean|fill_median|fill_mode|fill_0|fill_unknown|drop", "reason": "原因"}},
        {{"column": "标准列名", "action": "handle_outliers", "method": "iqr|zscore", "do": "remove|cap", "reason": "原因"}},
        {{"column": "标准列名", "action": "convert_type", "target_type": "numeric|datetime|string|category", "reason": "原因"}}
    ]
}}

注意：
- 只返回 JSON，不要有任何其他文字
- action 必须是 fill_missing / handle_outliers / convert_type 之一
- 严禁删除重复行（drop_duplicates），本系统不支持去重操作
- 如果用户没有明确说明，不要随意删除数据
- 如果某列不需要清洗（如没有缺失值、类型无误、无异常），就不要包含该列"""


def _call_llm_once(api_key: str, base_url: str, model: str, prompt: str) -> dict:
    """同步调用一次 LLM（openai SDK），解析返回 JSON 清洗计划。"""
    import openai
    client = openai.OpenAI(api_key=api_key, base_url=base_url, timeout=90.0)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=2048,
    )
    text = resp.choices[0].message.content.strip()
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)


def _apply_ai_clean_steps(session_id: str, dataset_id: str, mapped_df: pd.DataFrame, recommend: Dict[str, dict]):
    """按列套用：recommend 为 {{列名: {{action, method/target_type/do, reason}}}}。

    遍历 mapped_df 每一列，仅当该列在 recommend 中才清洗该列。
    返回 (清洗后df, 已执行步骤列表)。
    """
    df = mapped_df.copy()
    applied = []
    for col, spec in recommend.items():
        if col not in df.columns:
            continue
        action = spec.get("action", "")
        reason = spec.get("reason", "")
        backup = df.copy()
        try:
            if action == "fill_missing":
                method = spec.get("method", "fill_mean")
                df = handle_missing_values(df, col, method)
                applied.append({"step": f"填充缺失值 [{col}] 方法={method}", "reason": reason, "success": True})
                manager.add_cleaning_step(session_id, {"type": "ai_fill_missing", "dataset_id": dataset_id, "column": col, "method": method, "reason": reason})
            elif action == "handle_outliers":
                method = spec.get("method", "iqr")
                do = spec.get("do", "remove")
                df = handle_outliers(df, col, method, do)
                applied.append({"step": f"处理异常值 [{col}] 检测={method} 操作={do}", "reason": reason, "success": True})
                manager.add_cleaning_step(session_id, {"type": "ai_outliers", "dataset_id": dataset_id, "column": col, "method": method, "do": do, "reason": reason})
            elif action == "convert_type":
                target = spec.get("target_type", "string")
                df = convert_column_type(df, col, target)
                applied.append({"step": f"转换类型 [{col}] → {target}", "reason": reason, "success": True})
                manager.add_cleaning_step(session_id, {"type": "ai_convert_type", "dataset_id": dataset_id, "column": col, "target_type": target, "reason": reason})
            else:
                applied.append({"step": f"跳过未知动作 [{action}] {col}", "reason": "AI 返回了不支持的清洗动作", "success": False})
        except Exception as e:
            df = backup
            applied.append({"step": f"跳过 [{action}] {col}", "reason": f"执行失败: {str(e)}", "success": False})
    return df, applied


def _run_clean_finalize(task_id, session_id, process_items, datasets_status, total, explanation):
    """收尾：删除 merged 来源原表（合表语义决定，与清洗成败无关），回写整体状态。"""
    try:
        for it in process_items:
            if it["kind"] == "merged":
                for sd in it.get("sources", []):
                    try:
                        manager.remove_dataset(session_id, sd)
                    except Exception:
                        pass
    except Exception:
        pass
    with _CLEAN_TASKS_LOCK:
        done = sum(1 for v in datasets_status.values() if v.get("status") == "done")
        # 全部成功才 done；全失败 error；部分成功 partial（避免误报「完成」掩盖失败）
        if done == total:
            overall = "done"
        elif done == 0:
            overall = "error"
        else:
            overall = "partial"
        _CLEAN_TASKS[task_id].update({
            "status": overall,
            "total": total,
            "completed": done,
            "datasets": datasets_status,
            "ts": _time.time(),
        })


def _run_clean_task(task_id: str, session_id: str, req: AICleanRequest, process_items: List[dict]):
    """后台任务：合表 → 映射 → 并行统计 → 一次LLM → 按列套用 → 删来源原表。"""
    session = manager.get_session(session_id)
    if session is None:
        with _CLEAN_TASKS_LOCK:
            _CLEAN_TASKS[task_id].update({"status": "error", "error": "会话不存在", "ts": _time.time()})
        return

    total = len(process_items)
    datasets_status: Dict[str, dict] = {}
    for it in process_items:
        extra = {"kind": it["kind"]}
        if it["kind"] == "merged":
            extra["sources"] = it.get("sources", [])
            extra["merge_keys"] = it.get("merge_keys", [])
        datasets_status[it["dataset_id"]] = {"status": "pending", **extra}

    llm_key = req.api_key or manager.get_api_key(session_id)
    llm_base = req.base_url
    llm_model = req.model

    # 阶段1：逐单元列名映射（独立步骤；仅当配置了 API Key 时让映射走 LLM 兜底）
    mapped: Dict[str, pd.DataFrame] = {}
    for it in process_items:
        did = it["dataset_id"]
        try:
            df0 = manager.get_dataset_df(session_id, did)
            if df0 is None:
                datasets_status[did].update({"status": "error", "error": "数据集读取失败"})
                continue
            datasets_status[did].update({"status": "running"})
            _ds = session.datasets.get(did) if session else None
            _fname = _ds.file_name if _ds else None
            llm_cfg = {"api_key": llm_key, "base_url": llm_base, "model": llm_model} if llm_key else None
            mapped_df = map_dataset_columns(session_id, did, df0, llm_cfg,
                                           file_name=_fname)
            mapped[did] = mapped_df
        except Exception as e:
            datasets_status[did].update({"status": "error", "error": f"列名映射失败: {e}"})

    valid_ids = [d for d in mapped if datasets_status[d].get("status") != "error"]

    # 阶段2：并行算统计（max_workers=2）
    stats: Dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=2) as ex:
        fut_map = {ex.submit(_compute_stats, mapped[d]): d for d in valid_ids}
        for fut in as_completed(fut_map):
            d = fut_map[fut]
            try:
                stats[d] = fut.result()
            except Exception as e:
                datasets_status[d].update({"status": "error", "error": f"统计失败: {e}"})

    if not stats:
        with _CLEAN_TASKS_LOCK:
            for d in list(datasets_status.keys()):
                if datasets_status[d].get("status") in ("pending", "running"):
                    datasets_status[d].update({"status": "error", "error": "所有表的映射/统计均失败"})
            _CLEAN_TASKS[task_id].update({"status": "error", "error": "所有表的映射/统计均失败", "total": total, "completed": 0, "datasets": datasets_status, "ts": _time.time()})
        return

    # 阶段3：聚合 + 一次 LLM
    if not llm_key:
        with _CLEAN_TASKS_LOCK:
            for d in list(datasets_status.keys()):
                if datasets_status[d].get("status") in ("pending", "running"):
                    datasets_status[d].update({"status": "error", "error": "缺少 API Key"})
            _CLEAN_TASKS[task_id].update({"status": "error", "error": "请先配置 API Key", "total": total, "completed": 0, "datasets": datasets_status, "ts": _time.time()})
        return
    if not llm_base or not llm_model:
        with _CLEAN_TASKS_LOCK:
            for d in list(datasets_status.keys()):
                if datasets_status[d].get("status") in ("pending", "running"):
                    datasets_status[d].update({"status": "error", "error": "未选择 AI 模型"})
            _CLEAN_TASKS[task_id].update({"status": "error", "error": "请在页面左上角选择 AI 模型提供商", "total": total, "completed": 0, "datasets": datasets_status, "ts": _time.time()})
        return

    try:
        prompt = _build_ai_clean_prompt(stats, req.request)
        plan = _call_llm_once(llm_key, llm_base, llm_model, prompt)
        explanation = plan.get("explanation", "AI 清洗完成")
        recommend: Dict[str, dict] = {}
        for s in plan.get("steps", []):
            c = s.get("column")
            if c:
                recommend[c] = s
    except json.JSONDecodeError:
        # LLM 返回无法解析：有效单元标 done（仅展示参考），仍走收尾删源表
        for d in valid_ids:
            datasets_status[d].update({"status": "done", "explanation": "AI 返回的建议无法自动执行", "steps_applied": [], "rows_change": 0, "note": "AI 返回的建议无法自动执行，已展示给用户参考"})
        _run_clean_finalize(task_id, session_id, process_items, datasets_status, total, None)
        return
    except Exception as e:
        with _CLEAN_TASKS_LOCK:
            for d in list(datasets_status.keys()):
                if datasets_status[d].get("status") in ("pending", "running"):
                    datasets_status[d].update({"status": "error", "error": f"AI 调用失败: {e}"})
            _CLEAN_TASKS[task_id].update({"status": "error", "error": f"AI 调用失败: {e}", "total": total, "completed": 0, "datasets": datasets_status, "ts": _time.time()})
        return

    # 阶段4：按列套用 + 写回 + 标记
    for it in process_items:
        did = it["dataset_id"]
        if did not in mapped:
            continue
        if datasets_status[did].get("status") == "error":
            continue
        try:
            new_df, applied = _apply_ai_clean_steps(session_id, did, mapped[did], recommend)
            rows_change = len(new_df) - len(mapped[did])
            manager.update_dataset_df(session_id, did, new_df)
            ds = session.datasets.get(did)
            if ds is not None:
                ds.cleaned_mapped = True
            datasets_status[did].update({
                "status": "done",
                "explanation": explanation,
                "steps_applied": applied,
                "rows_change": rows_change,
            })
        except Exception as e:
            datasets_status[did].update({"status": "error", "error": f"套用失败: {e}"})

    _run_clean_finalize(task_id, session_id, process_items, datasets_status, total, explanation)


@router.post("/clean/ai-clean")
async def api_ai_clean(req: AICleanRequest):
    """AI 智能清洗（异步）：先合表 → 映射 → 并行统计 → 一次LLM → 按列套用。

    提交即返回 task_id，前端轮询 /clean/ai-clean/status/{task_id} 拿逐单元进度。
    """
    session = manager.get_session(req.session_id)
    if session is None or not session.datasets:
        raise HTTPException(status_code=404, detail="会话无数据集，请先上传")
    target = (req.dataset_ids if req.dataset_ids else list(session.datasets.keys()))
    target = [d for d in target if d in session.datasets]
    if not target:
        raise HTTPException(status_code=400, detail="指定的数据集不存在")
    llm_cfg = {
        "api_key": req.api_key or manager.get_api_key(req.session_id),
        "base_url": req.base_url,
        "model": req.model,
    }
    try:
        process_items = _resolve_clean_items(req.session_id, target, llm_cfg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"合表失败: {e}")
    if not process_items:
        raise HTTPException(status_code=400, detail="无可用数据集")

    task_id = str(uuid.uuid4())
    initial: Dict[str, dict] = {}
    for it in process_items:
        extra = {"kind": it["kind"]}
        if it["kind"] == "merged":
            extra["sources"] = it.get("sources", [])
            extra["merge_keys"] = it.get("merge_keys", [])
        initial[it["dataset_id"]] = {"status": "pending", **extra}
    with _CLEAN_TASKS_LOCK:
        _CLEAN_TASKS[task_id] = {"status": "running", "total": len(process_items), "completed": 0, "datasets": initial, "ts": _time.time()}
    threading.Thread(target=_run_clean_task, args=(task_id, req.session_id, req, process_items), daemon=True).start()
    return {"task_id": task_id, "total": len(process_items)}


@router.get("/clean/ai-clean/status/{task_id}")
async def api_ai_clean_status(task_id: str):
    with _CLEAN_TASKS_LOCK:
        _cleanup_clean_tasks()
        task = _CLEAN_TASKS.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="任务不存在或已过期")
        return sanitize_json(dict(task))
