/* EChartView - ECharts 图表渲染组件（option-based 联动高亮 + 3D GL 支持） */
import React, { useEffect, useRef, useMemo } from 'react';
import * as echarts from 'echarts/core';
import {
  BarChart, LineChart, PieChart, ScatterChart, EffectScatterChart, RadarChart,
  TreemapChart, BoxplotChart, HeatmapChart, CustomChart, GraphChart,
  FunnelChart,
} from 'echarts/charts';
import {
  TitleComponent, TooltipComponent, GridComponent, LegendComponent,
  ToolboxComponent, DataZoomComponent, VisualMapComponent,
  BrushComponent, MarkLineComponent, MarkPointComponent,
  GeoComponent,  // ★ 2D 地图组件
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
// ★ echarts-gl 3D 扩展
import 'echarts-gl';

echarts.use([
  BarChart, LineChart, PieChart, ScatterChart, EffectScatterChart, RadarChart,
  TreemapChart, BoxplotChart, HeatmapChart, CustomChart, GraphChart,
  FunnelChart,
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

// ★ 统一强调色（仙气紫，原 theme/ 银河紫辉光已内联）
const EMPHASIS_GLOW = 'rgba(124,58,237,0.55)'; // 仙气紫辉光（图表 hover 强调）
const EMPHASIS_BORDER = '#7c3aed'; // 仙气紫（边框强调）
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
    const base = enhanceOptionForInteraction(option);
    // 防御：规整 visualMap.text 为 2 元素数组，规避 ECharts endsText.slice(...).reverse 报错
    // （覆盖任何来源：后端生成 / 旧看板包 / 缺 text 或 text 为字符串的情况）
    const vm = (base as Record<string, unknown>).visualMap;
    (Array.isArray(vm) ? vm : vm ? [vm] : []).forEach((item) => {
      const o = item as Record<string, unknown>;
      const t = o?.text;
      if (!Array.isArray(t) || t.length !== 2) o.text = ['高', '低'];
    });
    // ★ 热力图兜底：ECharts 强制要求 heatmap series 必须配套 visualMap，
    // 后端偶发漏配 / 老版本包仍会触发「Heatmap must use with visualMap」异常并冒泡
    // 到 React ErrorBoundary 显示"页面渲染出错"。此处自动注入一个 minimal visualMap
    // （按 series.data 实际值范围生成 min/max；空 series 时退到 0~1）。
    const hasHeatmap = seriesArr.some((s) => String(s.type) === 'heatmap');
    const baseRec = base as Record<string, unknown>;
    const hasVM = Array.isArray(baseRec.visualMap)
      ? (baseRec.visualMap as unknown[]).length > 0
      : !!baseRec.visualMap;
    if (hasHeatmap && !hasVM) {
      let vMin = 0;
      let vMax = 1;
      for (const s of seriesArr) {
        const data = (s as Record<string, unknown>).data as unknown[] | undefined;
        if (!Array.isArray(data)) continue;
        for (const item of data) {
          let val: number | null = null;
          if (Array.isArray(item)) {
            const last = item[item.length - 1];
            if (typeof last === 'number' && Number.isFinite(last)) val = last;
          } else if (item && typeof item === 'object') {
            const obj = item as Record<string, unknown>;
            const v = obj.value;
            if (Array.isArray(v)) {
              const last = v[v.length - 1];
              if (typeof last === 'number' && Number.isFinite(last)) val = last;
            } else if (typeof v === 'number' && Number.isFinite(v)) {
              val = v;
            }
          } else if (typeof item === 'number' && Number.isFinite(item)) {
            val = item;
          }
          if (val !== null) {
            if (val < vMin) vMin = val;
            if (val > vMax) vMax = val;
          }
        }
      }
      // 若全相等则给 max 一个小偏移，避免 ECharts 区间为 0 报错
      if (vMin === vMax) vMax = vMin + 1;
      baseRec.visualMap = {
        min: vMin,
        max: vMax,
        calculable: true,
        orient: 'horizontal',
        left: 'center',
        bottom: 0,
        inRange: { color: ['#0b3a5c', '#1d6cb0', '#3aa6ff', '#a6dcff', '#ffefa0', '#ff8a4d', '#f04158'] },
        text: ['高', '低'],
      };
    }

    // ★ legend 自适应：图例溢出/重合兜底
    //   问题：ECharts 默认把 legend 放在底部水平铺开，series 数量多 + 图例名长时挤压/换行，
    //   出现「图例文字重合」「图例压到 x 轴 label」等。
    //   兜底：若 option.legend 没设 type → 注入 scroll 类型，让图例可横向滚动；
    //   若没设 top → 注入 'top' (铺在标题下方) —— 标题通常由图表容器自身渲染 (EtherealChart 组件已有 <ChartTitle/>)。
    //   但部分 chart 后端不带 title、只靠 chartType 渲染（包型 chart），
    //   此时 legend top=0 就在容器顶部，与 series 打架；因此按 series count 自动选择：
    //     - series 数 ≤ 4 且名短 → bottom: 'auto'（默认）
    //     - series 数 ≥ 5 或名长 → top:0 + type:scroll + textStyle.fontSize:10
    const computeLegendName = (s: Record<string, unknown>): string => {
      const n = s.name;
      if (typeof n === 'string') return n;
      if (Array.isArray(n)) return n.join('-');
      if (s.data && Array.isArray(s.data) && (s.data as unknown[])[0] && typeof (s.data as unknown[])[0] === 'object') {
        const head = (s.data as unknown[])[0] as Record<string, unknown>;
        return String(head.name || head.seriesName || '');
      }
      return '';
    };
    const seriesNames = seriesArr.map(computeLegendName).filter(Boolean);
    const longestName = seriesNames.reduce((m, n) => Math.max(m, n.length), 0);
    const needScroll = seriesNames.length >= 5 || longestName > 8;
    const existingLegend = baseRec.legend as Record<string, unknown> | undefined;
    // 部分组件（如 heatmap）会把 legend 关掉 (legend.show=false)，尊重它们
    if (!existingLegend || existingLegend.show !== false) {
      if (needScroll) {
        baseRec.legend = {
          ...(existingLegend || {}),
          type: 'scroll',
          top: 0,
          left: 'center',
          itemWidth: 12,
          itemHeight: 8,
          itemGap: 6,
          pageIconColor: '#5BA0FF',
          pageTextStyle: { color: '#6B7B95' },
          textStyle: { color: '#475569', fontSize: 10 },
        };
      } else {
        // 短图例：仍保留在底部默认，但若 bottom 已设置则不覆盖；并稍稍缩小字号以避免贴边
        baseRec.legend = {
          ...(existingLegend || {}),
          type: 'plain',
          bottom: (existingLegend && (existingLegend.bottom !== undefined)) ? existingLegend.bottom : 0,
          itemGap: 8,
          textStyle: { color: '#475569', fontSize: 11, ...(existingLegend?.textStyle as object || {}) },
        };
      }
    }

    // ★ 关键：legend 默认位置在 top:0 / scroll 时，ECharts 不会自动给 grid.top 让出空间，
    //   会把图例拉到底部并与 x 轴 label 重合（用户截图里"各群体占比"图例覆盖 x 轴）。
    //   解决：用户乐于 scroll 模式时强制 grid.top = 60 给图例留位；
    //   plain 模式时强制 grid.bottom = 36 给图例留位。
    const existingGrid = (baseRec.grid as Record<string, unknown> | undefined) || {};
    if (Array.isArray(baseRec.xAxis) || !Array.isArray(baseRec.xAxis)) {
      // 不论 xAxis 是否数组，grid 都要让位
    }
    const applyGridMargin = (key: 'top' | 'bottom', val: number) => {
      const cur = (existingGrid[key] as string | number | undefined);
      // 已有大值不覆盖
      if (typeof cur === 'number' && cur >= val) return;
      if (typeof cur === 'string' && /%$/.test(cur)) {
        const num = parseFloat(cur);
        if (num >= val) return;
      }
      existingGrid[key] = val;
    };
    if (needScroll) {
      applyGridMargin('top', 60);
    } else {
      applyGridMargin('bottom', 40);
    }
    if (existingGrid.left === undefined) existingGrid.left = 16;
    if (existingGrid.right === undefined) existingGrid.right = 16;
    if (existingGrid.containLabel === undefined) existingGrid.containLabel = true;
    baseRec.grid = existingGrid;
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

    // ★ 关键守卫：组件卸载/模式切换前异步任务全部作废
    let cancelled = false;
    // ★ 当前 effect 持有的 chart 实例引用（cleanup 时唯一 dispose 来源）
    let localChart: echarts.ECharts | null = null;

    // ★ 2D→3D 或 3D→2D 切换时，必须销毁旧实例重新创建
    // 因为 echarts-gl 需要在新实例上初始化 WebGL 上下文
    let chart = instanceRef.current;
    if (chart && isGLRef.current !== isGL) {
      try { chart.dispose(); } catch {}
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

      // ★ StrictMode / 快速切换 slot 时，异步 init 前再确认容器仍在、未被卸载
      if (cancelled) return;
      const curEl = domRef.current;
      if (!curEl) return;

      if (needsInit) {
        // ★ ECharts 核心只支持 'canvas' 和 'svg' 渲染器，不支持 'webgl'
        // echarts-gl 在 Canvas 渲染器之上内部处理 3D WebGL 渲染
        chart = echarts.init(curEl, undefined, { renderer: 'canvas' });
        localChart = chart;
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

      if (cancelled || !chart) return;

      try {
        chart.setOption(enhancedOption, { notMerge: true });
      } catch (err) {
        console.error('[EChartView] setOption 失败:', err);
        // 3D 渲染失败时，尝试降级到 2D
        if (isGL && needsInit) {
          console.warn('[EChartView] 3D 渲染失败，尝试降级到 2D');
          try { chart.dispose(); } catch {}
          if (cancelled) return;
          chart = echarts.init(curEl, undefined, { renderer: 'canvas' });
          instanceRef.current = chart;
          isGLRef.current = false;
          // 移除 3D 组件，仅保留基础渲染
          const fallbackOption = { ...enhancedOption };
          delete fallbackOption.geo3D;
          const fallbackSeries = (fallbackOption.series as Array<Record<string, unknown>>) || [];
          fallbackOption.series = fallbackSeries.filter(s => !String(s.type).includes('3D'));
          if (Object.keys(fallbackOption).length > 1) {
            try {
              chart.setOption(fallbackOption as EChartsOption, { notMerge: true });
            } catch (innerErr) {
              // ★ 兜底：2D setOption 仍失败（如 heatmap 缺 visualMap 等）时，渲染一个
              // "图表数据异常"占位 option，阻止异常冒泡到 ErrorBoundary 让整页崩溃。
              console.error('[EChartView] 2D 降级仍失败，渲染错误占位:', innerErr);
              chart.setOption({
                title: { text: '图表数据异常', left: 'center', top: 'middle', textStyle: { color: '#F87171', fontSize: 14 } },
              } as EChartsOption, { notMerge: true });
            }
          }
        } else {
          // ★ 非 3D 的 setOption 失败：兜底渲染错误占位，阻止整页崩溃。
          console.warn('[EChartView] setOption 失败（2D），渲染错误占位');
          try {
            chart.setOption({
              title: { text: '图表数据异常', left: 'center', top: 'middle', textStyle: { color: '#F87171', fontSize: 14 } },
            } as EChartsOption, { notMerge: true });
          } catch (innerErr) {
            console.error('[EChartView] 错误占位也失败:', innerErr);
          }
        }
      }
    };

    initAndRender();

    const onResize = () => {
      if (cancelled) return;
      try { chart?.resize(); } catch {}
    };
    window.addEventListener('resize', onResize);
    // ★ 容器尺寸变化（cell 高度变化、grid 重排等）也要 resize，否则图表固定初始尺寸
    let ro: ResizeObserver | null = null;
    if (typeof ResizeObserver !== 'undefined' && domRef.current) {
      ro = new ResizeObserver(() => {
        if (cancelled) return;
        try { chart?.resize(); } catch { /* ignore */ }
      });
      ro.observe(domRef.current);
    }
    return () => {
      // ★ 关键：effect 清理时（enhancedOption/groupId 变化 → React 重建 effect，
      //   或组件卸载）必须 dispose 当前持有的实例，避免 chart 在已卸载的容器
      //   上继续 RAF → 调 el.getBoundingClientRect() 报 null。
      cancelled = true;
      window.removeEventListener('resize', onResize);
      ro?.disconnect();
      ro = null;
      // ★ 优先 dispose 本 effect 创建的实例；否则 dispose ref 中的实例（兼容复用）
      const toDispose = localChart || instanceRef.current;
      if (toDispose) {
        try { toDispose.dispose(); } catch { /* ignore */ }
        if (instanceRef.current === toDispose) {
          instanceRef.current = null;
          isGLRef.current = null;
        }
      }
    };
  }, [enhancedOption, groupId]);

  if (!option) {
    return (
      <div className="glass-card p-4">
        {title && !hideTitle && <h3 className="text-sm font-medium text-slate-700 mb-3">{title}</h3>}
        <div style={{ height }} className="w-full flex items-center justify-center text-slate-500">
          暂无图表数据
        </div>
      </div>
    );
  }

  const displayTitle = hideTitle ? '' : (title || extractTitle(option));

  return (
    <div className="glass-card p-4" data-echart-wrapper style={{ overflow: 'hidden' }}>
      {displayTitle && <h3 className="text-sm font-medium text-slate-700 mb-3">{displayTitle}</h3>}
      <div ref={domRef} style={{ height: `${height}px`, width: '100%', minWidth: 0 }} />
    </div>
  );
}
