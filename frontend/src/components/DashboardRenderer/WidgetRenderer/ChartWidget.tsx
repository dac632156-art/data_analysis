import React, { memo, useRef, useEffect, useMemo, useCallback } from 'react';
import * as echarts from 'echarts';
import 'echarts-gl';
import type { WidgetSlot } from '../../../types/dashboard';
import { useDashboardTheme } from '../ThemeProvider';
import { buildChartBaseConfig, buildAxisStyle, buildPieStyle, buildRadarStyle, chartTypeToHeight, isGLChartType } from '../ChartConfigBuilder';
import { useLazyLoad } from '../hooks';

interface ChartWidgetProps {
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
 * ChartWidget —— 通用图表渲染组件
 *
 * 支持 line / bar / pie / scatter / radar / heatmap / treemap / funnel / gauge / map / map_3d 等
 * 绑定 Cross Filter（click → 联动）
 * 绑定 Highlight（hover → 联动高亮）
 * 绑定 Drill Down（click → 下钻提示）
 * 使用 LazyLoad（首次进入可视区后才渲染 ECharts）
 */

// ===== Highlight 淡化参数 =====
const DIM_OPACITY = 0.15;

function applyHighlightBlur(
  option: Record<string, unknown>,
  highlightLabels: string[]
): Record<string, unknown> {
  if (highlightLabels.length === 0) return option;
  const result = { ...option };
  const originalSeries = (result.series as Array<Record<string, unknown>>) || [];

  result.series = originalSeries.map((s) => {
    const sType = String(s.type || 'bar');
    // 3D 类型跳过
    if (['map3D', 'bar3D', 'scatter3D', 'lines3D', 'line3D', 'surface'].includes(sType)) {
      return s;
    }

    // 查找匹配的数据项
    const data = (s.data as unknown[]) || [];
    const matchingIndices: number[] = [];

    // 饼图 / treemap: data[i].name 匹配
    if (sType === 'pie' || sType === 'treemap') {
      data.forEach((d, i) => {
        if (typeof d === 'object' && d !== null && !Array.isArray(d)) {
          if (highlightLabels.includes(String((d as Record<string, unknown>).name || ''))) matchingIndices.push(i);
        }
      });
    } else {
      // 柱状/折线/散点: xAxis.data 类目匹配 + series.name 匹配
      const xAxisArr = option.xAxis as Array<Record<string, unknown>> | undefined;
      const xAxis = xAxisArr?.[0] || (option.xAxis as Record<string, unknown>);
      const xData = (xAxis?.data as string[]) || undefined;
      const sName = String(s.name || '');

      if (highlightLabels.includes(sName)) {
        // 系列名完全匹配 → 整个系列高亮
        return {
          ...s,
          lineStyle: { ...(s.lineStyle as object), width: 3, opacity: 1 },
          itemStyle: { ...(s.itemStyle as object), opacity: 1 },
        };
      }

      if (xData) {
        xData.forEach((cat, i) => {
          if (highlightLabels.includes(String(cat)) && i < data.length) matchingIndices.push(i);
        });
      }
    }

    if (matchingIndices.length > 0) {
      // 匹配点增强 + 非匹配点淡化
      const newData = data.map((d, i) => {
        const isMatch = matchingIndices.includes(i);
        const opacity = isMatch ? 1 : DIM_OPACITY;
        if (Array.isArray(d)) return { value: [...(d as unknown[])], itemStyle: { opacity } };
        if (typeof d === 'object' && d !== null) return { ...(d as Record<string, unknown>), itemStyle: { opacity } };
        return { value: d, itemStyle: { opacity } };
      });
      return { ...s, data: newData };
    } else {
      // 无匹配 → 整个 series 淡化
      return { ...s, itemStyle: { ...(s.itemStyle as object), opacity: DIM_OPACITY } };
    }
  });

  return result;
}

export const ChartWidget: React.FC<ChartWidgetProps> = memo(({ widget, onFilter, onClick, highlightLabel, globalFilterValues, isCrossFilterSource, hasDrillDown, onDrillDown }) => {
  const theme = useDashboardTheme();
  const accent = theme.palette.primary;
  const chartRef = useRef<HTMLDivElement>(null);
  const instanceRef = useRef<echarts.ECharts | null>(null);
  const isFirstRender = useRef(true);  // 首次渲染标记

  // LazyLoad：只在可视区才初始化 ECharts
  const { ref: lazyRef, shouldRender } = useLazyLoad<HTMLDivElement>();

  // 合并 chart_config.option 为完整 ECharts option
  const mergedOption = useMemo(() => {
    const rawOption = widget.chart_config?.option as Record<string, unknown>;
    if (!rawOption || Object.keys(rawOption).length === 0) {
      return null;  // 标记无数据，渲染占位
    }

    const chartType = widget.chart_type || 'bar';
    // 词云已从后端分析能力移除：任何来源的词云 widget 均不渲染（显示占位）
    if (chartType === 'wordcloud') return null;
    const axis = buildAxisStyle(theme);
    const base = buildChartBaseConfig(theme, widget.title);

    // 针对不同图表类型叠加专用样式
    let styledOption: Record<string, unknown>;
    if (chartType === 'pie') {
      const pieStyle = buildPieStyle(theme);
      styledOption = { ...base, ...pieStyle, ...rawOption };
    } else if (chartType === 'radar') {
      const radarStyle = buildRadarStyle(theme);
      styledOption = { ...base, ...radarStyle, ...rawOption };
    } else {
      styledOption = {
        ...base,
        ...rawOption,
        xAxis: rawOption.xAxis
          ? (Array.isArray(rawOption.xAxis) ? rawOption.xAxis.map(xa => ({ ...axis, ...xa })) : { ...axis, ...rawOption.xAxis })
          : { ...axis, type: 'category' },
        yAxis: rawOption.yAxis
          ? (Array.isArray(rawOption.yAxis) ? rawOption.yAxis.map(ya => ({ ...axis, ...ya })) : { ...axis, ...rawOption.yAxis })
          : { ...axis, type: 'value' },
      };
    }

    // 应用 Highlight（Cross Filter / Hover + 全局筛选器高亮）
    // 合并 Cross Filter 单一标签与全局筛选器命中值，统一高亮
    const filterLabels: string[] = [];
    const gf = globalFilterValues || {};
    const dimValues = (widget.chart_config?.dim_values || {}) as Record<string, string[]>;
    for (const [field, value] of Object.entries(gf)) {
      if (value && Array.isArray(dimValues[field]) && dimValues[field].includes(value)) {
        filterLabels.push(value);
      }
    }
    const effectiveLabels = [
      ...(highlightLabel ? [highlightLabel] : []),
      ...filterLabels,
    ].filter(Boolean);
    if (effectiveLabels.length > 0) {
      styledOption = applyHighlightBlur(styledOption, effectiveLabels);
    }

    return styledOption;
  }, [widget, theme, highlightLabel, globalFilterValues]);

  // 初始化 + 绑定事件
  useEffect(() => {
    if (!shouldRender || !chartRef.current || !mergedOption) return;

    const el = chartRef.current;
    const isGL = isGLChartType(widget.chart_type);
    let chart = instanceRef.current;

    // 2D→3D 切换时需要重新初始化
    if (chart && (chart as any)._isGL !== isGL) {
      chart.dispose();
      chart = null;
    }

    if (!chart) {
      chart = echarts.init(el, undefined, { renderer: 'canvas' });
      instanceRef.current = chart;
      (chart as any)._isGL = isGL;

      // ★ Cross Filter 绑定：只有配置了才会绑定
      if (isCrossFilterSource) {
        chart.on('click', (params: Record<string, unknown>) => {
          const label = String(params.name || params.seriesName || '');
          if (label && label !== 'undefined') {
            window.dispatchEvent(new CustomEvent('dashboard:cross-filter', {
              detail: { widgetId: widget.widget_id, label },
            }));
          }
        });
      }

      // ★ Hover：只显示 ECharts 原生 tooltip，不触发跨图表联动
      //   跨图表 hover 联动会导致 7 个图表同时 flash/redraw，页面抖动
    }

    try {
      // ★ 首次渲染用 notMerge: true（chart 为空，需全量设置）
      // ★ 后续 highlight 更新用 notMerge: false（平滑过渡，避免闪烁和交互丢失）
      const notMerge = isFirstRender.current;
      chart.setOption(mergedOption, { notMerge });
      isFirstRender.current = false;
    } catch (err) {
      console.error(`[ChartWidget] ${widget.widget_id} setOption 失败:`, err);
    }

    // ResizeObserver
    const ro = new ResizeObserver(() => chart?.resize());
    ro.observe(el);
    return () => {
      ro.disconnect();
    };
  }, [shouldRender, mergedOption, widget, isCrossFilterSource, hasDrillDown]);

  // 销毁
  useEffect(() => {
    return () => {
      instanceRef.current?.dispose();
      instanceRef.current = null;
    };
  }, []);

  // Drill Down 触发
  const handleDrillDownClick = useCallback(() => {
    // 从 DrillDownMap 中查找（简化实现，直接从 widget.metadata 取）
    const ddInfo = widget.metadata?.drill_down as { dimension: string; next_level: string } | undefined;
    if (ddInfo) {
      onDrillDown?.(widget.widget_id, ddInfo.dimension, ddInfo.next_level);
    }
  }, [widget, onDrillDown]);

  const height = chartTypeToHeight(widget.chart_type, widget.size_class);

  if (!shouldRender) {
    // 懒加载占位
    return (
      <div ref={lazyRef}
        className={`${theme.cardBg} ${theme.cardBorder} border rounded-xl`}
        style={{ height, padding: theme.cardPadding }}
      />
    );
  }

  // 无数据占位：chart_config 为空时显示提示，而不是空白
  if (!mergedOption) {
    return (
      <div ref={lazyRef}
        className={`${theme.cardBg} ${theme.cardBorder} border rounded-xl animate-db-scale-in ${theme.shadow}
          flex flex-col items-center justify-center gap-2`}
        style={{
          padding: theme.cardPadding,
          borderRadius: theme.borderRadius,
          height,
        }}
      >
        <div className="text-2xl opacity-30">📊</div>
        <p className={`text-xs ${theme.textSecondary}`}>{widget.title}</p>
        <p className={`text-[10px] opacity-50 ${theme.textSecondary}`}>暂无图表数据</p>
      </div>
    );
  }

  return (
    <div ref={lazyRef}
      className={`${theme.cardBg} ${theme.cardBorder} border rounded-xl db-transition
        animate-db-scale-in hover:border-opacity-100 ${theme.shadow}`}
      style={{
        padding: theme.cardPadding,
        borderRadius: theme.borderRadius,
        animationDelay: `${(widget.importance_score % 5) * 50}ms`,
      }}
    >
      {/* Drill Down 提示 */}
      {hasDrillDown && (
        <button onClick={handleDrillDownClick}
          className={`absolute top-2 right-2 text-xs px-1.5 py-0.5 rounded
            bg-[var(--db-accent)]/10 text-[var(--db-accent)] border border-[var(--db-accent)]/20
            hover:bg-[var(--db-accent)]/20 transition-colors z-10`}
          title="下钻分析"
        >
          ↓ 下钻
        </button>
      )}
      <div ref={chartRef} className="w-full" style={{ height }} />
      {/* 图表文字说明：解释该图含义（空值兜底不渲染） */}
      {widget.description ? (
        <p className={`mt-2 text-xs leading-relaxed ${theme.textSecondary} opacity-80`}>
          {widget.description}
        </p>
      ) : null}
    </div>
  );
});

ChartWidget.displayName = 'ChartWidget';
