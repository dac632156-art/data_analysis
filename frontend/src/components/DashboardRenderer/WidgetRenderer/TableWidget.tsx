import React, { memo } from 'react';
import type { WidgetSlot } from '../../../types/dashboard';
import { useDashboardTheme } from '../ThemeProvider';
import { useWidgetAnimation } from '../hooks';

interface TableWidgetProps {
  widget: WidgetSlot;
  onFilter?: (field: string, value: string) => void;
  onClick?: (widgetId: string, data: Record<string, unknown>) => void;
  highlightLabel?: string | null;
  isCrossFilterSource?: boolean;
  hasDrillDown?: boolean;
  onDrillDown?: (widgetId: string, dimension: string, nextLevel: string) => void;
}

export const TableWidget: React.FC<TableWidgetProps> = memo(({ widget, highlightLabel }) => {
  const theme = useDashboardTheme();

  const { ref: animRef, animationClass, animationStyle } = useWidgetAnimation({
    type: 'fade-in',
    delay: (widget.importance_score % 5) * 60,
  });

  const columns = (widget.chart_config?.columns as string[]) || [];
  const rows = (widget.chart_config?.rows as Record<string, unknown>[][]) || [];

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
              const isRowHighlighted = highlightLabel && row.some(cell => String(cell ?? '') === highlightLabel);
              return (
                <tr key={ri}
                  className={`hover:bg-white/[0.02] db-transition ${theme.text}
                    ${isRowHighlighted ? 'bg-accent/10 font-semibold' : ''}`}
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
