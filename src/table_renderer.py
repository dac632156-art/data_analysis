"""
TableRenderer —— 统一表格渲染层

输入 TableData → 输出前端可直接消费的结构化表格数据。
支持六种表格类型：summary / ranking / cross / growth / correlation / detail / exception
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from src.analysis_templates.base import TableData


@dataclass
class RenderedCell:
    value: Any
    highlight: bool = False       # 高亮标记
    color: str | None = None      # 文字颜色（如红涨绿跌）


@dataclass
class RenderedTable:
    title: str
    table_type: str
    columns: List[str] = field(default_factory=list)
    rows: List[List[RenderedCell]] = field(default_factory=list)
    sortable: bool = True
    highlight_col: Optional[int] = None  # 哪一列需要颜色标记


class TableRenderer:
    """统一表格渲染器"""

    def render(self, table_data: TableData) -> RenderedTable:
        """将 TableData 转换为 RenderedTable"""
        table_type = table_data.table_type
        columns = table_data.columns
        raw_rows = table_data.rows

        # 根据表格类型应用不同的渲染规则
        if table_type == "growth":
            return self._render_growth(table_data)
        elif table_type == "ranking":
            return self._render_ranking(table_data)
        elif table_type == "summary":
            return self._render_generic(table_data)
        elif table_type == "correlation":
            return self._render_correlation(table_data)
        elif table_type == "exception":
            return self._render_exception(table_data)
        else:
            return self._render_generic(table_data)

    def _render_generic(self, td: TableData) -> RenderedTable:
        rows = [[RenderedCell(value=v) for v in row] for row in td.rows]
        return RenderedTable(
            title=td.title,
            table_type=td.table_type,
            columns=td.columns,
            rows=rows,
        )

    def _render_growth(self, td: TableData) -> RenderedTable:
        """增长率表格：正增长率绿色，负增长率红色"""
        rows = []
        for row in td.rows:
            cells = []
            for i, val in enumerate(row):
                cell = RenderedCell(value=val)
                # 增长率列通常在第3列（index=2）或有"率"字的列
                if i >= 2 and isinstance(val, (int, float)):
                    cell.color = "#10B981" if val > 0 else "#EF4444" if val < 0 else None
                cells.append(cell)
            rows.append(cells)
        return RenderedTable(
            title=td.title,
            table_type=td.table_type,
            columns=td.columns,
            rows=rows,
            highlight_col=2,
        )

    def _render_ranking(self, td: TableData) -> RenderedTable:
        """排名表格：第一行高亮"""
        rows = []
        for idx, row in enumerate(td.rows):
            cells = [RenderedCell(value=v, highlight=(idx == 0)) for v in row]
            rows.append(cells)
        return RenderedTable(
            title=td.title,
            table_type=td.table_type,
            columns=td.columns,
            rows=rows,
        )

    def _render_correlation(self, td: TableData) -> RenderedTable:
        """相关矩阵表格：绝对值>0.7 高亮"""
        rows = []
        for row in td.rows:
            cells = []
            for j, val in enumerate(row):
                highlight = False
                if j > 0 and isinstance(val, (int, float)):
                    highlight = abs(val) > 0.7
                cells.append(RenderedCell(value=val, highlight=highlight))
            rows.append(cells)
        return RenderedTable(
            title=td.title,
            table_type=td.table_type,
            columns=td.columns,
            rows=rows,
            sortable=False,
        )

    def _render_exception(self, td: TableData) -> RenderedTable:
        """异常表格：全部高亮"""
        rows = [[RenderedCell(value=v, highlight=True) for v in row] for row in td.rows]
        return RenderedTable(
            title=td.title,
            table_type=td.table_type,
            columns=td.columns,
            rows=rows,
        )

    def render_all(self, table_data_list: List[TableData]) -> List[RenderedTable]:
        """批量渲染"""
        return [self.render(td) for td in table_data_list]
