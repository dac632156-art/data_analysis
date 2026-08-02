import React, { memo, useMemo } from 'react';
import type { WidgetSlot } from '../../../types/dashboard';
import { useDashboardTheme } from '../ThemeProvider';
import { useWidgetAnimation } from '../hooks';

// 列名 → 维度字段分类（与后端 _classify_category_field 对齐，用于筛选高亮列匹配）
const FIELD_KEYWORDS: Record<string, string[]> = {
  region: ['省', '市', '区', '地区', '城市', 'region', 'city', 'area', 'geo', '省份'],
  product: ['产品', '商品', 'product', 'sku', 'item', '品类', '类目', '品牌'],
  channel: ['渠道', '来源', 'channel', 'source', '平台'],
  category: ['类别', '分类', '类型', 'category', 'type'],
  time: ['日期', '时间', '月份', 'date', 'month', 'year'],
};

function classifyField(col: string): string {
  const lower = String(col).toLowerCase();
  for (const [field, kws] of Object.entries(FIELD_KEYWORDS)) {
    if (kws.some(k => lower.includes(k))) return field;
  }
  return '';
}

interface TableWidgetProps {
  widget: WidgetSlot;
  onFilter?: (field: string, value: string) => void;
  onClick?: (widgetId: string, data: Record<string, unknown>) => void;
  highlightLabel?: string | null;
  globalFilterValues?: Record<string, string>;
  isCrossFilterSource?: boolean;
  hasDrillDown?: boolean;
  onDrillDown?: (widgetId: string, dimension: string, nextLevel: string) => void;
}

export const TableWidget: React.FC<TableWidgetProps> = memo(({ widget, highlightLabel, globalFilterValues }) => {
  const theme = useDashboardTheme();

  const { ref: animRef, animationClass, animationStyle } = useWidgetAnimation({
    type: 'fade-in',
    delay: (widget.importance_score % 5) * 60,
  });

  const columns = (widget.chart_config?.columns as string[]) || [];
  const rows = (widget.chart_config?.rows as Record<string, unknown>[][]) || [];

  // ===== 全局筛选器高亮（命中行高亮、其余变淡） =====
  const activeFilters = useMemo(() => {
    const gf = globalFilterValues || {};
    return Object.entries(gf).filter(([, v]) => v) as [string, string][];
  }, [globalFilterValues]);

  // 列名 → 维度字段 → 列索引（仅保留与当前激活筛选器相关的列）
  const fieldColMap = useMemo(() => {
    const map: Record<string, number> = {};
    if (!activeFilters.length) return map;
    columns.forEach((col, i) => {
      const f = classifyField(col);
      if (f && !(f in map)) map[f] = i;
    });
    return map;
  }, [activeFilters, columns]);

  const filterHighlightRows = useMemo(() => {
    const set = new Set<number>();
    if (!activeFilters.length) return set;
    rows.forEach((row, ri) => {
      let relevant = false;
      let allMatch = true;
      for (const [field, value] of activeFilters) {
        const ci = fieldColMap[field];
        if (ci === undefined) continue;
        relevant = true;
        if (String(row[ci] ?? '') !== value) allMatch = false;
      }
      if (relevant && allMatch) set.add(ri);
    });
    return set;
  }, [activeFilters, fieldColMap, rows]);

  const hasRelevantFilter = activeFilters.some(([field]) => field in fieldColMap);

  return (
    <div ref={animRef}
      className={`${theme.cardBg} ${theme.cardBorder} border rounded-xl overflow-hidden
        db-transition ${animationClass} ${theme.shadow}`}
      style={{ borderRadius: theme.borderRadius, ...animationStyle }}
    >
      <div className={`px-4 py-3 border-b ${theme.cardBorder}`}>
        <span className={`text-sm font-semibold ${theme.text}`}>{widget.title}</span>
        <span className={`text-xs ml-2 ${theme.textSecondary}`}>{rows.length} 行</span>
      </div>
      <div className="overflow-x-auto max-h-72">
        <table className="w-full text-xs">
          <thead>
            <tr className={`${theme.cardBg}`}>
              {columns.map((col, i) => (
                <th key={i} className={`px-4 py-2 text-left font-medium ${theme.textSecondary} border-b ${theme.cardBorder}`}>
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, 20).map((row, ri) => {
              const matchedByLabel = highlightLabel && row.some(cell => String(cell ?? '') === highlightLabel);
              const isRowHighlighted = Boolean(matchedByLabel) || filterHighlightRows.has(ri);
              const dimmed = hasRelevantFilter && !isRowHighlighted;
              return (
                <tr key={ri}
                  className={`hover:bg-white/[0.02] db-transition ${theme.text}
                    ${isRowHighlighted ? 'bg-accent/10 font-semibold' : ''}
                    ${dimmed ? 'opacity-40' : ''}`}
                >
                  {row.map((cell, ci) => (
                    <td key={ci} className="px-4 py-1.5 border-b border-white/[0.02]">
                      {String(cell ?? '—')}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
        {rows.length > 20 && (
          <div className={`text-center py-2 text-xs ${theme.textSecondary}`}>
            仅显示前 20 行，共 {rows.length} 行
          </div>
        )}
      </div>
    </div>
  );
});

TableWidget.displayName = 'TableWidget';
