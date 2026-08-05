import React, { useEffect, useRef } from 'react';
import * as echarts from 'echarts/core';
import { HeatmapChart } from 'echarts/charts';
import { GridComponent, TooltipComponent, VisualMapComponent, ToolboxComponent, TitleComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import type { EChartsCoreOption } from 'echarts/core';
import 背景 from '../../assets/ethereal/背景.png';

echarts.use([HeatmapChart, GridComponent, TooltipComponent, VisualMapComponent, ToolboxComponent, TitleComponent, CanvasRenderer]);

// 仙气浅色调（对齐同期群留存热力图的 inRange 配色）
const EPHEMERAL_COLORS = ['#D6E5FA', '#E2DAF4', '#EDCEEC', '#F6C3E2', '#FCB8D7', '#FFAECC'];

interface Props {
  /** 直接吃原生 ECharts heatmap option（含 xAxis/yAxis/series/visualMap） */
  chartNode: Record<string, unknown>;
  title?: string;
  height?: number | string;
}

export const EtherealHeatmap: React.FC<Props> = ({ chartNode, title, height = 420 }) => {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    const chartDom = ref.current;
    const chart = echarts.init(chartDom);

    const xAxis = (chartNode.xAxis as { data?: unknown[] }) || {};
    const yAxis = (chartNode.yAxis as { data?: unknown[] }) || {};
    const series = (chartNode.series as Array<Record<string, unknown>>) || [];
    const series0 = series[0] || {};
    const heatData = (series0.data as Array<unknown>) || [];
    const visualMap = (chartNode.visualMap as Record<string, unknown>) || {};
    const chartTitle = (title as string) || (chartNode.title as string) || '';

    const vmin = typeof visualMap.min === 'number' ? visualMap.min : undefined;
    const vmax = typeof visualMap.max === 'number' ? visualMap.max : undefined;

    const option: EChartsCoreOption = {
      backgroundColor: 'transparent',
      title: chartTitle
        ? { text: chartTitle, left: 12, top: 8, textStyle: { color: '#475569', fontSize: 16, fontWeight: 'bold' } }
        : undefined,
      tooltip: {
        position: 'top',
        backgroundColor: 'rgba(255,255,255,0.95)',
        borderColor: '#E2E8F0',
        borderWidth: 1,
        textStyle: { color: '#475569', fontWeight: 'bold' },
        formatter: (p: { value: number[] }) =>
          `${p.value[0]} × ${p.value[1]}<br/>数值：<span style="color:#FCB8D7">${p.value[2]}</span>`,
      },
      grid: { top: chartTitle ? 50 : 30, left: 100, right: 30, bottom: 70, containLabel: true },
      xAxis: {
        type: 'category',
        data: (xAxis.data as unknown[]) || [],
        axisLabel: { color: '#64748B', fontWeight: 'bold', fontSize: 13 },
        axisLine: { show: false },
        axisTick: { show: false },
        splitArea: { show: false },
      },
      yAxis: {
        type: 'category',
        data: (yAxis.data as unknown[]) || [],
        axisLabel: { color: '#475569', fontWeight: 'bold', fontSize: 13 },
        axisLine: { show: false },
        axisTick: { show: false },
        splitArea: { show: false },
      },
      visualMap: {
        min: vmin ?? 0,
        max: vmax ?? 1,
        calculable: true,
        orient: 'horizontal',
        left: 'center',
        bottom: 10,
        textStyle: { color: '#64748B', fontWeight: 'bold', fontSize: 11 },
        inRange: { color: EPHEMERAL_COLORS },
        ...(vmin === undefined || vmax === undefined ? {} : {}),
      },
      toolbox: {
        show: true,
        right: 20,
        top: 0,
        itemSize: 16,
        itemGap: 12,
        z: 9999,
        iconStyle: { borderColor: '#8B7FB0' },
        feature: { saveAsImage: { title: '下载图片', name: chartTitle || 'heatmap' } },
      },
      series: [
        {
          name: (series0.name as string) || 'value',
          type: 'heatmap',
          data: heatData,
          itemStyle: { borderColor: '#FFFFFF', borderWidth: 3, borderRadius: 6 },
          label: {
            show: true,
            color: '#475569',
            fontWeight: 'bold',
            fontSize: 11,
            formatter: (p: { value: number[] }) => String(p.value[2]),
          },
          emphasis: { itemStyle: { shadowBlur: 8, shadowColor: 'rgba(252,184,215,0.6)' } },
        },
      ],
    };

    chart.setOption(option, true);

    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(chartDom);
    return () => {
      ro.disconnect();
      chart.dispose();
    };
  }, [chartNode, title]);

  // ★ 与「活跃趋势（折线）组件」保持一致的仙气玻璃卡风格：同款背景图 + 玻璃白 + 大圆角 + 阴影 + 边框
  //   修复热力图背景在并排时消失/不一致的问题（之前背景在 useEffect 里设置，与外层叠加时易被覆盖）
  return (
    <div
      ref={ref}
      style={{
        width: '100%',
        height,
        backgroundImage: `url(${背景})`,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        backgroundColor: 'rgba(255, 255, 255, 0.45)',
        backdropFilter: 'blur(24px)',
        WebkitBackdropFilter: 'blur(24px)',
        border: '1px solid rgba(255, 255, 255, 0.8)',
        borderRadius: 24,
        boxShadow: '0 10px 30px rgba(31, 41, 55, 0.18)',
      }}
    />
  );
};

export default EtherealHeatmap;
