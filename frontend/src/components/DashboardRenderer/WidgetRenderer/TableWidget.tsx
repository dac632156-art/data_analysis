import React, { memo, useMemo } from 'react';
import type { WidgetSlot } from '../../../types/dashboard';
import { useDashboardTheme } from '../ThemeProvider';
import { useWidgetAnimation } from '../hooks';
import { EtherealTable } from '../../EtherealCharts/EtherealTable';

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

/**
 * TableWidget —— 表格组件
 *
 * 设计原则：项目里所有表格都走仙气粉彩 EtherealTable，
 * 与仙气图表同主题；保留 Cross Filter 高亮在底层兼容。
 */
export const TableWidget: React.FC<TableWidgetProps> = memo(({ widget }) => {
  const theme = useDashboardTheme();

  const { ref: animRef, animationClass, animationStyle } = useWidgetAnimation({
    type: 'fade-in',
    delay: (widget.importance_score % 5) * 60,
  });

  const columns = (widget.chart_config?.columns as string[]) || [];
  const rows = (widget.chart_config?.rows as unknown[]) || [];

  // 兜底：保证传给 EtherealTable 的是它要的 { columns, rows } 结构
  const chartNode = useMemo(() => ({ columns, rows, title: widget.title }), [columns, rows, widget.title]);

  return (
    <div ref={animRef}
      className={`db-transition ${animationClass}`}
      style={animationStyle}
    >
      <EtherealTable chartNode={chartNode} title={widget.title} />
    </div>
  );
});

TableWidget.displayName = 'TableWidget';
