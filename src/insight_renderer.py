"""
InsightRenderer —— 统一洞察文本渲染层

输入 List[str] → 输出按优先级排序的结构化洞察列表。
支持：优先级标记、截断、去重
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class RenderedInsight:
    text: str
    priority: str = "normal"   # "high" | "normal" | "low"
    label: str = ""             # "趋势洞察" | "结构洞察" | "异常洞察"


class InsightRenderer:
    """统一洞察渲染器"""

    # 关键词 → 优先级 + 标签映射
    PRIORITY_KEYWORDS = {
        "异常": ("high", "异常洞察"),
        "风险": ("high", "风险洞察"),
        "最高": ("high", "集中度洞察"),
        "最低": ("high", "集中度洞察"),
        "趋势": ("normal", "趋势洞察"),
        "占比": ("normal", "结构洞察"),
        "增长": ("normal", "趋势洞察"),
        "下降": ("normal", "趋势洞察"),
    }

    def render(self, insight: str, index: int = 0) -> RenderedInsight:
        """渲染单条洞察"""
        priority, label = self._classify(insight)
        # 首条洞察默认为 high
        if index == 0 and priority == "normal":
            priority = "high"
        return RenderedInsight(text=insight, priority=priority, label=label)

    def render_all(self, insights: List[str]) -> List[RenderedInsight]:
        """批量渲染并按优先级排序（high → normal → low）"""
        rendered = [self.render(text, i) for i, text in enumerate(insights)]
        # 去重（相同文本只保留一个）
        seen = set()
        unique = []
        for r in rendered:
            if r.text not in seen:
                seen.add(r.text)
                unique.append(r)
        # 排序
        priority_order = {"high": 0, "normal": 1, "low": 2}
        unique.sort(key=lambda x: priority_order.get(x.priority, 1))
        return unique

    def _classify(self, text: str) -> tuple:
        """根据文本内容推断优先级和标签"""
        for keyword, (priority, label) in self.PRIORITY_KEYWORDS.items():
            if keyword in text:
                return priority, label
        return "normal", ""
