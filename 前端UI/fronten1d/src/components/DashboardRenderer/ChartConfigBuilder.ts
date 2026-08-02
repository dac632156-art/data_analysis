import type { DashboardTheme } from '../../types/dashboard';

/**
 * ChartStyleEngine —— 统一的 ECharts 配置构建器（来自 Theme Engine）
 *
 * ★ 所有颜色统一从传入的 `theme`（Galaxy Executive Dashboard / theme/ 模块）读取，
 *   禁止任何写死颜色。新增主题（Light / Finance / Operations）时，只要 theme 对象变化，
 *   本文件无需任何改动。
 *
 * 保证整个 Dashboard 的图表风格一致：
 * - 统一颜色（Line / Bar / Pie / Scatter / Radar 全部走 theme.chart）
 * - 统一 Legend / Tooltip / Grid / Axis 样式
 * - 统一动画（cubicOut）
 * - 统一字体 / 圆角 / Padding
 */

/** 统一的 ECharts 基础配置 */
export function buildChartBaseConfig(
  theme: DashboardTheme,
  title: string,
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  const p = theme.palette;
  const c = theme.chart;
  return {
    title: {
      text: title,
      textStyle: {
        color: p.textPrimary,
        fontSize: 14,
        fontWeight: 600,
        fontFamily: theme.fontFamily,
      },
      left: 0,
      top: 0,
    },
    tooltip: {
      backgroundColor: c.tooltip.background,
      borderColor: c.tooltip.border,
      textStyle: {
        color: c.tooltip.content,
        fontSize: 12,
        fontFamily: theme.fontFamily,
      },
      borderWidth: 1,
      padding: [8, 12],
      extraCssText: `border-radius: ${theme.borderRadius}; box-shadow: ${theme.shadow};`,
      ...((overrides.tooltip as object) || {}),
    },
    legend: {
      textStyle: {
        color: c.legend,
        fontSize: 11,
        fontFamily: theme.fontFamily,
      },
      icon: 'roundRect',
      itemWidth: 12,
      itemHeight: 8,
      itemGap: 16,
      ...((overrides.legend as object) || {}),
    },
    grid: {
      left: 0,
      right: 16,
      top: 40,
      bottom: 8,
      containLabel: true,
      ...((overrides.grid as object) || {}),
    },
    animation: true,
    animationDuration: theme.animationDuration,
    animationEasing: 'cubicOut',
    animationDelay: 0,
    progressive: 200,
    progressiveThreshold: 1000,
    color: theme.chartColors,
    backgroundColor: 'transparent',
    ...overrides,
  };
}

/** 统一的坐标轴样式 */
export function buildAxisStyle(theme: DashboardTheme): Record<string, unknown> {
  const c = theme.chart;
  return {
    axisLine: { lineStyle: { color: c.grid } },
    axisTick: { show: false },
    axisLabel: {
      color: c.axis,
      fontSize: 10,
      fontFamily: theme.fontFamily,
    },
    splitLine: {
      lineStyle: {
        color: c.grid,
        type: 'dashed' as const,
      },
    },
  };
}

/** 统一的 KPI sparkline 配置 */
export function buildSparklineConfig(
  theme: DashboardTheme,
  data: number[],
  color?: string,
): Record<string, unknown> {
  const p = theme.palette;
  const c = theme.chart;
  const lineColor = color || p.primary;
  const areaTop = `${lineColor}40`;
  const areaBottom = `${lineColor}05`;
  return {
    grid: { left: 0, right: 0, top: 4, bottom: 0 },
    xAxis: { show: false, data: data.map((_, i) => i) },
    yAxis: { show: false },
    series: [{
      type: 'line',
      data,
      smooth: true,
      showSymbol: false,
      lineStyle: { color: lineColor, width: 1.5 },
      areaStyle: {
        color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: areaTop },
            { offset: 1, color: areaBottom },
          ],
        },
      },
      animationDuration: theme.animationDuration,
      animationEasing: 'cubicOut',
    }],
  };
}

/** 统一的饼图/环形图样式 */
export function buildPieStyle(theme: DashboardTheme): Record<string, unknown> {
  const p = theme.palette;
  const c = theme.chart;
  return {
    itemStyle: {
      borderRadius: 6,
      borderColor: p.pageBg,
      borderWidth: 2,
    },
    label: {
      color: c.legend,
      fontSize: 11,
      fontFamily: theme.fontFamily,
    },
    emphasis: {
      scaleSize: 12,
      itemStyle: {
        shadowBlur: 20,
        shadowColor: c.emphasisGlow,
      },
    },
  };
}

/** 统一的雷达图样式 */
export function buildRadarStyle(theme: DashboardTheme): Record<string, unknown> {
  const c = theme.chart;
  return {
    radar: {
      axisLine: { lineStyle: { color: c.radar.axis } },
      splitLine: { lineStyle: { color: c.radar.split } },
      splitArea: { areaStyle: { color: [c.radar.area, 'transparent'] } },
      axisName: { color: c.legend, fontSize: 10, fontFamily: theme.fontFamily },
    },
  };
}

/** chart_type → 高度映射 */
export function chartTypeToHeight(chartType: string | null, sizeClass: string): string {
  if (chartType === 'map' || chartType === 'map_3d') return '400px';
  if (chartType === 'radar') return '300px';
  if (chartType === 'gauge') return '240px';
  if (chartType === 'treemap') return '280px';
  if (chartType === 'funnel') return '280px';
  if (chartType === 'heatmap') return '300px';
  const map: Record<string, string> = {
    hero: '400px', large: '320px', medium: '260px', small: '200px',
  };
  return map[sizeClass] || '260px';
}

/** chart_type → ECharts series.type 映射 */
export function chartTypeToSeriesType(chartType: string | null): string {
  const map: Record<string, string> = {
    line: 'line', bar: 'bar', pie: 'pie', scatter: 'scatter',
    radar: 'radar', heatmap: 'heatmap', treemap: 'treemap',
    funnel: 'funnel', waterfall: 'bar', gauge: 'gauge',
    area: 'line', bubble: 'scatter', histogram: 'bar',
    boxplot: 'boxplot', map: 'map', map_3d: 'map3D',
  };
  return map[chartType || ''] || 'bar';
}

/** 是否为 3D GL 类型 */
export function isGLChartType(chartType: string | null): boolean {
  const glTypes = ['map_3d', 'scatter3D', 'bar3D', 'line3D', 'lines3D', 'surface'];
  return glTypes.includes(chartType || '');
}
