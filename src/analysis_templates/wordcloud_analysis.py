"""
词频/词云分析模板 —— 统计分类列中各类别的出现次数，生成词云图

V1：基于 RankingCalculator 计算次数，复用 wordcloud 图表类型
"""
import pandas as pd
from src.analysis_templates.base import (
    AnalysisTemplate, TemplateMeta, TemplateRuntime,
    KPIItem, TableData, ChartData,
)


class WordCloudAnalysis(AnalysisTemplate):
    meta = TemplateMeta(
        analysis_type="wordcloud_analysis",
        display_name="词频/词云分析",
        version="1.0",
        description="统计分类列中各类别的出现次数，生成词云图展示最热门项目",
    )

    runtime = TemplateRuntime(
        REQUIRED_SCHEMA={
            "dimension_type": "category",
            "metric_type": "",
            "min_dimension": 1,
            "min_metric": 0,
        },
        MIN_ROWS=3,
        FALLBACK="ranking_analysis",
    )

    _cache: dict = {}

    def can_run(self, df: pd.DataFrame) -> bool:
        """需要至少 1 个文本/分类列 + 至少 3 行 + 2 个以上不同值。

        词云本就适合高基数文本（如产品长名称、评论），因此放宽接受任意
        非数值文本列，而非仅分类器判定的「分类列」（后者会排除高基数文本）。
        """
        if df is None or len(df) < self.runtime.MIN_ROWS:
            return False
        text_cols = [c for c in df.columns
                     if not pd.api.types.is_numeric_dtype(df[c]) and df[c].nunique() >= 2]
        if text_cols:
            return True
        cat_cols = self.classifier.get_category_columns(df) if self.classifier else []
        return len(cat_cols) >= 1

    def _compute(self, df, dimension, metric, **kwargs):
        """统计 dimension 列中各类别的出现次数"""
        dim = dimension
        if not dim or dim not in df.columns:
            # 兜底：复用 Planner 同样的「确定性语义解构选列」（2026-07-13 统一选列入口）
            #   历史上用 text_cols[0] 或 get_category_columns[0]，会把订单号/流水号（每行唯一）
            #   当成词云维度，导致词云变成 1 个超长词或乱序高频词。
            dim = self.classifier.select_wordcloud_column(df, "") if self.classifier else None
        if not dim or dim not in df.columns:
            return None
        counts = df[dim].value_counts().reset_index()
        counts.columns = [dim, "count"]
        # 截取 Top 50
        counts = counts.head(50)
        self._cache["dimension"] = dim
        self._cache["counts"] = counts
        self._cache["total"] = int(df[dim].notna().sum())
        self._cache["unique"] = int(df[dim].nunique())
        return counts

    def build_kpis(self, df, dimension, metric, algorithm):
        self._compute(df, dimension, metric)
        counts = self._cache.get("counts")
        if counts is None or len(counts) == 0:
            return [KPIItem(label="无数据", value="0", change="", kpi_type="count")]

        top1_name = str(counts.iloc[0].iloc[0])
        top1_count = int(counts.iloc[0]["count"])
        top3_sum = int(counts.head(3)["count"].sum())
        top3_share = top3_sum / max(self._cache["total"], 1)

        return [
            KPIItem(label=f"最高频：{top1_name}", value=f"{top1_count} 次", change="", kpi_type="count"),
            KPIItem(label="Top3 集中度", value=f"{top3_share*100:.1f}%", change="", kpi_type="rate"),
            KPIItem(label="独立类别数", value=str(self._cache["unique"]), change="", kpi_type="count"),
        ]

    def build_tables(self, df, dimension, metric, algorithm):
        counts = self._cache.get("counts")
        if counts is None or len(counts) == 0:
            return []
        dim = self._cache["dimension"]
        total = max(self._cache["total"], 1)
        rows = []
        n = min(30, len(counts))
        for i in range(n):
            name = str(counts.iloc[i].iloc[0])
            cnt = int(counts.iloc[i]["count"])
            share = cnt / total * 100
            rows.append([i + 1, name, cnt, f"{share:.1f}%"])

        return [TableData(
            title=f"{dim}词频明细",
            table_type="ranking",
            columns=["排名", dim, "出现次数", "占比(%)"],
            rows=rows,
        )]

    def build_charts(self, df, dimension, metric, algorithm):
        counts = self._cache.get("counts")
        if counts is None or len(counts) == 0:
            return []
        dim = self._cache["dimension"]
        # ECharts 词云需要 [{name, value}] 原生格式（2026-07-13 修复 value=1 链路 bug）
        # 历史上用 {x, y} 占位键再经 ChartRenderer.rename 改写，会被 create_wordcloud
        # 二次 value_counts 稀释成 value=1（每行唯一）。直接给 {name, value} 让
        # create_wordcloud 走"已聚合模式"，保证 value range > 0。
        cloud_data = []
        n = min(50, len(counts))
        for i in range(n):
            name = str(counts.iloc[i].iloc[0])
            value = int(counts.iloc[i]["count"])
            cloud_data.append({"name": name, "value": value})

        return [ChartData(
            slot="word_cloud", chart_type="wordcloud",
            title=f"{dim}词云图（出现次数）",
            x=dim, y="count",
            data=cloud_data,
        )]

    def build_insights(self, df, dimension, metric, algorithm, kpis, chart_data):
        counts = self._cache.get("counts")
        if counts is None or len(counts) == 0:
            return []
        dim = self._cache["dimension"]
        top1_name = str(counts.iloc[0].iloc[0])
        top1_count = int(counts.iloc[0]["count"])
        top3_sum = int(counts.head(3)["count"].sum())
        total = self._cache["total"]
        top3_share = top3_sum / max(total, 1) * 100
        return [
            f"「{top1_name}」出现 {top1_count} 次，是出现频率最高的{dim}",
            f"前 3 名合计占比 {top3_share:.1f}%，集中度{'较高' if top3_share > 50 else '一般'}",
            f"共有 {self._cache['unique']} 种独立{dim}，总记录 {total} 条",
        ]

    def build_findings(self, df, dimension, metric, algorithm, kpis, chart_data):
        """生成 BusinessFinding 对象（领域模型）—— 复用 self.factory"""
        counts = self._cache.get("counts")
        f = self.factory
        if counts is None or len(counts) == 0:
            return [f.summary("词频分析完成，但无可用数据")]

        dim = self._cache["dimension"]
        top1_name = str(counts.iloc[0].iloc[0])
        top1_count = int(counts.iloc[0]["count"])
        total = self._cache["total"]
        top1_share = top1_count / max(total, 1)

        findings = []
        findings.append(f.ranking(
            entity=top1_name, metric=f"{dim}出现次数", value=top1_count, rank=1,
            title=f"最高频：{top1_name}（{top1_count} 次，{top1_share*100:.1f}%）",
            confidence=1.0
        ))

        # Top3 集中度
        top3_sum = int(counts.head(3)["count"].sum())
        top3_share = top3_sum / max(total, 1)
        if top3_share > 0:
            findings.append(f.concentration(
                title=f"前 3 名{dim}占比 {top3_share*100:.1f}%",
                metric=f"{dim}频次", value=top3_share, unit="%",
                confidence=1.0,
                business_meaning=f"前 3 名合计出现 {top3_sum} 次，占总记录 {top3_share*100:.1f}%"
            ))

        # 独立类别数
        findings.append(f.summary(
            f"共有 {self._cache['unique']} 种独立{dim}，总记录 {total} 条"
        ))

        return findings
