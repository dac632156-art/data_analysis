import React, { memo, useRef, useEffect, useState } from 'react';
import * as echarts from 'echarts';
import type { WidgetSlot } from '../../../types/dashboard';
import { useDashboardTheme } from '../ThemeProvider';
import { buildSparklineConfig } from '../ChartConfigBuilder';
import { useWidgetAnimation } from '../hooks';
import { FiTrendingUp, FiTrendingDown, FiMinus } from 'react-icons/fi';

interface KPIWidgetProps {
  widget: WidgetSlot;
  onFilter?: (field: string, value: string) => void;
  onClick?: (widgetId: string, data: Record<string, unknown>) => void;
  highlightLabel?: string | null;
  isCrossFilterSource?: boolean;
  hasDrillDown?: boolean;
  onDrillDown?: (widgetId: string, dimension: string, nextLevel: string) => void;
}

export const KPIWidget: React.FC<KPIWidgetProps> = memo(({ widget, onClick, highlightLabel }) => {
  const theme = useDashboardTheme();
  const chartRef = useRef<HTMLDivElement>(null);

  // Animation
  const { ref: animRef, animationClass, animationStyle } = useWidgetAnimation({
    type: 'scale-in',
    delay: (widget.importance_score % 5) * 50,
  });

  const data = widget.chart_config?.data as number[] | undefined;
  const change = (widget.metadata?.change as number) ?? 0;
  const label = (widget.metadata?.kpi_label as string) ?? '';
  const value = (widget.metadata?.formatted as string) ?? (widget.metadata?.value as string) ?? '';

  const TrendIcon = change > 0 ? FiTrendingUp : change < 0 ? FiTrendingDown : FiMinus;
  const trendColor = change > 0 ? 'text-emerald-500' : change < 0 ? 'text-rose-500' : 'text-slate-600';

  // 是否应该高亮（如果 highlightLabel 匹配 KPI 名称）
  const isHighlighted = highlightLabel === widget.title || highlightLabel === label;

  // ★ 修复：value 兜底不要回退到 title（之前会把"客户复购率如何"当 value 显示）
  // 无数据时显示 "—"，有数据时显示数值 + 副标签（label 仅作副标题）
  const hasValue = value && value !== '0' && value !== '0%' && value !== '0.0' && value !== '0.0%';
  const hasSparkline = data && data.length > 0;

  useEffect(() => {
    if (!chartRef.current || !hasSparkline) return;
    const chart = echarts.init(chartRef.current);
    chart.setOption(buildSparklineConfig(theme, data, change >= 0 ? theme.palette.success : theme.palette.danger));
    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(chartRef.current);
    return () => { chart.dispose(); ro.disconnect(); };
  }, [data, theme, change, hasSparkline]);

  return (
    <div ref={animRef}
      className={`${theme.cardBg} ${theme.cardBorder} border rounded-xl p-4
        cursor-pointer db-transition ${animationClass} ${theme.shadow}
        ${isHighlighted ? 'border-[var(--db-accent)] ring-1 ring-[var(--db-accent)]/30' : ''}`}
      style={{
        borderRadius: theme.borderRadius,
        padding: theme.cardPadding,
        ...animationStyle,
      }}
      onClick={() => onClick?.(widget.widget_id, {})}
    >
      <div className="flex items-start justify-between mb-1">
        <span className={`text-xs font-medium ${theme.textSecondary}`}>{widget.title}</span>
        {change !== 0 && (
          <span className={`flex items-center gap-0.5 text-xs font-semibold ${trendColor}`}>
            <TrendIcon className="w-3 h-3" />
            {change > 0 ? '+' : ''}{change.toFixed(1)}%
          </span>
        )}
      </div>
      {hasValue ? (
        <div className={`text-2xl font-bold ${theme.text} tabular-nums`}>
          {value}
        </div>
      ) : (
        <div className={`text-2xl font-bold opacity-30 tabular-nums ${theme.text}`}>
          —
        </div>
      )}
      {label && label !== widget.title && (
        <div className={`text-[10px] mt-0.5 ${theme.textSecondary}`}>{label}</div>
      )}
      {hasSparkline ? (
        <div ref={chartRef} className="w-full h-10 mt-1" />
      ) : hasValue ? (
        <div className={`text-[10px] mt-1 ${theme.textSecondary}`}>数据完整度低</div>
      ) : null}
    </div>
  );
});

KPIWidget.displayName = 'KPIWidget';
