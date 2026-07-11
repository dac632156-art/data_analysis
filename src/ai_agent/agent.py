"""
AI Agent 核心 - 使用原生 DeepSeek API 实现函数调用
不依赖 LangChain，更简单、更可控
"""
import pandas as pd
import json
import openai
import threading
from typing import List, Dict, Any, Optional
from src.ai_agent.prompts import (
    SYSTEM_PROMPT, REPORT_SYSTEM_PROMPT, REPORT_USER_PROMPT_TEMPLATE,
    INSIGHTS_SYSTEM_PROMPT, INSIGHTS_USER_PROMPT_TEMPLATE,
    REPORT_BI_SYSTEM_PROMPT, REPORT_BI_USER_PROMPT_TEMPLATE,
)
from src.report_analyzer import run_full_analysis
from src.report_builder import ReportBuilder
from src.report_builder import SECTION_DISPLAY_NAME

class DataAnalysisAgent:
    """数据分析 AI Agent（原生 DeepSeek API 实现）"""

    def __init__(self, api_key: str, model: str = "deepseek-chat", base_url: str = "https://api.deepseek.com"):
        """初始化 Agent"""
        self.api_key = api_key
        self.model = model
        self.base_url = base_url

        # 初始化 OpenAI 客户端
        # 报告生成最长 180s；openai SDK 默认 max_retries=2，一旦 AI 服务慢/不可达，
        # 单次超时(180s)后会再重试 2 次，最坏 180×3=540s，远超前端 300s 超时 →
        # 前端先 ECONNABORTED 断开，后端还在重试，用户永远收不到降级报告。
        # 故关闭 SDK 重试（max_retries=0）：超时即抛错 → 立即走 fallback 降级报告，
        # 保证后端在 180s 内返回 200，前端不会再超时。
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=240.0,
            max_retries=0,
        )

    def _get_data_summary(self, df: pd.DataFrame) -> str:
        """生成数据摘要（用于传给 AI）"""
        numeric_stats = ""
        try:
            if len(df.select_dtypes(include=['number']).columns) > 0:
                import io as _io
                buf = _io.StringIO()
                df.describe().to_csv(buf, encoding='utf-8')
                numeric_stats = buf.getvalue()
        except Exception:
            numeric_stats = "(无法计算描述性统计)"

        summary = f"""
数据规模：{len(df)} 行 x {len(df.columns)} 列
列名：{list(df.columns)}
数据类型：{dict(zip(df.columns, [str(dtype) for dtype in df.dtypes]))}
缺失值：{df.isnull().sum().to_dict()}
数值列统计：
{numeric_stats}
"""
        return summary

    def _execute_code(self, code: str, df: pd.DataFrame, timeout_sec: int = 20) -> str:
        """执行 Python 代码分析数据（带超时保护，防止死循环卡死整个服务）"""
        result_container = {"result": None, "error": None, "done": False}

        def _run():
            try:
                # 使用 df 的副本，避免修改原始数据
                local_vars = {"df": df.copy(), "pd": pd, "np": __import__('numpy')}
                exec_globals = {}
                exec(code, exec_globals, local_vars)

                if 'result' in local_vars:
                    result_container["result"] = str(local_vars['result'])
                else:
                    result_container["result"] = "代码执行成功，但未返回结果。"
            except Exception as e:
                result_container["error"] = f"代码执行出错：{str(e)}"
            finally:
                result_container["done"] = True

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        thread.join(timeout=timeout_sec)

        if not result_container["done"]:
            return f"[WARN] 代码执行超时（>{timeout_sec}秒），已跳过。"
        if result_container["error"]:
            return result_container["error"]
        return result_container["result"]

    def analyze(self, user_query: str, df: pd.DataFrame) -> str:
        """分析用户问题，返回 AI 回答
        
        当用户询问分析/图表时，返回结构化 JSON（同 generate_insights 格式），
        包含 insights 和 intents，以便前端生成可执行的分析计划。
        """
        try:
            data_summary = self._get_data_summary(df)
            
            # 判断是否为分析/图表相关请求
            is_analysis_request = any(kw in user_query for kw in 
                ['图表', '建议', '推荐', '分析方向', '做什么', '画什么', '地图', '省份', 
                 '分析', '可视化', '生成', '统计', '对比', '趋势', '分布'])
            
            if is_analysis_request:
                # 分析请求：直接调用 generate_insights 返回结构化 JSON
                return self.generate_insights(df, user_query)
            
            # 通用对话：直接回答
            _chart_hint = (
                '\n\n如果用户询问分析方向或图表建议，请在\u201c分析建议\u201d章节中，'
                '每条建议包含 (X:列名, Y:列名) 格式标注，并紧跟\u201c\u2192 图表类型\u201d说明。'
                '示例格式：\n'
                "1. 各省份销售金额的地区分布 → 3D地图（X:省份, Y:销售金额）\n"
                "   + 汇总表格（行:省份, 列:销售金额）\n"
                "2. 各产品类别的销售对比 → 柱状图（X:产品类别, Y:销售金额）\n"
                "   + 排序表格（排序:销售金额, 降序）\n"
                "请使用数据中真实的列名，不要虚构不存在的列。"
            ) if any(kw in user_query for kw in ['图表', '建议', '推荐', '分析方向', '做什么', '画什么', '地图', '省份']) else ""
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"用户问题：{user_query}\n\n当前数据摘要：\n{data_summary}\n\n请直接用中文回答用户问题。如果需要计算，在回答中说明分析思路即可，不要生成 Python 代码。{_chart_hint}"}
            ]

            # 调用 API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
                max_tokens=2048,
                timeout=60,
            )

            ai_response = response.choices[0].message.content

            # 仅在确实需要执行代码时才执行（带超时保护）
            if "```python" in ai_response or "```py" in ai_response:
                code_start = ai_response.find("```python")
                if code_start == -1:
                    code_start = ai_response.find("```py")

                code_end = ai_response.find("```", code_start + 10)
                if code_start != -1 and code_end != -1:
                    code = ai_response[code_start:code_end].replace("```python", "").replace("```py", "").replace("```", "").strip()

                    # 执行代码（20 秒超时）
                    execution_result = self._execute_code(code, df)

                    follow_up_messages = messages + [
                        {"role": "assistant", "content": ai_response},
                        {"role": "user", "content": f"代码执行结果：\n{execution_result}\n\n请根据这个结果，用中文总结分析结论。"}
                    ]

                    follow_up_response = self.client.chat.completions.create(
                        model=self.model,
                        messages=follow_up_messages,
                        temperature=0.3,
                        max_tokens=2048,
                        timeout=60,
                    )

                    return follow_up_response.choices[0].message.content

            return ai_response

        except Exception as e:
            return f"AI 分析出错：{str(e)}\n\n请检查 API Key 是否正确，或稍后重试。"

    def generate_insights(self, df: pd.DataFrame, user_query: str = "") -> str:
        """自动生成数据洞察报告 + 分析意图列表（JSON 格式）
        
        使用 INSIGHTS_SYSTEM_PROMPT + INSIGHTS_USER_PROMPT_TEMPLATE，
        输出 JSON：{insights: Markdown, intents: [{business_question, analysis_goal, priority, reason}]}
        
        参数：
            user_query: 用户的具体分析问题（可选），如果提供，会在提示词中加入该问题
        """
        try:
            # ============================================
            # 阶段 1-3：Python 精确统计分析
            # ============================================
            analysis_data = run_full_analysis(df, None)
            fields = analysis_data["phase_1_fields"]
            stats = analysis_data["phase_3_stats"]
            charts = analysis_data["phase_2_charts"]

            # ---- 构建数据摘要（供 LLM 使用）----
            data_summary = _build_insights_data_summary(df, fields, stats, charts)

            # ============================================
            # 阶段 4-5：AI 生成洞察（Structured Output JSON）
            # ============================================
            query_context = f"\n\n用户具体问题：{user_query}\n请重点围绕用户问题生成相关的分析意图。" if user_query else ""
            user_prompt = INSIGHTS_USER_PROMPT_TEMPLATE.format(
                data_summary=data_summary,
            ) + query_context

            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": INSIGHTS_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.0,
                    max_tokens=4096,
                    timeout=120,
                )

                ai_text = response.choices[0].message.content or ""
                return ai_text  # 返回 JSON 字符串，由 insights.py 解析

            except Exception as e:
                # AI 调用失败时，降级为纯统计洞察
                import json as _json
                fallback = _build_fallback_insights(df, fields, stats, charts, str(e))
                return _json.dumps({"insights": fallback, "intents": []})

        except Exception as e:
            import json as _json
            return _json.dumps({"insights": f"生成洞察报告出错：{str(e)}", "intents": []})

    def generate_report(
        self,
        df: pd.DataFrame,
        saved_charts: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """生成完整的结构化数据分析报告（五阶段流水线）

        阶段1-3由 report_analyzer.run_full_analysis() 完成（pandas 精确计算）
        阶段4-5由 LLM 完成（洞察生成 + 报告撰写）

        返回 Dict 包含 sections 列表，每个 section 有 type / title / content / insights
        """
        import json as _json
        import traceback as _tb

        try:
            # ---- 阶段 1-3：Python 统计分析 ----
            analysis_data = run_full_analysis(df, saved_charts)
            fields = analysis_data["phase_1_fields"]
            stats = analysis_data["phase_3_stats"]
            charts = analysis_data["phase_2_charts"]

            # ---- 格式化统计结果为可读文本 ----
            overview_text = _format_overview(stats["overview"])

            basic_stats_text = _format_basic_stats(stats["basic_stats"])

            trend_text = _format_trend(stats["trend_analysis"])

            yoy_text = _format_yoy(stats["yoy_mom"])

            top_text = _format_top(stats["top_analysis"])

            structure_text = _format_structure(stats["structure_analysis"])

            anomaly_text = _format_anomalies(stats["anomaly_analysis"])

            charts_text = "\n".join(
                f"- [{c['type']}] {c['title']}（X: {c.get('x','')}, Y: {str(c.get('y',''))}）→ {c.get('reason','')}"
                for c in charts
            ) if charts else "（无推荐图表）"

            # ---- 阶段 4-5：AI 生成洞察和报告 ----
            user_prompt = REPORT_USER_PROMPT_TEMPLATE.format(
                data_overview=overview_text,
                time_dimension=fields.get("time_dimension") or "无",
                metrics=", ".join(fields.get("metrics", [])) or "无",
                dimensions=", ".join(fields.get("dimensions", [])) or "无",
                basic_stats=basic_stats_text,
                trend_analysis=trend_text,
                yoy_mom=yoy_text,
                top_analysis=top_text,
                structure_analysis=structure_text,
                anomaly_analysis=anomaly_text,
                planned_charts=charts_text,
            )

            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": REPORT_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.4,
                    max_tokens=8192,
                    timeout=120,
                )

                ai_text = response.choices[0].message.content or ""
                # debug: AI text length logged via logging

                # 尝试解析 JSON
                sections = _parse_report_json(ai_text)
                # 归一化 type 名（_fill_missing_sections 可能注入了新版名）→ 旧版名，确保 _bind_core_charts 能匹配
                sections = _normalize_section_types(sections)
                # debug: parsed sections logged via logging

                # 自动绑定保底图表到对应 section（AI 漏填 chartIndex 时兜底）
                sections = _bind_core_charts_to_sections(sections, charts)

                return {
                    "success": True,
                    "sections": sections,
                    "raw_analysis": analysis_data,
                }

            except Exception as e:
                # 降级：返回纯统计分析数据（不带 AI 洞察）
                return {
                    "success": True,
                    "sections": _normalize_section_types(_build_fallback_sections(analysis_data)),
                    "raw_analysis": analysis_data,
                    "warning": f"AI 生成洞察失败（{str(e)}），仅返回统计数据",
                }

        except Exception as e:
            # 阶段 1-3 或格式化过程出错，打印完整错误到控制台
            import logging as _logging; _logging.getLogger("agent").error(f"generate_report: {e}")
            _tb.print_exc()

    # ===== V3：基于 AnalysisPackage 的报告生成 =====
    def generate_report_from_packages(
        self,
        packages: List[Dict[str, Any]],
        data_profile: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """基于已保存的 AnalysisPackage 生成 AI 分析报告

        Report AI 的唯一职责是读取 AnalysisPackage 并组织语言生成专业报告。
        不再重新分析数据，不访问原始 DataFrame。
        """
        import json as _json
        import traceback as _tb

        packages = packages or []

        if not packages:
            return {
                "success": True,
                "sections": _normalize_section_types([{
                    "type": "executive_summary",
                    "title": "执行摘要",
                    "content": "当前没有已保存的分析结果。请先在分析页面执行分析并保存，再生成报告。",
                }]),
                "packages_used": 0,
            }

        builder = ReportBuilder()
        report_input = builder.build_input(packages, data_profile)

        if not report_input["available_sections"]:
            return {
                "success": True,
                "sections": _normalize_section_types([{
                    "type": "executive_summary",
                    "title": "执行摘要",
                    "content": "已保存的分析包中没有可报告的数据。",
                }]),
                "packages_used": len(packages),
            }

        user_prompt = REPORT_BI_USER_PROMPT_TEMPLATE.format(
            packages_summary=report_input["packages_summary"],
            prompt_text=report_input["prompt_text"],
        )

        warning: Optional[str] = None
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": REPORT_BI_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.4,
                max_tokens=8192,  # 保持 8192，通过精简输入 prompt 提速
                timeout=240,  # 与 client 级一致；SDK 重试已关，最坏 240s 即走 fallback
            )

            ai_text = response.choices[0].message.content or ""
            sections = _parse_report_json(ai_text)

            # 绑定图表信息到 sections
            sections = _bind_package_charts_to_sections(sections, report_input["sections_data"])

            # 归一化 type 名 → 前端兼容格式
            sections = _normalize_section_types(sections)

            return {
                "success": True,
                "sections": sections,
                "packages_used": len(packages),
            }

        except Exception as e:
            import logging as _logging; _logging.getLogger("agent").warning(f"report fallback: {e}")
            _tb.print_exc()
            warning = f"AI 报告生成失败（{str(e)}），以下为已有分析数据的直接汇总。"

            try:
                fallback_sections = _build_fallback_from_packages(packages, report_input)
                # 归一化 type 名 → 前端兼容格式
                fallback_sections = _normalize_section_types(fallback_sections)
                return {
                    "success": True,
                    "sections": fallback_sections,
                    "packages_used": len(packages),
                    "warning": warning,
                }
            except Exception as fb_e:
                return {
                    "success": False,
                    "sections": [],
                    "packages_used": len(packages),
                    "warning": f"报告生成失败：{str(fb_e)}",
                }



# ============================================================
# 报告格式化辅助函数
# ============================================================

def _format_overview(ov: Dict[str, Any]) -> str:
    """格式化数据概览"""
    return (
        f"数据行数：{ov['total_rows']:,} 行\n"
        f"数据列数：{ov['total_cols']} 列\n"
        f"列名：{', '.join(ov['column_names'][:15])}"
        f"{'...' if len(ov['column_names']) > 15 else ''}\n"
        f"缺失值：{ov['missing_total']} 个（{ov['missing_rate']}%）\n"
        f"重复行：{ov['duplicate_rows']} 行\n"
        f"数值列：{ov['numeric_columns']} 个，分类列：{ov['categorical_columns']} 个\n"
        f"内存占用：{ov['memory_mb']} MB"
    )


def _format_basic_stats(bs: Dict[str, Any]) -> str:
    """格式化基础统计"""
    lines = []
    for col, s in bs.items():
        lines.append(
            f"【{col}】 总值={s['total']:,.2f}  均值={s['mean']:,.2f}  "
            f"中位数={s['median']:,.2f}  最大值={s['max']:,.2f}  "
            f"最小值={s['min']:,.2f}  标准差={s['std']:,.2f}  样本数={s['count']}"
        )
    return "\n".join(lines) if lines else "（无数值指标）"


def _format_trend(tr: Dict[str, Any]) -> str:
    """格式化趋势分析"""
    lines = []
    for col, t in tr.items():
        g = t.get("overall_growth_rate")
        g_str = f"{g:+.2f}%" if g is not None else "N/A"
        lines.append(
            f"【{col}】 周期数={t['period_count']}  "
            f"首值={t['first_value']:,.2f} → 末值={t['last_value']:,.2f}  "
            f"整体增长率={g_str}  方向={t['direction']}  "
            f"波动率(CV)={t['volatility_cv']:.2f}%  "
            f"最大单次增长={t['max_single_growth']:+.2f}%  "
            f"最大单次下降={t['max_single_decline']:+.2f}%  "
            f"最长连续涨={t['consecutive_up']}次  最长连续跌={t['consecutive_down']}次"
        )
    return "\n".join(lines) if lines else "（无趋势数据）"


def _format_yoy(ym: Dict[str, Any]) -> str:
    """格式化同环比"""
    if not ym.get("has_yoy") and not ym.get("computed"):
        return "（无同环比数据，可能缺少时间维度或年份数据不足）"
    lines = []
    for d in ym.get("details", []):
        lines.append(
            f"【{d['title']}】 指标列={d['value_column']}  "
            f"当前年={d['current_year']}  对比年={d['previous_year']}  "
            f"数据行数={d['row_count']}  含同比={d['has_yoy']}"
        )
    if ym.get("computed"):
        c = ym["computed"]
        lines.append(f"【{c['metric']}】 总计={c['total']:,.2f}  均值={c['mean']:,.2f} ({c['note']})")
    return "\n".join(lines)


def _format_top(ta: Dict[str, Any]) -> str:
    """格式化 Top/Bottom 分析"""
    lines = []
    for key, t in ta.items():
        top_items = ", ".join(f"{k}:{v:,.2f}" for k, v in t.get("top5", {}).items())
        bottom_items = ", ".join(f"{k}:{v:,.2f}" for k, v in t.get("bottom5", {}).items())
        lines.append(
            f"【{key}】 总分类={t['total_categories']}  "
            f"Top1={t['max_category']}({t['max_value']:,.2f})  "
            f"Bottom1={t['min_category']}({t['min_value']:,.2f})  "
            f"Top3集中度={t['top3_concentration']:.1f}%  "
            f"Top5: {top_items}  "
            f"Bottom5: {bottom_items}"
        )
    return "\n".join(lines) if lines else "（无分类维度）"


def _format_structure(sd: Dict[str, Any]) -> str:
    """格式化结构分析"""
    lines = []
    for key, s in sd.items():
        dist = ", ".join(f"{k}:{int(v['share'])}%" for k, v in list(s.get("distribution", {}).items())[:5])
        lines.append(
            f"【{key}】 分类数={s['category_count']}  "
            f"Top3占比={s['top3_share']:.1f}%  "
            f"分布: {dist}"
        )
    return "\n".join(lines) if lines else "（无分类维度）"


def _format_anomalies(al: List[Dict[str, Any]]) -> str:
    """格式化异常分析"""
    if not al:
        return "（未检测到显著异常）"
    lines = []
    for a in al:
        t = a.get("type", "")
        if t == "离群点":
            details = ", ".join(f"{k}(值={v['value']}, Z={v['z_score']})" for k, v in a.get("details", {}).items())
            lines.append(f"【{t}】指标={a.get('metric','')}  规则={a.get('rule','')}  明细: {details}")
        elif t == "IQR异常":
            lines.append(
                f"【{t}】指标={a.get('metric','')}  规则={a.get('rule','')}  "
                f"异常数={a.get('count',0)}/{a.get('total',0)}({a.get('anomaly_rate',0)}%)"
            )
        elif t == "占比异常":
            lines.append(f"【{t}】维度={a.get('dimension','')}  指标={a.get('metric','')}  警告={a.get('warning','')}")
    return "\n".join(lines) if lines else "（未检测到显著异常）"



def _fill_missing_sections(sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """补全缺失的 report sections，确保报告结构完整

    注意：required_types 必须与 REPORT_BI_SYSTEM_PROMPT 中定义的 section type 枚举保持一致，
    否则会把 AI 已经正常输出的 section 误判为"缺失"，注入"数据不足"占位。
    """
    existing_types = {s.get("type", "") for s in sections}
    # 与 prompts.py 中 REPORT_BI_SYSTEM_PROMPT 的 section type 枚举对齐
    required_types = [
        "executive_summary", "data_overview", "trend_analysis", "ranking_analysis",
        "structure_analysis", "concentration_analysis", "distribution_analysis",
        "correlation_analysis", "comparison_analysis", "geo_analysis",
        "retention_analysis", "anomaly_analysis", "proportion_analysis",
        "risk_analysis", "management_suggestions", "conclusion",
    ]

    new_sections = []
    for rt in required_types:
        if rt in existing_types:
            continue
        # 缺失章节：插入明确的"未提供"占位，而不是误导性的"数据不足"
        if rt == "executive_summary":
            new_sections.append({
                "type": "executive_summary", "title": "执行摘要",
                "content": "AI 未生成执行摘要。",
            })
        elif rt == "data_overview":
            new_sections.append({
                "type": "data_overview", "title": "数据概览",
                "content": "AI 未生成数据概览。",
            })
        elif rt == "conclusion":
            new_sections.append({
                "type": "conclusion", "title": "总结",
                "insights": [{"analysis": "AI 未生成总结。"}],
            })
        elif rt == "management_suggestions":
            new_sections.append({
                "type": "management_suggestions", "title": "管理建议",
                "insights": [{"analysis": "AI 未生成管理建议。"}],
            })
        else:
            new_sections.append({
                "type": rt,
                "title": _section_title_for(rt),
                "insights": [{"analysis": f"{_section_title_for(rt)}：本章节无相关数据。"}],
            })

    if new_sections:
        sections.extend(new_sections)
    return sections


def _section_title_for(section_type: str) -> str:
    """section type → 中文标题"""
    return {
        "trend_analysis": "趋势分析",
        "ranking_analysis": "排名分析",
        "structure_analysis": "结构分析",
        "concentration_analysis": "集中度分析",
        "distribution_analysis": "分布分析",
        "correlation_analysis": "相关性分析",
        "comparison_analysis": "对比分析",
        "geo_analysis": "地理空间分析",
        "retention_analysis": "留存分析",
        "anomaly_analysis": "异常分析",
        "proportion_analysis": "占比分析",
        "risk_analysis": "风险分析",
    }.get(section_type, section_type)

def _parse_report_json(ai_text: str) -> List[Dict[str, Any]]:
    """从 AI 返回的文本中解析 JSON sections"""
    import json as _json

    # 提取 JSON 块
    if "```json" in ai_text:
        start = ai_text.find("```json") + 7
        end = ai_text.find("```", start)
        json_str = ai_text[start:end].strip()
    elif "```" in ai_text:
        start = ai_text.find("```") + 3
        end = ai_text.find("```", start)
        json_str = ai_text[start:end].strip()
    else:
        # 尝试找到 JSON 对象
        brace_start = ai_text.find("{")
        brace_end = ai_text.rfind("}")
        if brace_start >= 0 and brace_end > brace_start:
            json_str = ai_text[brace_start:brace_end + 1]
        else:
            return [{"type": "error", "title": "AI 返回解析失败", "content": ai_text[:500]}]

    try:

        data = _json.loads(json_str)
        sections = data.get("sections", [])
        # 兜底：只在 sections 为空（AI 完全没生成）时才补全。
        # 旧逻辑 len < 5 触发补全会与正常 AI 输出冲突。
        if not sections:
            sections = _fill_missing_sections(sections)
        return sections
    except Exception:
        # JSON 解析失败，返回原始文本
        return [{"type": "error", "title": "AI 返回格式异常", "content": ai_text[:1000]}]


def _bind_core_charts_to_sections(
    sections: List[Dict[str, Any]],
    charts: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """自动将保底图表绑定到对应类型的报告 section 上

    plan_charts 的阶段 A 给每个保底图打了 section 标签（trend/structure/top）。
    此函数确保这些图的 chartIndex 被绑定到对应的 section，AI 即使漏填也能兜底。
    只在 AI 没有填 chartIndex 时才补，不覆盖 AI 已有的绑定。
    """
    # 建立 section.tag → chart 索引的映射
    section_to_chart_idx: Dict[str, int] = {}
    for i, chart in enumerate(charts):
        tag = chart.get("section")
        if tag and tag not in section_to_chart_idx:
            section_to_chart_idx[tag] = i

    for section in sections:
        stype = section.get("type", "")
        # 只在 section 没有 chartIndex 时才补
        if "chartIndex" not in section and stype in section_to_chart_idx:
            section["chartIndex"] = section_to_chart_idx[stype]

    return sections


def _sections_to_markdown(sections: List[Dict[str, Any]]) -> str:
    """将结构化 sections 列表转换为 Markdown 文本（用于 Streamlit 显示）"""
    lines = []

    # 图标映射
    type_colors = {
        "overview": "[INFO]", "kpi": "[KPI]", "trend": "[TREND]",
        "structure": "[STRUCT]", "top": "[TOP]", "anomaly": "[WARN]",
        "conclusion": "[CONCLUSION]", "suggestions": "[SUGGEST]", "next_steps": "[NEXT]",
        "error": "[ERROR]",
    }

    # 洞察类型标签颜色
    label_colors = {
        "趋势洞察": "[TREND]", "结构洞察": "[STRUCT]", "集中度洞察": "[TOP]",
        "异常洞察": "[WARN]", "风险洞察": "[RISK]",
    }

    for section in sections:
        icon = type_colors.get(section.get("type", ""), "[PIN]")
        title = section.get("title", "")
        lines.append(f"## {icon} {title}")
        lines.append("")

        # content 字段
        if section.get("content"):
            lines.append(section["content"])
            lines.append("")

        # insights 字段
        insights = section.get("insights", [])
        if insights:
            for item in insights:
                if isinstance(item, dict):
                    chart_title = item.get("chart_title", "") or ""
                    analysis = item.get("analysis", "") or ""
                    chart_type = item.get("chart_type") or ""
                    table_type = item.get("table_type") or ""
                    rule_id = item.get("rule_id") or ""
                    insight_label = item.get("insight_label") or ""

                    # 构建规则标签行
                    rule_badge = ""
                    if rule_id or chart_type or table_type or insight_label:
                        badge_parts = []
                        if insight_label:
                            label_icon = label_colors.get(insight_label, "")
                            badge_parts.append(f"{label_icon} {insight_label}")
                        if rule_id:
                            badge_parts.append(rule_id)
                        if chart_type and chart_type != "null":
                            badge_parts.append(f"[KPI] {chart_type}")
                        if table_type and table_type not in ("null", ""):
                            badge_parts.append(f"[INFO] {table_type}")
                        rule_badge = f"*[{' | '.join(badge_parts)}]*  "

                    # 渲染内容
                    if chart_title:
                        lines.append(f"- {rule_badge}**{chart_title}**：{analysis}")
                    else:
                        lines.append(f"- {rule_badge}{analysis}")
                elif isinstance(item, str):
                    lines.append(f"- {item}")
            lines.append("")

        # next_steps section 特殊渲染
        if section.get("type") == "next_steps":
            # ---- 生图计划 ----
            charts_plan = section.get("charts_to_create", [])
            if charts_plan:
                chart_type_cn = {
                    "line": "折线图", "bar": "柱状图", "pie": "饼图",
                    "horizontal_bar": "横向条形图", "stacked_bar": "堆叠柱状图",
                    "scatter": "散点图", "histogram": "直方图", "map_3d": "3D 地图",
                    "table": "数据表格",
                }
                lines.append("### [KPI] 推荐生成的图表")
                lines.append("")
                for c in charts_plan:
                    ctype = c.get("chart_type", "")
                    cname = chart_type_cn.get(ctype, ctype)
                    ctitle = c.get("chart_title", "")
                    guide = c.get("guide", "")
                    value = c.get("value", "")
                    rid = c.get("rule_id", "")
                    xa = c.get("x_axis", "")
                    ya = c.get("y_axis", "")
                    rid_str = f" [{rid}]" if rid else ""
                    lines.append(f"- **{ctitle}**{rid_str} → 创建**{cname}**（X={xa}，Y={ya}）")
                    if value:
                        lines.append(f"  > {value}")
                    if guide:
                        lines.append(f"  > [MOUSE]️ {guide}")
                    lines.append("")
            # ---- 操作清单 ----
            action_items = section.get("action_items", [])
            if action_items:
                lines.append("### [OK] 操作清单")
                lines.append("")
                for a in sorted(action_items, key=lambda x: x.get("priority", 99)):
                    lines.append(f"{a.get('priority', '')}. {a.get('action', '')}")
                lines.append("")

        if section.get("type") == "overview":
            lines.append("---")
        lines.append("")

    return "\n".join(lines).strip()


def _build_fallback_sections(analysis_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """构建降级报告（无 AI 洞察时的统计摘要），包含可执行的生图计划"""
    fields = analysis_data["phase_1_fields"]
    stats = analysis_data["phase_3_stats"]
    charts = analysis_data["phase_2_charts"]
    overview = stats["overview"]

    sections: List[Dict[str, Any]] = []

    # 数据概览
    sections.append({
        "type": "overview",
        "title": "数据概览",
        "content": (
            f"本数据集包含 {overview['total_rows']:,} 行 {overview['total_cols']} 列。"
            f"时间维度：{fields.get('time_dimension') or '无'}。"
            f"核心指标：{', '.join(fields.get('metrics', [])) or '无'}。"
            f"分类维度：{', '.join(fields.get('dimensions', [])) or '无'}。"
            f"数据缺失率 {overview['missing_rate']}%，重复行 {overview['duplicate_rows']} 行。"
        ),
    })

    # KPI 指标（规则10：同环比）
    kpi_insights = []
    for col, s in stats.get("basic_stats", {}).items():
        kpi_insights.append({
            "chart_title": f"{col}核心指标",
            "chart_type": None,
            "table_type": None,
            "rule_id": "规则10",
            "insight_label": "趋势洞察",
            "analysis": f"{col}：总计 {s['total']:,.2f}，均值 {s['mean']:,.2f}，最大值 {s['max']:,.2f}",
        })
    sections.append({"type": "kpi", "title": "核心指标", "insights": kpi_insights})

    # 趋势（规则9）
    trend_insights = []
    for col, t in stats.get("trend_analysis", {}).items():
        g = t.get("overall_growth_rate")
        icon = "[UP]" if (g or 0) > 0 else "[DOWN]" if (g or 0) < 0 else "➖"
        trend_insights.append({
            "chart_title": f"{col}趋势分析",
            "chart_type": "line",
            "table_type": "sort",
            "rule_id": "规则9",
            "insight_label": "趋势洞察",
            "analysis": f"整体增长 {icon} {g:+.2f}%，波动率 {t['volatility_cv']:.2f}%，最长连续涨 {t['consecutive_up']} 次。",
        })
    sections.append({"type": "growth_analysis", "title": "趋势分析", "insights": trend_insights})

    # 结构（规则12）
    struct_insights = []
    for key, s in stats.get("structure_analysis", {}).items():
        struct_insights.append({
            "chart_title": key,
            "chart_type": "pie",
            "table_type": "summary",
            "rule_id": "规则12",
            "insight_label": "结构洞察",
            "analysis": f"共 {s['category_count']} 个分类，Top3 占比 {s['top3_share']:.1f}%。",
        })
    sections.append({"type": "structure_analysis", "title": "结构分析", "insights": struct_insights})

    # Top（规则11）
    top_insights = []
    for key, t in stats.get("top_analysis", {}).items():
        top_insights.append({
            "chart_title": f"{key}排名分析",
            "chart_type": "bar",
            "table_type": "sort",
            "rule_id": "规则11",
            "insight_label": "集中度洞察",
            "analysis": f"{key}：Top1={t['max_category']}({t['max_value']:,.2f})，Top3 集中度={t.get('top3_concentration',0):.1f}%",
        })
    sections.append({"type": "ranking_analysis", "title": "TOP / 集中度分析", "insights": top_insights})

    # 异常
    anomaly_insights = []
    for a in stats.get("anomaly_analysis", []):
        if a.get("type") == "占比异常":
            anomaly_insights.append({
                "chart_title": None, "chart_type": None, "table_type": None,
                "rule_id": None, "insight_label": "风险洞察", "analysis": a.get("warning", ""),
            })
        elif a.get("type") == "IQR异常":
            anomaly_insights.append({
                "chart_title": None, "chart_type": None, "table_type": None,
                "rule_id": None, "insight_label": "异常洞察",
                "analysis": f"{a.get('metric','')}：发现 {a.get('count',0)} 个 IQR 异常值（{a.get('anomaly_rate',0):.1f}%）",
            })
    if not anomaly_insights:
        anomaly_insights = [{
            "chart_title": None, "chart_type": None, "table_type": None,
            "rule_id": None, "insight_label": "异常洞察", "analysis": "未检测到显著异常",
        }]
    sections.append({"type": "anomaly_analysis", "title": "异常分析", "insights": anomaly_insights})

    # 结论
    sections.append({
        "type": "conclusion",
        "title": "核心结论",
        "insights": [
            {"chart_title": None, "chart_type": None, "table_type": None,
             "rule_id": None, "insight_label": None,
             "analysis": f"数据规模 {overview['total_rows']:,} 行，{overview['total_cols']} 个字段"},
            {"chart_title": None, "chart_type": None, "table_type": None,
             "rule_id": None, "insight_label": None,
             "analysis": f"缺失率 {overview['missing_rate']}%（{'偏高，建议关注' if overview['missing_rate'] > 5 else '正常范围'}）"},
            {"chart_title": None, "chart_type": None, "table_type": None,
             "rule_id": None, "insight_label": None,
             "analysis": "以上为自动统计分析结果，开启 AI API Key 可生成更丰富的洞察"},
        ],
    })


    # 建议（更具体的业务建议）
    dims = fields.get("dimensions", [])
    mets = fields.get("metrics", [])
    time_col = fields.get("time_dimension")

    suggestion_items = []
    if dims and mets:
        suggestion_items.append({
            "chart_title": None, "chart_type": None, "table_type": None,
            "rule_id": None, "insight_label": None,
            "analysis": f"重点监控 {dims[0]} 维度的 {mets[0] if mets else '指标'} 变化趋势，按周对比异常波动"
        })
    if time_col and mets:
        suggestion_items.append({
            "chart_title": None, "chart_type": None, "table_type": None,
            "rule_id": None, "insight_label": None,
            "analysis": f"建立 {mets[0]} 的月度环比监控，若环比下降超过 15% 触发预警"
        })
    if overview["missing_rate"] > 5:
        suggestion_items.append({
            "chart_title": None, "chart_type": None, "table_type": None,
            "rule_id": None, "insight_label": None,
            "analysis": f"数据缺失率 {overview['missing_rate']}%，建议排查缺失原因并补充数据"
        })
    # 兜底
    if not suggestion_items:
        suggestion_items = [{
            "chart_title": None, "chart_type": None, "table_type": None,
            "rule_id": None, "insight_label": None,
            "analysis": "定期监控指标变化趋势，及时调整业务策略"
        }]
    sections.append({
        "type": "suggestions",
        "title": "业务建议",
        "insights": suggestion_items,
    })

    # ---- 后续操作：操作清单 ----
    action_items = []
    if dims and mets:
        action_items.append({
            "priority": 1,
            "action": f"优先进入「仪表盘」页面，创建折线图监控 {mets[0]} 随时间的变化趋势"
        })
    if len(dims) >= 2 and mets:
        action_items.append({
            "priority": 2,
            "action": f"创建 {dims[0]}×{dims[1]} 交叉分析图，找出双重维度下的增长驱动因素"
        })
    if len(mets) >= 2:
        action_items.append({
            "priority": 3,
            "action": f"创建 {mets[0]} 与 {mets[1]} 的散点图，探索指标间相关性"
        })
    action_items.append({
        "priority": 99,
        "action": "完成图表创建后，点击「生成报告」按钮生成完整分析报告并导出 PDF"
    })
    if not action_items:
        action_items = [{"priority": 1, "action": "去仪表盘页面创建合适的图表，开始数据可视化分析"}]

    sections.append({
        "type": "next_steps",
        "title": "下一步操作建议",
        "action_items": action_items,
    })

    return sections


# ============================================================
# 数据洞察（用户指定格式）辅助函数
# ============================================================

def _build_insights_data_summary(
    df: pd.DataFrame,
    fields: Dict[str, Any],
    stats: Dict[str, Any],
    charts: List[Dict[str, Any]],
) -> str:
    """构建给 LLM 的数据摘要（用于生成用户指定格式的洞察）"""
    overview = stats["overview"]
    lines = []

    # 一、基本信息
    lines.append("【数据基本信息】")
    lines.append(f"- 行数：{overview['total_rows']:,}")
    lines.append(f"- 列数：{overview['total_cols']}")
    lines.append(f"- 完整列名列表：{overview['column_names']}")
    lines.append(f"- 数据类型：{dict(zip(overview['column_names'], [str(d) for d in df.dtypes]))}")
    lines.append("")

    # 二、字段分类（最重要！LLM 必须使用这些真实列名）
    time_col = fields.get("time_dimension")
    metrics = fields.get("metrics", [])
    dimensions = fields.get("dimensions", [])

    lines.append("【字段分类——分析建议中必须使用这些真实列名！】")
    lines.append(f"- [CAL] 时间列：{time_col if time_col else '（无）'}")
    lines.append(f"- [KPI] 数值指标列：{', '.join(metrics) if metrics else '（无）'}")
    lines.append(f"- [TAG]️ 分类维度列：{', '.join(dimensions) if dimensions else '（无）'}")
    # 识别地区列
    region_cols = [c for c in dimensions if any(
        kw in str(c).lower() for kw in ['省', '市', '区', '县', '地区', '区域', '城市', '省份',
                                          'province', 'city', 'region', 'district', 'area']
    )]
    if region_cols:
        lines.append(f"- [MAP]️ 地区/地图列：{', '.join(region_cols)}（必须推荐 3D 地图！）")
    lines.append("")

    # 三、数据质量
    missing_info = df.isnull().sum().to_dict()
    missing_cols = {k: v for k, v in missing_info.items() if v > 0}
    lines.append("【数据质量】")
    lines.append(f"- 总缺失值：{overview['missing_total']} 个（{overview['missing_rate']}%）")
    if missing_cols:
        lines.append(f"- 有缺失的列：{missing_cols}")
    lines.append(f"- 重复行：{overview['duplicate_rows']} 行")
    lines.append("")

    # 四、数值列统计
    if metrics:
        lines.append("【数值指标统计（用于关键发现中引用具体数字）】")
        for col_name in metrics[:5]:
            if col_name in df.columns:
                col_data = df[col_name].dropna()
                if len(col_data) > 0 and pd.api.types.is_numeric_dtype(col_data):
                    lines.append(
                        f"- {col_name}：均值={col_data.mean():,.2f} "
                        f"中位数={col_data.median():,.2f} "
                        f"总和={col_data.sum():,.2f} "
                        f"最大值={col_data.max():,.2f} "
                        f"最小值={col_data.min():,.2f} "
                        f"标准差={col_data.std():,.2f}"
                    )
        lines.append("")

    # 五、分类列信息
    if dimensions:
        lines.append("【分类维度信息（用于分析建议中的对比/排名/占比分析）】")
        for dim in dimensions[:5]:
            if dim in df.columns:
                vc = df[dim].value_counts()
                top3 = ", ".join(f"{k}({v})" for k, v in vc.head(3).items())
                lines.append(f"- {dim}：共 {len(vc)} 个分类，Top3：{top3}")
        lines.append("")

    # 六、已规划图表（作为参考，LLM 可据此生成分析建议）
    if charts:
        lines.append("【系统已推荐的图表（作为分析建议的参考）】")
        for c in charts[:10]:
            x = c.get('x', '')
            y = c.get('y', '')
            t = c.get('type', '')
            title = c.get('title', '')
            reason = c.get('reason', '')
            lines.append(f"- [{t}] {title}（X={x}, Y={y}）→ {reason}")
        lines.append("")

    return "\n".join(lines)


def _clean_insights_text(ai_text: str) -> str:
    """清洗 AI 返回的洞察文本（去除常见前缀后缀）"""
    text = ai_text.strip()
    # 去掉 AI 可能添加的前导语
    prefixes_to_strip = [
        "好的，以下是对数据的分析：",
        "好的，以下是数据分析报告：",
        "以下是对给定数据的分析：",
        "根据提供的数据，分析如下：",
        "好的，我来分析：",
        "以下是对数据的自动分析：",
    ]
    for prefix in prefixes_to_strip:
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
    # 去掉可能的 markdown code block 包裹
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline > 0:
            text = text[first_newline:].strip()
        if text.endswith("```"):
            text = text[:-3].strip()
    # 确保以 ## 开头
    if not text.startswith("##") and not text.startswith("##"):
        lines = text.split("\n")
        # 找到第一个 ## 行
        for i, line in enumerate(lines):
            if line.strip().startswith("##"):
                text = "\n".join(lines[i:])
                break
    return text


def _build_fallback_insights(
    df: pd.DataFrame,
    fields: Dict[str, Any],
    stats: Dict[str, Any],
    charts: List[Dict[str, Any]],
    error_msg: str,
) -> str:
    """构建降级洞察（无 LLM 时用 Python 直接生成用户指定格式）"""
    overview = stats["overview"]
    time_col = fields.get("time_dimension")
    metrics = fields.get("metrics", [])
    dimensions = fields.get("dimensions", [])
    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    cat_cols = [c for c in df.columns if c not in numeric_cols and c != time_col]

    # 识别地区列
    region_cols = [c for c in dimensions if any(
        kw in str(c).lower() for kw in ['省', '市', '区', '县', '地区', '区域', '城市', '省份',
                                          'province', 'city', 'region', 'district', 'area']
    )]

    lines = []

    # ---- 数据概览 ----
    lines.append("## 数据概览")
    lines.append(
        f"本数据集包含 {overview['total_rows']:,} 行、{overview['total_cols']} 列，"
        f"涵盖 {len(metrics)} 个数值指标和 {len(dimensions)} 个分类维度。"
    )
    if time_col:
        lines.append(f"数据有时间维度「{time_col}」，支持趋势分析和同环比计算。")
    if region_cols:
        lines.append(f"数据包含地区维度「{region_cols[0]}」，支持地理分布分析。")
    lines.append("")

    # ---- 关键发现 ----
    lines.append("## 关键发现")
    finding_idx = 1
    # 时间趋势
    if time_col and metrics:
        col = metrics[0]
        if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
            lines.append(f"{finding_idx}. 「{col}」数据整体均值为 {df[col].mean():,.2f}，最高值 {df[col].max():,.2f}，最低值 {df[col].min():,.2f}，标准差 {df[col].std():,.2f}")
            finding_idx += 1
    # Top 集中度
    for dim in dimensions[:2]:
        if dim in df.columns:
            vc = df[dim].value_counts()
            top1 = vc.index[0]
            top3_share = vc.head(3).sum() / vc.sum() * 100 if vc.sum() > 0 else 0
            lines.append(f"{finding_idx}. 「{dim}」维度共 {len(vc)} 个分类，Top1 为「{top1}」，Top3 占比 {top3_share:.1f}%")
            finding_idx += 1
    # 每指标统计
    for col in metrics[1:3]:
        if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
            lines.append(f"{finding_idx}. 「{col}」总和 {df[col].sum():,.2f}，中位数 {df[col].median():,.2f}，数据离散度为 {df[col].std()/df[col].mean()*100 if df[col].mean() != 0 else 0:.1f}%")
            finding_idx += 1
    # 异常
    anomaly_list = stats.get("anomaly_analysis", [])
    if anomaly_list:
        lines.append(f"{finding_idx}. 检测到 {len(anomaly_list)} 类数据异常，包括：{', '.join(a.get('type', '') for a in anomaly_list)}")
        finding_idx += 1
    if finding_idx <= 1:
        lines.append("1. 数据规模适中，字段结构完整，可进行多维度交叉分析")
    lines.append("")

    # ---- 数据质量 ----
    lines.append("## 数据质量")
    missing_cols = {k: v for k, v in df.isnull().sum().to_dict().items() if v > 0}
    if missing_cols:
        lines.append(f"存在缺失值：{missing_cols}，整体缺失率 {overview['missing_rate']}%。")
    else:
        lines.append("数据完整性良好，无缺失值。")
    if overview['duplicate_rows'] > 0:
        lines.append(f"发现 {overview['duplicate_rows']} 行重复数据，建议去重后分析。")
    # 异常值
    anomaly_list = stats.get("anomaly_analysis", [])
    if anomaly_list:
        for a in anomaly_list[:3]:
            t = a.get("type", "")
            if t == "IQR异常":
                lines.append(f"「{a.get('metric', '')}」列存在 {a.get('count', 0)} 个 IQR 异常值。")
            elif t == "占比异常":
                lines.append(f"「{a.get('dimension', '')}」维度：{a.get('warning', '')}")
    else:
        lines.append("未检测到显著异常值。")
    lines.append("")

    # ---- 分析建议 ----
    lines.append("## 分析建议")
    lines.append("以下建议包含计算列和推荐图表，每条标注X轴列和Y轴列，点击「应用洞察」可自动执行：")
    lines.append("")
    s_idx = 1

    # 策略1：有时间列 + 金额/数值列 → 优先同环比
    if time_col and metrics:
        for metric in metrics[:2]:
            lines.append(f"{s_idx}. 计算「{metric}」的同比（与去年同月对比）→ 折线图（X:{time_col}, Y:{metric}同比）")
            lines.append(f"    + 排序表格（排序:{metric}同比变化%, 降序）")
            s_idx += 1
            lines.append(f"{s_idx}. 计算「{metric}」的环比（与上月对比）→ 折线图（X:{time_col}, Y:{metric}环比）")
            lines.append(f"    + 排序表格（排序:{metric}环比变化%, 降序）")
            s_idx += 1
            lines.append(f"{s_idx}. 计算「{metric}」的累计值 → 面积图（X:{time_col}, Y:{metric}累计）")
            s_idx += 1
            lines.append(f"{s_idx}. 计算「{metric}」的移动平均（3月平滑）→ 折线图（X:{time_col}, Y:{metric}移动平均）")
            s_idx += 1
            break  # 只对第一个指标做同环比

    # 策略2：有地区列 → 3D 地图
    if region_cols and metrics:
        lines.append(f"{s_idx}. 绘制「{region_cols[0]}」的「{metrics[0]}」地图与省份地区分布 → 3D地图（X:{region_cols[0]}, Y:{metrics[0]}）")
        lines.append(f"    + 汇总表格（行:{region_cols[0]}, 列:{metrics[0]}）")
        s_idx += 1

    # 策略3：有分类维度 + 数值指标 → 对比排名 / 占比
    if dimensions and metrics:
        lines.append(f"{s_idx}. 计算各「{dimensions[0]}」的「{metrics[0]}」均值，对比排名 → 柱状图（X:{dimensions[0]}, Y:{metrics[0]}）")
        lines.append(f"    + 排序表格（排序:{metrics[0]}, 降序）")
        s_idx += 1

    # 策略4：≥2 个数值指标 → 散点图
    if len(metrics) >= 2:
        lines.append(f"{s_idx}. 探索「{metrics[0]}」与「{metrics[1]}」的相关与关联关系 → 散点图（X:{metrics[0]}, Y:{metrics[1]}）")
        lines.append(f"    + 相关系数表格（行:{metrics[0]}, 列:{metrics[1]}）")
        s_idx += 1

    # 策略5：数值列分布
    if metrics:
        lines.append(f"{s_idx}. 分析「{metrics[0]}」的分布与频次 → 直方图（X:{metrics[0]}, Y:）")
        s_idx += 1

    # 策略6：≥2 个分类维度 → 交叉分析
    if len(dimensions) >= 2 and metrics:
        lines.append(f"{s_idx}. 计算「{metrics[0]}」按「{dimensions[0]}」×「{dimensions[1]}」的交叉汇总 → 堆叠柱状图（X:{dimensions[0]}, Y:{metrics[0]}, 分组:{dimensions[1]}）")
        lines.append(f"    + 交叉表格（行:{dimensions[0]}, 列:{dimensions[1]}, 值:{metrics[0]}）")
        s_idx += 1

    # 策略7：无时间列时 → 排名
    if not time_col and dimensions and metrics:
        lines.append(f"{s_idx}. 计算「{metrics[0]}」按「{dimensions[0]}」的排名 → 柱状图（X:{dimensions[0]}, Y:{metrics[0]}）")
        lines.append(f"    + 排序表格（排序:{metrics[0]}, 降序）")
        s_idx += 1

    if s_idx == 1:
        # 兜底
        if numeric_cols and cat_cols:
            lines.append(f"1. 计算各「{cat_cols[0]}」的「{numeric_cols[0]}」对比排名 → 柱状图（X:{cat_cols[0]}, Y:{numeric_cols[0]}）")
            lines.append(f"    + 排序表格（排序:{numeric_cols[0]}, 降序）")

    return "\n".join(lines) + f"\n\n\n---\n\n> [WARN] AI 洞察生成失败（{error_msg}），以上为自动统计分析结果。"



# ============================================================
# V3：基于 AnalysisPackage 的报告辅助函数
# ============================================================

# 归一化：将 AI prompt 中使用的 section type（新名）映射到前端 DashboardPage 硬编码的旧名
# 前端 DashboardPage.tsx:417-433 只识别：overview/kpi/trend/top/structure/anomaly/conclusion/suggestions/next_steps
_SECTION_TYPE_NORMALIZE: Dict[str, str] = {
    "data_overview": "overview",
    "trend_analysis": "trend",
    "growth_analysis": "trend",  # 五阶段流水线 _build_fallback_sections 使用的旧名
    "ranking_analysis": "top",
    "structure_analysis": "structure",
    "anomaly_analysis": "anomaly",
    "conclusion": "conclusion",
    "management_suggestions": "suggestions",
    "action_items": "next_steps",
}

def _normalize_section_types(sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """将 AI 返回/fallback 生成的 sections 的 type 转为前端兼容的旧名

    同时为 next_steps 类型的 section 容错：AI 可能输出 actions/steps/recommendations
    等变体字段名，统一规范为 action_items（前端 buildReportHTML 识别的字段名）。
    """
    for s in sections:
        old_type = _SECTION_TYPE_NORMALIZE.get(s.get("type", ""), s.get("type", ""))
        s["type"] = old_type
        # next_steps 容错：合并各种可能的字段名到 action_items
        if s.get("type") == "next_steps" and not s.get("action_items"):
            merged: List[Dict[str, Any]] = []
            for alt_key in ("actions", "steps", "recommendations", "action_list", "items"):
                alt = s.get(alt_key)
                if isinstance(alt, list):
                    for item in alt:
                        if isinstance(item, str):
                            merged.append({"priority": 99, "action": item})
                        elif isinstance(item, dict):
                            merged.append({
                                "priority": item.get("priority", item.get("顺序", 99)),
                                "action": item.get("action", item.get("action_text", item.get("text", str(item)))),
                            })
            if merged:
                s["action_items"] = merged
    return sections

def _bind_package_charts_to_sections(
    sections: List[Dict[str, Any]],
    sections_data: Dict[str, List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """将 AnalysisPackage 中的图表信息绑定到 AI 生成的 sections 中"""
    chart_map: Dict[str, Dict[str, Any]] = {}
    for section_name, pkgs in sections_data.items():
        for pkg in pkgs:
            charts = pkg.get("chart_data", [])
            for c in charts:
                title = c.get("title", "")
                if title:
                    chart_map[title] = {
                        "chart_type": c.get("chart_type", c.get("type", "")),
                        "analysis_type": pkg.get("analysis_type", ""),
                        "dimension": pkg.get("dimension"),
                        "metric": pkg.get("metric"),
                    }

    for section in sections:
        insights = section.get("insights")
        if not isinstance(insights, list):
            continue
        for ins in insights:
            ct = ins.get("chart_title", "")
            if ct and ct in chart_map:
                info = chart_map[ct]
                if not ins.get("chart_type"):
                    ins["chart_type"] = info["chart_type"]
                if not ins.get("analysis_type"):
                    ins["analysis_type"] = info["analysis_type"]
                if not ins.get("dimension"):
                    ins["dimension"] = info["dimension"]
                if not ins.get("metric"):
                    ins["metric"] = info["metric"]

    return sections


def _build_fallback_from_packages(
    packages: List[Dict[str, Any]],
    report_input: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """AI 调用失败时，直接用 AnalysisPackage 中的已有数据构建报告"""
    sections: List[Dict[str, Any]] = []
    sections_data = report_input.get("sections_data", {})

    # 执行摘要
    total_kpis = 0
    total_insights = 0
    for pkgs in sections_data.values():
        for pkg in pkgs:
            total_kpis += len(pkg.get("kpis", []))
            total_insights += len(pkg.get("insights", [])) + len(pkg.get("conclusions", []))
    sections.append({
        "type": "executive_summary",
        "title": "执行摘要",
        "content": (
            f"本报告基于 {len(packages)} 个已完成的分析包生成。"
            f"共包含 {total_kpis} 项 KPI 指标和 {total_insights} 条数据洞察。"
        ),
    })

    # 数据概览
    data_profile = report_input.get("data_profile", {})
    if data_profile:
        time_cols = data_profile.get("time_cols", [])
        cat_cols = data_profile.get("category_cols", [])
        num_cols = data_profile.get("numeric_cols", [])
        sections.append({
            "type": "data_overview",
            "title": "数据概览",
            "content": (
                f"时间维度：{', '.join(time_cols) if time_cols else '无'}。"
                f"数值指标：{', '.join(num_cols) if num_cols else '无'}。"
                f"分类维度：{', '.join(cat_cols) if cat_cols else '无'}。"
            ),
        })
    else:
        sections.append({
            "type": "data_overview",
            "title": "数据概览",
            "content": f"基于 {len(packages)} 个分析包生成。分析包概要：{report_input.get('packages_summary', '')}",
        })

    # 各分析章节
    for section_name, pkgs in sections_data.items():
        insights = []
        for pkg in pkgs:
            question = pkg.get("business_question", "")
            conclusions = pkg.get("conclusions", [])
            pkg_insights = pkg.get("insights", [])
            kpis = pkg.get("kpis", [])

            analysis_parts = []
            if question:
                analysis_parts.append(f"业务问题：{question}")
            if kpis:
                kpi_texts = []
                for k in kpis[:5]:
                    cs = f" ({k.get('change', '')})" if k.get("change") else ""
                    kpi_texts.append(f"{k.get('label', '')}：{k.get('value', '')}{cs}")
                analysis_parts.append("；".join(kpi_texts))
            if conclusions:
                analysis_parts.extend(conclusions)
            if pkg_insights:
                analysis_parts.extend(pkg_insights[:3])

            chart_title = None
            charts = pkg.get("chart_data", [])
            if charts:
                chart_title = charts[0].get("title", "")

            insights.append({
                "chart_title": chart_title,
                "chart_type": charts[0].get("type") if charts else None,
                "insight_label": None,
                "analysis_type": pkg.get("analysis_type", ""),
                "dimension": pkg.get("dimension"),
                "metric": pkg.get("metric"),
                "business_question": question,
                "business_conclusion": "；".join(conclusions) if conclusions else None,
                "analysis": "。".join(analysis_parts) if analysis_parts else "暂无详细分析数据",
            })

        if insights:
            sections.append({
                "type": section_name,
                "title": SECTION_DISPLAY_NAME.get(section_name, section_name),
                "insights": insights,
            })

    # 管理建议
    all_conclusions = []
    for pkgs in sections_data.values():
        for pkg in pkgs:
            all_conclusions.extend(pkg.get("conclusions", []))
            all_conclusions.extend(pkg.get("recommendations", []))

    if all_conclusions:
        sections.append({
            "type": "management_suggestions",
            "title": "管理建议",
            "insights": [{"analysis": c} for c in all_conclusions[:5]],
        })

    # 总结
    sections.append({
        "type": "conclusion",
        "title": "总结",
        "insights": [{"analysis": f"报告基于 {len(packages)} 个分析包自动生成。AI 报告生成失败，以上内容为已有分析数据的直接汇总。"}],
    })

    return sections