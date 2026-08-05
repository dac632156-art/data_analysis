import React, { useEffect, useRef } from 'react';
import * as echarts from 'echarts/core';
import { RadarChart } from 'echarts/charts';
import { TooltipComponent, LegendComponent, ToolboxComponent, TitleComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import type { EChartsCoreOption } from 'echarts/core';
import 背景 from '../../assets/ethereal/背景.png';

echarts.use([RadarChart, TooltipComponent, LegendComponent, ToolboxComponent, TitleComponent, CanvasRenderer]);

// 仙气水彩色板：取自 EtherealBubbleChart.tsx 的 BASE_COLORS（同套柔彩体系），
// 扩到 4 色避免多系列撞色（原版只有 2 色，3 系列时必有两系列同色）。
// 顺序：蓝 / 粉 / 淡紫 / 玫瑰粉，保持柔和水彩调性，不引入刺眼色。
const pastelColors = ['#A3C4F3', '#F1C0E8', '#A78BFA', '#FB7185'];

// 水墨纹理 canvas（对齐原版 createPureWatercolorPattern 第 42 行）
function createPureWatercolorPattern(img: HTMLImageElement, hexColor: string): HTMLCanvasElement {
  const canvas = document.createElement('canvas');
  canvas.width = 150;
  canvas.height = 150;
  const ctx = canvas.getContext('2d')!;
  ctx.drawImage(img, 0, 0, img.naturalWidth, img.naturalHeight, 0, 0, 150, 150);
  const imageData = ctx.getImageData(0, 0, 150, 150);
  const data = imageData.data;
  const hex = hexColor.replace('#', '');
  const r = parseInt(hex.substring(0, 2), 16);
  const g = parseInt(hex.substring(2, 4), 16);
  const b = parseInt(hex.substring(4, 6), 16);
  for (let i = 0; i < data.length; i += 4) {
    const darkness = (255 - data[i]) / 255;
    let opacity = 0.4 + darkness * 2.8;
    if (opacity > 1) opacity = 1;
    data[i] = Math.round(255 * (1 - opacity) + r * opacity);
    data[i + 1] = Math.round(255 * (1 - opacity) + g * opacity);
    data[i + 2] = Math.round(255 * (1 - opacity) + b * opacity);
    data[i + 3] = 255;
  }
  ctx.putImageData(imageData, 0, 0);
  return canvas;
}
// 降级：无图时用纯色半透
function fallbackArea(color: string) {
  return { color, opacity: 0.45 };
}

interface RadarSeriesItem {
  name: string;
  color?: string;
  value: number[];
}
interface Props {
  chartNode: Record<string, unknown>;
  height?: number | string;
}

export const EtherealRadarChart: React.FC<Props> = ({ chartNode, height = 420 }) => {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    const chartDom = ref.current;
    chartDom.style.backgroundImage = `url(${背景})`;
    chartDom.style.backgroundSize = 'cover';
    chartDom.style.backgroundPosition = 'center';
    chartDom.style.borderRadius = '24px';
    chartDom.style.backgroundColor = 'rgba(255, 255, 255, 0.4)';
    chartDom.style.backdropFilter = 'blur(20px)';
    chartDom.style.boxShadow = '0 20px 40px -10px rgba(99, 102, 241, 0.1), inset 0 1px 0 rgba(255, 255, 255, 0.9)';

    const chart = echarts.init(chartDom);

    const title = (chartNode.title as string) || '';

    // 兼容两套输入结构：
    //   A. 标准 ECharts radar option（后端 /api 走这条路）：
    //      chartNode.radar.indicator = [{name, max}]，chartNode.series = [{name, type:'radar', data:[{value:[...], name}]}]
    //   B. 私有仙气结构（旧预览页 / 模板库）：
    //      chartNode.indicators = [{name, max}]，chartNode.series = [{name, value:[...]}]
    const radarNode = (chartNode.radar as Record<string, unknown>) || {};
    const stdIndicators = (radarNode.indicator as Array<{ name: string; max: number }>) || [];
    const privIndicators = (chartNode.indicators as Array<{ name: string; max: number }>) || [];
    const indicators = stdIndicators.length ? stdIndicators : privIndicators;

    const rawSeries = (chartNode.series as Array<Record<string, unknown>>) || [];
    // 归一化为 { name, value:number[] }
    const seriesRaw: RadarSeriesItem[] = rawSeries.map((s) => {
      // 标准结构：s.data = [{ value:[...], name }]
      const dataArr = (s.data as Array<unknown>) || [];
      if (dataArr.length && typeof dataArr[0] === 'object' && dataArr[0] !== null) {
        const first = dataArr[0] as Record<string, unknown>;
        const val = (first.value as number[]) || [];
        const nm = (first.name as string) || (s.name as string) || '';
        return { name: nm, value: val, color: s.color as string | undefined };
      }
      // 私有结构：s.value 直接是 number[]
      return {
        name: (s.name as string) || '',
        value: (s.value as number[]) || [],
        color: s.color as string | undefined,
      };
    }).filter((s) => Array.isArray(s.value) && s.value.length > 0);

    // 异步加载水彩底图（对齐原版 fetch bg5.png 逻辑）
    const img = new Image();
    img.src = 背景;
    const build = () => {
      // 图层顺序修复：ECharts 后画的 series 盖在先画的上面。
      // 按各系列「均值（近似面积）」从大到小排序，让大图先画、小图最后画浮在最上层，
      // 避免大粉图把小蓝图压在下面（用户期望：越小的图越在上面）。
      const ordered = [...seriesRaw].sort(
        (a, b) => b.value.reduce((s, v) => s + (v || 0), 0) / b.value.length
                - a.value.reduce((s, v) => s + (v || 0), 0) / a.value.length,
      );
      const series = ordered.map((s, idx) => {
        // 严格对齐原版 pastelColors 硬编码（忽略 s.color）
        const color = pastelColors[idx % pastelColors.length];
        const areaStyle = img.complete && img.naturalWidth
          ? { color: { image: createPureWatercolorPattern(img, color), repeat: 'repeat' } as unknown, opacity: 0.85 }
          : fallbackArea(color);
        return {
          name: s.name,
          type: 'radar' as const,
          // 标准 radar 要求 data 为 [{value:[...], name}] 对象数组，不能裸数组
          data: [{ value: s.value, name: s.name }],
          itemStyle: { color: '#ffffff', borderColor: color, borderWidth: 1.5 },
          lineStyle: { width: 2, color },
          areaStyle,
          symbol: 'circle',
          symbolSize: 7,
        };
      });

      const option: EChartsCoreOption = {
        backgroundColor: 'transparent',
        title: title ? { text: title, left: 12, top: 8, textStyle: { color: '#475569', fontSize: 16, fontWeight: 'bold' } } : undefined,
        tooltip: { trigger: 'item' },
        legend: {
          show: seriesRaw.length > 1,
          bottom: 0,
          icon: 'circle',
          itemWidth: 10,
          itemHeight: 10,
          textStyle: { color: '#64748B', fontWeight: 600, fontSize: 12 },
        },
        radar: {
          indicator: indicators,
          center: ['50%', title ? '54%' : '50%'],
          radius: '62%',
          axisName: { color: '#475569', fontWeight: 'bold', fontSize: 13, padding: [3, 3] as [number, number] },
          splitArea: { show: false },
          splitLine: { lineStyle: { color: ['#F1F5F9', '#E2E8F0'], width: 1.5 } },
          axisLine: { lineStyle: { color: '#E2E8F0', type: 'dashed' } },
        },
        toolbox: {
          show: true,
          left: 'right',
          right: 20,
          top: 0,
          orient: 'horizontal',
          itemSize: 16,
          itemGap: 12,
          z: 9999,
          iconStyle: { borderColor: '#8B7FB0' },
          feature: { saveAsImage: { title: '下载图片', name: title || 'chart' } },
        },
        series,
      };
      chart.setOption(option, true);
    };

    // 数据不全（无维度或无序列）时不渲染，避免 ECharts radarLayout 因 indicator 为空而崩溃整页
    if (indicators.length === 0 || seriesRaw.length === 0) {
      chart.dispose();
      if (ref.current) {
        ref.current.innerHTML =
          '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#94a3b8;font-size:13px;">雷达图数据不完整，暂无法渲染</div>';
      }
      return;
    }

    if (img.complete && img.naturalWidth) build();
    else img.onload = build;

    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(chartDom);
    return () => {
      ro.disconnect();
      chart.dispose();
    };
  }, [chartNode]);

  return <div ref={ref} style={{ width: '100%', height, borderRadius: 24 }} />;
};
