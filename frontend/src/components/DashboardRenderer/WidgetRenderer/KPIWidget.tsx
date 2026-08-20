import React, { memo } from 'react';
import * as echarts from 'echarts';
import type { WidgetSlot } from '../../../types/dashboard';
import { useDashboardTheme } from '../ThemeProvider';
import { buildSparklineConfig } from '../ChartConfigBuilder';
import { useWidgetAnimation } from '../hooks';
import { EtherealMetricCard } from '../../EtherealCharts/EtherealMetricCard';
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

/**
 * KPIWidget —— 核心数字指标
 *
 * 渲染策略：
 * 1. 默认走仙气粉彩渐变卡片 EtherealMetricCard（项目标准大屏风格）
 * 2. hasSparkline 为 true 时，在 EtherealMetricCard 下方追加 ECharts mini sparkline
 *    （这样能保留趋势小图的同时享受渐变背景，不丢任何视觉特性）
 */
export const KPIWidget: React.FC<KPIWidgetProps> = memo(({ widget, onClick, highlightLabel }) => {
  const theme = useDashboardTheme();
  const chartRef = React.useRef<HTMLDivElement>(null);

  const { ref: animRef, animationClass, animationStyle } = useWidgetAnimation({
    type: 'scale-in',
    delay: (widget.importance_score % 5) * 50,
  });

  const data = (widget.chart_config?.data as number[] | undefined);
  const change = (widget.metadata?.change as number) ?? 0;
  const label = (widget.metadata?.kpi_label as string) ?? '';
  const value =
    (widget.metadata?.formatted as string) ||
    (widget.metadata?.value as string) ||
    '';

  const TrendIcon = change > 0 ? FiTrendingUp : change < 0 ? FiTrendingDown : FiMinus;
  const trendColor = change > 0 ? 'text-emerald-500' : change < 0 ? 'text-rose-500' : 'text-slate-600';

  const isHighlighted = highlightLabel === widget.title || highlightLabel === label;

  // ★ 兜底：value 不要回退到 title（之前会把"客户复购率如何"当 value 显示）
  const hasValue = value && value !== '0' && value !== '0%' && value !== '0.0' && value !== '0.0%';
  const hasSparkline = Array.isArray(data) && data.length > 0;
  const numericValue = hasValue ? Number(String(value).replace(/[^\d.\-]/g, '')) : NaN;

  // Sparkline（ECharts mini，保留趋势小图）
  React.useEffect(() => {
    if (!chartRef.current || !hasSparkline) return;
    const chart = echarts.init(chartRef.current);
    chart.setOption(
      buildSparklineConfig(
        theme,
        data!,
        change >= 0 ? theme.palette.success : theme.palette.danger,
      ),
    );
    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(chartRef.current);
    return () => {
      chart.dispose();
      ro.disconnect();
    };
  }, [data, theme, change, hasSparkline]);

  // 走仙气粉彩渐变卡片（与 Ethereal*Chart 风格一致）
  if (!hasSparkline) {
    return (
      <div ref={animRef}
        className={`${animationClass} ${isHighlighted ? 'ring-1 ring-[var(--db-accent)]/30' : ''}`}
        style={animationStyle}
        onClick={() => onClick?.(widget.widget_id, {})}
      >
        <EtherealMetricCard
          metricData={{
            title: widget.title,
            label: label || undefined,
            value: hasValue ? (Number.isFinite(numericValue) ? numericValue : String(value)) : '--',
            change: change ? (change >= 0 ? `+${change.toFixed(1)}%` : `${change.toFixed(1)}%`) : undefined,
            unit: (widget.metadata?.unit as string | undefined),
          }}
        />
      </div>
    );
  }

  // 保留 Sparkline：外层主题色 + 仙气卡（兼容趋势型 KPI）
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
