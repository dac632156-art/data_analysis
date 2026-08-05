import uuid
from dataclasses import dataclass, field
from typing import Any, Optional
import math


# ============================================================
# Card 标准模型
# ============================================================

@dataclass
class Card:
    id: str = ""  # 不传时由 __post_init__ 自动生成 uuid 前 8 位
    type: str = ""  # kpi | chart | table | insight | warning | fallback
    title: str = ""
    priority: int = 5  # 1-10
    size: str = "m"  # s | m | l | xl
    data: Any = None
    chart_type: Optional[str] = None
    fallback_chain: list = field(default_factory=list)
    score: float = 0.0

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())[:8]


# ============================================================
# Visual Score Map
# ============================================================

VISUAL_SCORE_MAP = {
    'chart': 0.7,
    'map': 0.9,
    'kpi': 0.5,
    'table': 0.3,
    'insight': 0.4,
    'warning': 0.6,
}

# Impact weights by analysis_type
IMPACT_WEIGHTS = {
    'trend_analysis': 0.9,
    'top_analysis': 0.8,
    'distribution_analysis': 0.7,
    'correlation_analysis': 0.6,
    'geo_analysis': 0.85,
    'anomaly_detection': 0.75,
    'growth_analysis': 0.8,
    'comparison_analysis': 0.65,
}


# ============================================================
# Card Generator
# ============================================================

class CardGenerator:
    """将 AnalysisPackage 转换为 CardPackage（Card 列表）"""

    def __init__(self):
        self.cards: list[Card] = []

    def generate(self, package: dict) -> dict:
        """
        输入: AnalysisPackage dict (含 rendered_kpis, rendered_tables, rendered_charts, rendered_insights)
        输出: CardPackage dict { cards, meta }
        """
        self.cards = []

        # 1. KPI Cards
        for kpi in package.get('rendered_kpis', package.get('kpis', [])):
            card = self._kpi_card(kpi)
            if card:
                self.cards.append(card)

        # 2. Chart Cards
        for chart in package.get('rendered_charts', package.get('charts', [])):
            card = self._chart_card(chart)
            if card:
                self.cards.append(card)

        # 3. Table Cards
        for table in package.get('rendered_tables', package.get('tables', [])):
            card = self._table_card(table)
            if card:
                self.cards.append(card)

        # 4. Insight Cards
        for ins in package.get('rendered_insights', package.get('insights', [])):
            card = self._insight_card(ins)
            if card:
                self.cards.append(card)

        # 5. Fallback injection
        self.cards = self._apply_fallback(self.cards, package)

        # 7. Score + Rank
        scored = self._score_cards(self.cards, package)
        ranked = self._rank(scored)

        # 8. Build CardPackage
        insight_strength = sum(c.score for c in ranked) / max(len(ranked), 1)
        return {
            'cards': [self._card_to_dict(c) for c in ranked],
            'meta': {
                'total_cards': len(ranked),
                'insight_strength': round(insight_strength, 2),
                'data_quality': self._estimate_data_quality(package),
                'analysis_type': package.get('analysis_type', 'unknown'),
            }
        }

    def _kpi_card(self, kpi: dict) -> Optional[Card]:
        label = kpi.get('label', '')
        value = kpi.get('value', '')
        change = kpi.get('change')
        kpi_type = kpi.get('kpi_type', 'sum')

        if not label:
            return None

        # Priority based on kpi_type
        priority_map = {'sum': 8, 'rate': 9, 'change': 8, 'avg': 6, 'count': 5}
        priority = priority_map.get(kpi_type, 5)

        return Card(
            type='kpi',
            title=label,
            priority=priority,
            size=self._priority_to_size(priority),
            data={'value': value, 'change': change, 'kpi_type': kpi_type},
            score=0,
        )

    def _chart_card(self, chart: dict) -> Optional[Card]:
        title = chart.get('title', '')
        chart_type = chart.get('chart_type', '')
        option = chart.get('option') or chart.get('rendered_option') or {}
        role = chart.get('role', '')

        if not title and not chart_type:
            return None

        # Role determines priority
        role_priority = {'primary': 9, 'secondary': 6, 'detail': 4}
        priority = role_priority.get(role, 5)

        # Boost if it's a line chart (trend) or bar chart (ranking)
        if 'line' in chart_type:
            priority = max(priority, 8)
        if 'bar' in chart_type and ('top' in title.lower() or 'rank' in title.lower()):
            priority = max(priority, 7)

        return Card(
            type='chart',
            title=title or chart_type,
            priority=priority,
            size=self._priority_to_size(priority),
            data=option,
            chart_type=chart_type,
            score=0,
        )

    def _table_card(self, table: dict) -> Optional[Card]:
        title = table.get('title', '')
        table_type = table.get('table_type', '')
        columns = table.get('columns', [])
        rows = table.get('rows', [])

        if not title and not table_type:
            return None

        priority_map = {
            'ranking': 7,
            'summary': 6,
            'growth': 6,
            'correlation': 5,
            'detail': 3,
            'exception': 8,
        }
        priority = priority_map.get(table_type, 4)

        return Card(
            type='table',
            title=title or table_type,
            priority=priority,
            size=self._priority_to_size(priority),
            data={'columns': columns, 'rows': rows},
            score=0,
        )

    def _insight_card(self, insight: Any, is_conclusion: bool = False) -> Optional[Card]:
        text = insight if isinstance(insight, str) else insight.get('text', '')
        if not text:
            return None

        return Card(
            type='insight' if not is_conclusion else 'insight',
            title='核心结论' if is_conclusion else '洞察',
            priority=5,
            size='m',
            data={'text': text, 'is_conclusion': is_conclusion},
            score=0,
        )

    def _priority_to_size(self, priority: int) -> str:
        if priority >= 9:
            return 'xl'
        elif priority >= 7:
            return 'l'
        elif priority >= 4:
            return 'm'
        else:
            return 's'

    def _score_cards(self, cards: list[Card], package: dict) -> list[Card]:
        """Card Score Engine"""
        analysis_type = package.get('analysis_type', '')
        impact_weight = IMPACT_WEIGHTS.get(analysis_type, 0.5)

        for card in cards:
            score = 0.0

            # Data value (priority normalized to 0-1)
            score += (card.priority / 10.0) * 0.4

            # Business importance
            score += (card.priority / 10.0) * 0.3

            # Visual expressiveness
            score += VISUAL_SCORE_MAP.get(card.type, 0.3) * 0.2

            # Analysis type boost
            score *= (0.5 + impact_weight * 0.5)

            card.score = round(score, 3)

        return cards

    def _rank(self, cards: list[Card]) -> list[Card]:
        """排序并分配 size（XL 只有一个，L 最多 2 个）"""
        sorted_cards = sorted(cards, key=lambda c: c.score, reverse=True)

        xl_count = 0
        l_count = 0

        for card in sorted_cards:
            if card.score >= 0.6 and xl_count == 0:
                card.size = 'xl'
                xl_count += 1
            elif card.score >= 0.45 and l_count < 2:
                card.size = 'l'
                l_count += 1
            elif card.score >= 0.3:
                card.size = 'm'
            else:
                card.size = 's'

        return sorted_cards

    def _apply_fallback(self, cards: list[Card], package: dict) -> list[Card]:
        """Fallback 机制：确保没有空白区域"""
        # 检查是否有 chart 类型缺失
        has_line = any(c.chart_type and 'line' in c.chart_type for c in cards)
        has_bar = any(c.chart_type and 'bar' in c.chart_type for c in cards)
        has_pie = any(c.chart_type and 'pie' in c.chart_type for c in cards)

        analysis_type = package.get('analysis_type', '')

        # 如果是趋势分析但没有折线图 → 注入 fallback
        if analysis_type in ('trend_analysis', 'growth_analysis') and not has_line:
            cards.append(Card(
                type='fallback',
                title='趋势概览',
                priority=3,
                size='s',
                data={'hint': '当前数据未检测到趋势图，建议运行趋势分析'},
                fallback_chain=[
                    {'type': 'bar', 'hint': '可用柱状图替代趋势展示'},
                    {'type': 'table', 'hint': '可用数据表格展示'},
                    {'type': 'insight', 'hint': '可用文字洞察补充'},
                ],
            ))

        # 如果是分布分析但没有饼图 → 注入 fallback
        if analysis_type in ('distribution_analysis',) and not has_pie:
            cards.append(Card(
                type='fallback',
                title='结构概览',
                priority=3,
                size='s',
                data={'hint': '当前数据未检测到分布图，建议运行分布分析'},
            ))

        # 如果没有洞察卡片 → 注入默认洞察
        has_insight = any(c.type == 'insight' for c in cards)
        if not has_insight:
            cards.append(Card(
                type='insight',
                title='提示',
                priority=2,
                size='s',
                data={'text': '此分析暂无深度洞察，建议结合业务背景解读', 'is_hint': True},
            ))

        return cards

    def _estimate_data_quality(self, package: dict) -> float:
        """估计数据质量"""
        kpis = package.get('rendered_kpis', package.get('kpis', []))
        charts = package.get('rendered_charts', package.get('charts', []))
        tables = package.get('rendered_tables', package.get('tables', []))

        score = 0
        if kpis:
            score += min(len(kpis) / 3.0, 1.0) * 0.4
        if charts:
            score += min(len(charts) / 2.0, 1.0) * 0.3
        if tables:
            score += min(len(tables) / 2.0, 1.0) * 0.3
        return round(min(score, 1.0), 2)

    def _card_to_dict(self, card: Card) -> dict:
        return {
            'id': card.id,
            'type': card.type,
            'title': card.title,
            'priority': card.priority,
            'size': card.size,
            'score': card.score,
            'data': card.data,
            'chart_type': card.chart_type,
            'fallback_chain': card.fallback_chain,
        }
