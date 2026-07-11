"""
Business Reasoning Pipeline API 路由（⑥ 业务推理管道）

端点：
- POST /reasoning/run — 运行推理管道，返回 ReasoningResult（无需 LLM）

流程：
    saved_packages (dicts) → reconstruct_packages → ReasoningPipeline.run()
    → ReasoningResult → JSON
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.session_manager import manager

router = APIRouter()


class ReasoningRequest(BaseModel):
    session_id: str
    title: Optional[str] = ""


@router.post("/reasoning/run")
async def api_reasoning_run(req: ReasoningRequest):
    """运行业务推理管道

    使用 ReasoningPipeline（Rule Engine → Evidence Engine → LLM Reasoner）
    基于已保存的 AnalysisPackage 进行推理，不依赖 LLM。

    返回 ReasoningResult，包含：
    - root_causes: 根因列表
    - risks: 风险列表
    - opportunities: 增长机会列表
    - executive_summary: 执行摘要
    - narrative: 业务叙事
    - key_findings: 关键发现
    - confidence: 整体置信度
    """
    saved_packages = manager.get_saved_packages(req.session_id)

    if not saved_packages:
        raise HTTPException(
            status_code=400,
            detail="没有已保存的分析结果。请先在分析页面执行分析并保存（点击「保存到仪表盘」），再进行业务推理。"
        )

    try:
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=1) as executor:
            result = await loop.run_in_executor(
                executor,
                _run_reasoning_sync,
                saved_packages,
                req.title or "",
            )
            return {"success": True, "data": result}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"业务推理失败: {str(e)}")


def _run_reasoning_sync(package_dicts, title: str) -> Dict[str, Any]:
    """同步执行推理管道（在 ThreadPoolExecutor 中运行）"""
    from src.utils.package_reconstructor import reconstruct_packages
    from src.reasoning import ReasoningPipeline

    # Step 1: dict → AnalysisPackage
    packages = reconstruct_packages(package_dicts)

    if not packages:
        return {"error": "所有分析包重构失败", "conclusions_count": 0}

    # Step 2: 运行推理管道（无需 LLM，LLMReasoner 自动回退到规则模式）
    pipeline = ReasoningPipeline()
    reasoning_result = pipeline.run(packages, title=title)

    # Step 3: 序列化为 JSON
    return _serialize_reasoning_result(reasoning_result)


def _serialize_reasoning_result(result) -> Dict[str, Any]:
    """将 ReasoningResult 序列化为 API 友好格式"""
    return {
        "id": result.id,
        "title": result.title,
        "created_at": result.created_at,
        # 摘要
        "executive_summary": result.executive_summary,
        "narrative": result.narrative,
        # 关键发现
        "key_findings": result.key_findings,
        # 分类结论
        "root_causes": [c.to_dict() for c in result.root_causes],
        "risks": [c.to_dict() for c in result.risks],
        "opportunities": [c.to_dict() for c in result.opportunities],
        "recommendations": [c.to_dict() for c in result.recommendations],
        "business_impacts": [c.to_dict() for c in result.business_impacts],
        # 统计
        "confidence": result.confidence,
        "packages_consumed": result.packages_consumed,
        "findings_consumed": result.findings_consumed,
        "rules_fired": result.rules_fired,
        "execution_time": result.execution_time,
        # 证据映射（简化：conclusion_id → evidence_count）
        "evidence_summary": {
            cid: len(items) for cid, items in (result.evidence_mapping or {}).items()
        },
    }
