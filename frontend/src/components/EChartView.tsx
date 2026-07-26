/* EChartView - ECharts 图表渲染组件（option-based 联动高亮 + 3D GL 支持） */
import React, { useEffect, useRef, useMemo } from 'react';
import * as echarts from 'echarts/core';
import {
  BarChart, LineChart, PieChart, ScatterChart, EffectScatterChart, RadarChart,
  TreemapChart, BoxplotChart, HeatmapChart, CustomChart,
} from 'echarts/charts';
import {
  TitleComponent, TooltipComponent, GridComponent, LegendComponent,
  ToolboxComponent, DataZoomComponent, VisualMapComponent,
  BrushComponent, MarkLineComponent, MarkPointComponent,
  GeoComponent,  // ★ 2D 地图组件
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
// ★ Theme Engine（Single Source of Truth for colors）
import { theme as GALAXY_THEME } from '../theme';
// ★ echarts-gl 3D 扩展
import 'echarts-gl';

echarts.use([
  BarChart, LineChart, PieChart, ScatterChart, EffectScatterChart, RadarChart,
  TreemapChart, BoxplotChart, HeatmapChart, CustomChart,
  TitleComponent, TooltipComponent, GridComponent, LegendComponent,
  ToolboxComponent, DataZoomComponent, VisualMapComponent,
  BrushComponent, MarkLineComponent, MarkPointComponent,
  GeoComponent,
  CanvasRenderer,
]);

// 中国地图 GeoJSON：优先本地 public/china.json（582KB，自部署避免跨域/网络问题），
// 加载失败时降级到阿里云 DataV。
const CHINA_GEO_LOCAL = '/china.json';
const CHINA_GEO_URL = 'https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json';

// ★ 统一强调色（来自 theme/ Theme Engine，禁止写死）
const EMPHASIS_GLOW = GALAXY_THEME.chart.emphasisGlow; // 银河紫辉光（图表 hover 强调）
const EMPHASIS_BORDER = '#A78BFA'; // 银河紫（极光青边框改为紫色强调）
// 地图是否已注册
let chinaMapRegistered = false;
let chinaMapLoading: Promise<void> | null = null;

/** 确保中国地图 GeoJSON 已注册到 ECharts */
function ensureChinaMapRegistered(): Promise<void> {
  if (chinaMapRegistered) return Promise.resolve();
  if (chinaMapLoading) return chinaMapLoading;

  // ★ 优先从本地 public/china.json 加载（避免阿里云跨域/网络问题），失败时降级到 DataV
  const tryLoad = (url: string) =>
    fetch(url).then(r => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    });

  chinaMapLoading = new Promise<void>((resolve) => {
    tryLoad(CHINA_GEO_LOCAL)
      .then(geo => {
        echarts.registerMap('china', geo as any);
        chinaMapRegistered = true;
        resolve();
      })
      .catch(() => {
        // 本地失败时降级到阿里云
        console.warn('[ECharts] 本地 china.json 加载失败，降级到阿里云 DataV');
        return tryLoad(CHINA_GEO_URL)
          .then(geo => {
            echarts.registerMap('china', geo as any);
            chinaMapRegistered = true;
            resolve();
          })
          .catch(() => {
            console.warn('中国地图 GeoJSON 加载失败，地图可能无法显示');
            resolve();
          });
      });
  });
  return chinaMapLoading;
}

export interface EChartsOption {
  [key: string]: unknown;
  series?: Array<Record<string, unknown>>;
}

interface Props {
  option: EChartsOption | null;
  title?: string;
  height?: number;
  hideTitle?: boolean;
  dataIndex?: number;
  groupId?: string;
  highlightLabel?: string | null;
  onHighlight?: (label: string | null) => void;
}

function extractTitle(option: EChartsOption | null): string {
  if (!option) return '';
  return String((option.title as Record<string, unknown>)?.text || '');
}

/** 检测 option 是否需要 WebGL 渲染（3D 图表） */
function needsWebGL(option: EChartsOption | null): boolean {
  if (!option) return false;
  // 检查 geo3D / globe 组件
  if (option.geo3D || option.globe) return true;
  // 检查 series 中的 3D 类型
  const series = (option.series as Array<Record<string, unknown>>) || [];
  const glTypes = ['scatter3D', 'bar3D', 'line3D', 'lines3D', 'surface', 'map3D', 'polygons3D'];
  return series.some((s) => glTypes.includes(String(s.type || '')));
}

/** 检测 option 是否需要中国地图（geo / geo3D / map3D / map 系列） */
function needsChinaMap(option: EChartsOption | null): boolean {
  if (!option) return false;
  // geo / geo3D 组件引用 china 地图
  if ((option.geo as Record<string, unknown>)?.map === 'china') return true;
  if ((option.geo3D as Record<string, unknown>)?.map === 'china') return true;
  if ((option.globe as Record<string, unknown>)?.baseTexture === 'china') return true;
  // 检查 series
  const series = (option.series as Array<Record<string, unknown>>) || [];
  return series.some((s) => {
    const m = s.map;
    return m === 'china' || m === 'china';
  });
}

// ===== 淡化/增强参数 =====
const DIM_OPACITY = 0.15;
const DIM_LINE_OPACITY = 0.15;
const DIM_AREA_OPACITY = 0.03;

// ===== 工具函数 =====

/**
 * ★ 安全包装数据项：正确处理数组 vs 对象 vs 简单值
 * ECharts 支持三种数据格式：
 *  - 简单值: 1200
 *  - 数组: [x, y] 或 [x, y, size]  (散点/气泡/箱线)
 *  - 对象: { name: "a", value: 1200 }
 *
 * 数组绝对不能直接 ...展开（会把索引变成 key，破坏格式）
 */
function wrapDataItem(d: unknown, extraStyle: Record<string, unknown>): unknown {
  if (d === null || d === undefined) {
    return { value: d, itemStyle: { ...extraStyle } };
  }
  if (Array.isArray(d)) {
    // ★ 数组数据（散点/气泡/箱线）→ 包裹为 { value: [...], itemStyle }
    return { value: [...(d as unknown[])], itemStyle: { ...extraStyle } };
  }
  if (typeof d === 'object') {
    // ★ 对象数据（饼图扇区/有 name 的数据项）
    const obj = d as Record<string, unknown>;
    const existingStyle = (obj.itemStyle as Record<string, unknown>) || {};
    return { ...obj, itemStyle: { ...existingStyle, ...extraStyle } };
  }
  // ★ 简单值（柱状图/折线图的数值）
  return { value: d, itemStyle: { ...extraStyle } };
}

/**
 * 为 option 的每个 series 添加 emphasis 样式（hover/click 时的发光视觉反馈）
 */
function enhanceOptionForInteraction(option: EChartsOption): EChartsOption {
  const result: Record<string, unknown> = { ...option, backgroundColor: 'transparent' };
  // ★ 缺省 tooltip 时补一个默认提示，保证悬停可见数据（不覆盖已有 tooltip）
  if (!result.tooltip) {
    const series = (result.series as Array<Record<string, unknown>>) || [];
    const useItem = series.some(s =>
      ['pie', 'map', 'scatter', 'bubble', 'radar', 'treemap'].includes(String(s.type || ''))
    );
    result.tooltip = { trigger: useItem ? 'item' : 'axis', confine: true };
  }
  const originalSeries = (result.series as Array<Record<string, unknown>>) || [];

  result.series = originalSeries.map((s) => {
    const type = String(s.type || 'bar');
    // ★ 3D 类型跳过增强（map3D/bar3D/scatter3D 结构不同）
    if (['map3D', 'bar3D', 'scatter3D', 'lines3D', 'line3D', 'surface'].includes(type)) {
      return s;
    }
    const existingEmphasis = (s.emphasis as Record<string, unknown>) || {};

    let emphasis: Record<string, unknown>;
    if (type === 'pie') {
      emphasis = {
        ...existingEmphasis,
        scaleSize: 15,
        itemStyle: {
          shadowBlur: 25,
          shadowColor: EMPHASIS_GLOW,
          ...(existingEmphasis.itemStyle as Record<string, unknown>),
        },
      };
    } else if (type === 'line' || type === 'area') {
      emphasis = {
        ...existingEmphasis,
        lineStyle: { width: 4 },
        itemStyle: {
          shadowBlur: 15,
          shadowColor: EMPHASIS_GLOW,
          borderWidth: 3,
          borderColor: EMPHASIS_BORDER,
          ...(existingEmphasis.itemStyle as Record<string, unknown>),
        },
      };
    } else if (type === 'radar') {
      emphasis = {
        ...existingEmphasis,
        lineStyle: { width: 4 },
        areaStyle: { opacity: 0.45 },
        itemStyle: {
          shadowBlur: 12,
          shadowColor: EMPHASIS_GLOW,
        },
      };
    } else if (type === 'boxplot') {
      emphasis = {
        ...existingEmphasis,
        itemStyle: {
          shadowBlur: 15,
          shadowColor: EMPHASIS_GLOW,
          borderColor: EMPHASIS_BORDER,
          borderWidth: 2,
          ...(existingEmphasis.itemStyle as Record<string, unknown>),
        },
      };
    } else {
      emphasis = {
        ...existingEmphasis,
        itemStyle: {
          shadowBlur: 20,
          shadowColor: EMPHASIS_GLOW,
          borderColor: EMPHASIS_BORDER,
          borderWidth: 2,
          ...(existingEmphasis.itemStyle as Record<string, unknown>),
        },
      };
    }

    return { ...s, emphasis };
  });

  return result as EChartsOption;
}


// ===================================================================
// ★ 核心：在 option 中查找匹配 highlightLabel 的数据项索引
// ===================================================================

function findMatchingIndices(
  series: Record<string, unknown>,
  option: EChartsOption,
  highlightLabel: string
): number[] {
  const data = (series.data as unknown[]) || [];
  const sName = String(series.name || '');
  const sType = String(series.type || '');

  // 1) 系列名完全匹配 → 整个系列高亮（所有数据点）
  if (sName === highlightLabel) {
    return data.map((_, i) => i);
  }

  const matching: number[] = [];

  // 2) 饼图/树状图: data[i].name 匹配
  if (sType === 'pie' || sType === 'treemap') {
    data.forEach((d, i) => {
      if (typeof d === 'object' && d !== null && !Array.isArray(d)) {
        const name = String((d as Record<string, unknown>).name || '');
        if (name === highlightLabel) matching.push(i);
      }
    });
    return matching;
  }

  // 3) 雷达图: data[i].name 或 series.name 匹配
  if (sType === 'radar') {
    data.forEach((d, i) => {
      if (typeof d === 'object' && d !== null && !Array.isArray(d)) {
        const name = String((d as Record<string, unknown>).name || '');
        if (name === highlightLabel) matching.push(i);
      }
    });
    return matching;
  }

  // 4) 柱状图/折线图/直方图: xAxis.data 类目匹配
  const xAxisArr = option.xAxis as Array<Record<string, unknown>> | undefined;
  const xAxis = xAxisArr?.[0] || (option.xAxis as Record<string, unknown>);
  const xData = (xAxis as Record<string, unknown>)?.data as string[] | undefined;

  if (xData) {
    const matchTypes = ['bar', 'line', 'area', 'histogram', 'boxplot', 'scatter', 'bubble'];
    if (matchTypes.includes(sType)) {
      xData.forEach((cat, i) => {
        if (String(cat) === highlightLabel && i < data.length) matching.push(i);
      });
      return matching;
    }
  }

  // 5) 热力图: x/y 轴类目匹配
  if (sType === 'heatmap') {
    const xMatch = xData ? xData.findIndex(cat => String(cat) === highlightLabel) : -1;
    const yAxisArr = option.yAxis as Array<Record<string, unknown>> | undefined;
    const yAxis = yAxisArr?.[0] || (option.yAxis as Record<string, unknown>);
    const yData = (yAxis as Record<string, unknown>)?.data as string[] | undefined;
    const yMatch = yData ? yData.findIndex(cat => String(cat) === highlightLabel) : -1;

    data.forEach((d, i) => {
      if (Array.isArray(d)) {
        if (xMatch >= 0 && d[0] === xMatch) matching.push(i);
        if (yMatch >= 0 && d[1] === yMatch) matching.push(i);
      }
    });
    return matching;
  }

  // 6) 散点图/气泡图: data[i] 的 name 匹配
  data.forEach((d, i) => {
    if (typeof d === 'object' && d !== null && !Array.isArray(d)) {
      const name = String((d as Record<string, unknown>).name || '');
      if (name === highlightLabel) matching.push(i);
    }
  });

  return matching;
}

// ===================================================================
// ★ option-based 高亮/淡化：数据点级别精细化控制
// ===================================================================

function applyHighlightBlur(
  option: EChartsOption,
  highlightLabel: string
): EChartsOption {
  const result: Record<string, unknown> = { ...option };
  const originalSeries = (result.series as Array<Record<string, unknown>>) || [];

  result.series = originalSeries.map((s) => {
    const sType = String(s.type || '');
    // ★ 3D 类型跳过淡化/高亮
    if (['map3D', 'bar3D', 'scatter3D', 'lines3D', 'line3D', 'surface'].includes(sType)) {
      return s;
    }
    const matchingIndices = findMatchingIndices(s, option, highlightLabel);

    if (matchingIndices.length > 0) {
      return applyDataPointHighlight(s, sType, matchingIndices);
    } else {
      return dimEntireSeries(s, sType);
    }
  });

  return result as EChartsOption;
}

// ===================================================================
// ★ 数据点级别：匹配点增强 + 非匹配点淡化
// ===================================================================

function applyDataPointHighlight(
  series: Record<string, unknown>,
  sType: string,
  matchingIndices: number[]
): Record<string, unknown> {
  // 雷达图 → series 级别增强
  if (sType === 'radar') {
    return {
      ...series,
      lineStyle: {
        ...(series.lineStyle as Record<string, unknown>),
        width: 3, opacity: 1,
      },
      areaStyle: {
        ...(series.areaStyle as Record<string, unknown>),
        opacity: 0.35,
      },
      itemStyle: {
        ...(series.itemStyle as Record<string, unknown>),
        opacity: 1,
      },
      symbolSize: 8,
    };
  }

  // ★ 饼图/环形图/树状图：数据点级别
  if (sType === 'pie' || sType === 'treemap') {
    const data = (series.data as unknown[]) || [];
    return {
      ...series,
      data: data.map((d, i) => {
        const isMatch = matchingIndices.includes(i);
        return wrapDataItem(d, { opacity: isMatch ? 1 : DIM_OPACITY });
      }),
    };
  }

  // ★ 柱状图/直方图：数据点级别
  if (sType === 'bar' || sType === 'histogram') {
    const data = (series.data as unknown[]) || [];
    return {
      ...series,
      data: data.map((d, i) => {
        const isMatch = matchingIndices.includes(i);
        return wrapDataItem(d, { opacity: isMatch ? 1 : DIM_OPACITY });
      }),
    };
  }

  // ★ 折线图/面积图：数据点级别
  if (sType === 'line' || sType === 'area') {
    const data = (series.data as unknown[]) || [];
    const hasAnyMatch = matchingIndices.length > 0;
    return {
      ...series,
      lineStyle: {
        ...(series.lineStyle as Record<string, unknown>),
        opacity: hasAnyMatch ? 0.6 : DIM_LINE_OPACITY,
        width: hasAnyMatch ? 3 : (series.lineStyle as Record<string, unknown>)?.width as number || 2,
      },
      areaStyle: sType === 'area' ? {
        ...(series.areaStyle as Record<string, unknown>),
        opacity: hasAnyMatch ? 0.3 : DIM_AREA_OPACITY,
      } : series.areaStyle,
      data: data.map((d, i) => {
        const isMatch = matchingIndices.includes(i);
        return wrapDataItem(d, { opacity: isMatch ? 1 : 0.3 });
      }),
    };
  }

  // ★ 箱线图：数据点级别
  if (sType === 'boxplot') {
    const data = (series.data as unknown[]) || [];
    return {
      ...series,
      data: data.map((d, i) => {
        const isMatch = matchingIndices.includes(i);
        return wrapDataItem(d, { opacity: isMatch ? 1 : DIM_OPACITY });
      }),
    };
  }

  // ★ 散点图/气泡图：数据点级别
  if (sType === 'scatter' || sType === 'bubble') {
    const data = (series.data as unknown[]) || [];
    return {
      ...series,
      data: data.map((d, i) => {
        const isMatch = matchingIndices.includes(i);
        return wrapDataItem(d, { opacity: isMatch ? 1 : DIM_OPACITY });
      }),
    };
  }

  // ★ 热力图：数据点级别
  if (sType === 'heatmap') {
    const data = (series.data as unknown[]) || [];
    return {
      ...series,
      data: data.map((d, i) => {
        const isMatch = matchingIndices.includes(i);
        if (Array.isArray(d)) {
          return { value: d, itemStyle: { opacity: isMatch ? 1 : DIM_OPACITY } };
        }
        if (typeof d === 'object' && d !== null) {
          return wrapDataItem(d, { opacity: isMatch ? 1 : DIM_OPACITY });
        }
        return d;
      }),
    };
  }

  // 其他类型 → fallback: series 级别增强
  return series;
}

// ===================================================================
// ★ Series 级别：整个 series 淡化（无匹配数据点时）
// ===================================================================

function dimEntireSeries(series: Record<string, unknown>, sType: string): Record<string, unknown> {
  if (sType === 'radar') {
    return {
      ...series,
      lineStyle: {
        ...(series.lineStyle as Record<string, unknown>),
        opacity: DIM_LINE_OPACITY,
      },
      areaStyle: {
        ...(series.areaStyle as Record<string, unknown>),
        opacity: DIM_AREA_OPACITY,
      },
      itemStyle: {
        ...(series.itemStyle as Record<string, unknown>),
        opacity: DIM_OPACITY,
      },
      symbolSize: 3,
    };
  }

  // 饼图/树状图：逐数据项淡化
  if (sType === 'pie' || sType === 'treemap') {
    const data = (series.data as unknown[]) || [];
    return {
      ...series,
      data: data.map((d) => wrapDataItem(d, { opacity: DIM_OPACITY })),
    };
  }

  // 折线图/面积图：series 级别淡化
  if (sType === 'line' || sType === 'area') {
    return {
      ...series,
      lineStyle: {
        ...(series.lineStyle as Record<string, unknown>),
        opacity: DIM_LINE_OPACITY,
      },
      areaStyle: {
        ...(series.areaStyle as Record<string, unknown>),
        opacity: DIM_AREA_OPACITY,
      },
      itemStyle: {
        ...(series.itemStyle as Record<string, unknown>),
        opacity: DIM_OPACITY,
      },
    };
  }

  // ★ 柱状图/直方图/箱线图/散点图/气泡图：逐数据项淡化
  //   → 使用 wrapDataItem 安全处理数组/对象/简单值
  if (['bar', 'histogram', 'boxplot', 'scatter', 'bubble'].includes(sType)) {
    const data = (series.data as unknown[]) || [];
    if (data.length > 0) {
      return {
        ...series,
        data: data.map((d) => wrapDataItem(d, { opacity: DIM_OPACITY })),
      };
    }
  }

  // 热力图：series 级别淡化
  if (sType === 'heatmap') {
    const data = (series.data as unknown[]) || [];
    return {
      ...series,
      data: data.map((d) => {
        if (Array.isArray(d)) {
          return { value: d, itemStyle: { opacity: DIM_OPACITY } };
        }
        return wrapDataItem(d, { opacity: DIM_OPACITY });
      }),
    };
  }

  // 其他类型 → series 级别淡化
  return {
    ...series,
    itemStyle: {
      ...(series.itemStyle as Record<string, unknown>),
      opacity: DIM_OPACITY,
    },
  };
}

// ===================================================================
// ★ 主组件
// ===================================================================

export default function EChartView({
  option, title, height = 400, hideTitle,
  groupId, highlightLabel, onHighlight,
}: Props) {
  const domRef = useRef<HTMLDivElement>(null);
  const instanceRef = useRef<echarts.ECharts | null>(null);
  const lastClickRef = useRef(0);
  const highlightLabelRef = useRef(highlightLabel);
  const onHighlightRef = useRef(onHighlight);

  useEffect(() => { highlightLabelRef.current = highlightLabel ?? null; }, [highlightLabel]);
  useEffect(() => { onHighlightRef.current = onHighlight; }, [onHighlight]);

  // ★ 计算增强后的 option（联动样式 + 高亮/淡化）
  const enhancedOption = useMemo(() => {
    if (!option) return null;
    // 词云已从后端分析能力移除：任何来源的词云 option 均不渲染
    const seriesArr = (option.series as Array<Record<string, unknown>>) || [];
    if (seriesArr.some((s) => String(s.type) === 'wordCloud')) return null;
    const base = enhanceOptionForInteraction(option);
    // 防御：规整 visualMap.text 为 2 元素数组，规避 ECharts endsText.slice(...).reverse 报错
    // （覆盖任何来源：后端生成 / 旧看板包 / 缺 text 或 text 为字符串的情况）
    const vm = (base as Record<string, unknown>).visualMap;
    (Array.isArray(vm) ? vm : vm ? [vm] : []).forEach((item) => {
      const o = item as Record<string, unknown>;
      const t = o?.text;
      if (!Array.isArray(t) || t.length !== 2) o.text = ['高', '低'];
    });
    if (highlightLabel) {
      return applyHighlightBlur(base, highlightLabel);
    }
    return base;
  }, [option, highlightLabel]);

  // ★ 记录当前是否为 3D 图表，用于检测 2D/3D 切换时需要重新初始化
  const isGLRef = useRef<boolean | null>(null);

  // ===== 初始化图表 + 绑定事件 =====
  useEffect(() => {
    const el = domRef.current;
    if (!el || !enhancedOption) return;

    // ★ 检测当前是否需要 3D（echarts-gl）
    const isGL = needsWebGL(enhancedOption);

    // ★ 2D→3D 或 3D→2D 切换时，必须销毁旧实例重新创建
    // 因为 echarts-gl 需要在新实例上初始化 WebGL 上下文
    let chart = instanceRef.current;
    if (chart && isGLRef.current !== isGL) {
      chart.dispose();
      chart = null;
      instanceRef.current = null;
      isGLRef.current = null;
    }

    const needsInit = !chart;

    const initAndRender = async () => {
      // ★ 任何使用中国地图的图表都需要先注册 GeoJSON（2D geo 和 3D geo3D/map3D）
      if (needsChinaMap(enhancedOption)) {
        await ensureChinaMapRegistered();
      }

      if (needsInit) {
        // ★ ECharts 核心只支持 'canvas' 和 'svg' 渲染器，不支持 'webgl'
        // echarts-gl 在 Canvas 渲染器之上内部处理 3D WebGL 渲染
        chart = echarts.init(el, undefined, { renderer: 'canvas' });
        instanceRef.current = chart;
        isGLRef.current = isGL;

        if (groupId) {
          chart.group = groupId;
          echarts.connect(groupId);
        }

        chart.on('click', (params: Record<string, unknown>) => {
          const oh = onHighlightRef.current;
          if (!oh) return;
          const now = Date.now();
          if (now - lastClickRef.current < 250) return;
          lastClickRef.current = now;

          const seriesType = String(params.seriesType || '');
          const isRadar = seriesType === 'radar';
          const label = isRadar
            ? String(params.seriesName || params.name || '')
            : String(params.name || params.seriesName || '');

          if (!label || label === 'undefined') return;

          if (label === highlightLabelRef.current) {
            oh(null);
          } else {
            oh(label);
          }
        });

        chart.getZr().on('click', (e: Record<string, unknown>) => {
          if (!e.target) {
            onHighlightRef.current?.(null);
          }
        });
      }

      try {
        chart.setOption(enhancedOption, { notMerge: true });
      } catch (err) {
        console.error('[EChartView] setOption 失败:', err);
        // 3D 渲染失败时，尝试降级到 2D
        if (isGL && needsInit) {
          console.warn('[EChartView] 3D 渲染失败，尝试降级到 2D');
          chart.dispose();
          chart = echarts.init(el, undefined, { renderer: 'canvas' });
          instanceRef.current = chart;
          isGLRef.current = false;
          // 移除 3D 组件，仅保留基础渲染
          const fallbackOption = { ...enhancedOption };
          delete fallbackOption.geo3D;
          const fallbackSeries = (fallbackOption.series as Array<Record<string, unknown>>) || [];
          fallbackOption.series = fallbackSeries.filter(s => !String(s.type).includes('3D'));
          if (Object.keys(fallbackOption).length > 1) {
            chart.setOption(fallbackOption as EChartsOption, { notMerge: true });
          }
        }
      }
    };

    initAndRender();

    const onResize = () => chart?.resize();
    window.addEventListener('resize', onResize);
    return () => { window.removeEventListener('resize', onResize); };
  }, [enhancedOption, groupId]);

  useEffect(() => {
    return () => {
      const chart = instanceRef.current;
      if (chart) {
        chart.dispose();
        instanceRef.current = null;
        isGLRef.current = null;
      }
    };
  }, []);

  if (!option) {
    return (
      <div className="glass-card p-4">
        {title && !hideTitle && <h3 className="text-sm font-medium text-slate-300 mb-3">{title}</h3>}
        <div style={{ height }} className="w-full flex items-center justify-center text-slate-500">
          暂无图表数据
        </div>
      </div>
    );
  }

  const displayTitle = hideTitle ? '' : (title || extractTitle(option));

  return (
    <div className="glass-card p-4" data-echart-wrapper style={{ overflow: 'hidden' }}>
      {displayTitle && <h3 className="text-sm font-medium text-slate-300 mb-3">{displayTitle}</h3>}
      <div ref={domRef} style={{ height: `${height}px`, width: '100%', minWidth: 0 }} />
    </div>
  );
}
