import React, { useEffect, useRef } from 'react';
import * as echarts from 'echarts/core';
import { LineChart } from 'echarts/charts';
import { GridComponent, TooltipComponent, TitleComponent, LegendComponent, ToolboxComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import type { EChartsCoreOption } from 'echarts/core';
import 背景 from '../../assets/ethereal/背景.png';

echarts.use([LineChart, GridComponent, TooltipComponent, TitleComponent, LegendComponent, ToolboxComponent, CanvasRenderer]);

// 仙气粉彩调色板（与可视化库「折线图组件.js」逐字一致）
const customPalette = ['#FCCDDF', '#C8E1F5', '#E2C9F3', '#D7EFE5', '#FCDDC8', '#E8C9CE', '#F9F1C6', '#BAC2F0'];

interface Props {
  chartNode: Record<string, unknown>;
  title?: string;
  height?: number;
}

function normalizeTitle(node: Record<string, unknown>, propTitle?: string): string {
  if (propTitle) return propTitle;
  const t = node.title;
  if (typeof t === 'string') return t;
  if (t && typeof t === 'object') {
    const text = (t as Record<string, unknown>).text;
    if (typeof text === 'string') return text;
  }
  return '';
}

function getXData(opt: Record<string, unknown>): string[] {
  const xAxis = opt.xAxis as Record<string, unknown> | Array<Record<string, unknown>> | undefined;
  if (!xAxis) return [];
  const first = Array.isArray(xAxis) ? xAxis[0] : xAxis;
  const data = first?.data;
  return Array.isArray(data) ? data.map((v) => String(v ?? '')) : [];
}

function getSeriesData(opt: Record<string, unknown>): Array<Record<string, unknown>> {
  const series = opt.series as Array<Record<string, unknown>> | undefined;
  return Array.isArray(series) ? series : [];
}

// 从后端 series 原样取数据数组，null 保持原样（断点正确断开，不洗成 0）
function extractSeriesValues(raw: unknown): Array<number | null> {
  if (!Array.isArray(raw)) return [];
  return raw.map((v) => {
    if (v === null || v === undefined) return null;
    if (typeof v === 'object') return Number((v as Record<string, unknown>).value ?? 0);
    return Number(v);
  });
}

export const EtherealLineChart: React.FC<Props> = ({ chartNode, title, height = 360 }) => {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    const chartDom = ref.current;
    const chart = echarts.init(chartDom);
    const node = chartNode || {};

    const titleText = normalizeTitle(node, title);

    // 兼容标准 ECharts option（series + xAxis.data）以及老私有格式（data 数组）
    let xAxisData: string[] = getXData(node);
    const rawData = (node.data as Array<Record<string, unknown>>) || undefined;
    if (xAxisData.length === 0 && Array.isArray(rawData) && rawData.length > 0) {
      const xField = (node.x as string) || '首单月';
      xAxisData = rawData.map((r) => String(r[xField] ?? ''));
    }

    const seriesInput = getSeriesData(node);
    const series: any[] = [];

    if (seriesInput.length > 0) {
      // 忠实透传后端 series，仅叠加仙气样式（保留 connectNulls 语义）
      seriesInput.forEach((s, idx) => {
        const color = customPalette[idx % customPalette.length];
        const connectNulls = (s.connectNulls as boolean) ?? false;
        series.push({
          name: s.name || `Series ${idx + 1}`,
          type: 'line',
          smooth: true,
          connectNulls,
          showSymbol: true,
          symbol: 'circle',
          symbolSize: 9,
          data: extractSeriesValues(s.data),
          lineStyle: {
            color,
            width: 3,
            shadowColor: color,
            shadowBlur: 10,
            shadowOffsetY: 6,
          },
          itemStyle: {
            color: '#fff',
            borderColor: color,
            borderWidth: 2,
            shadowColor: color,
            shadowBlur: 10,
          },
          emphasis: { focus: 'series' },
        });
      });
    } else if (Array.isArray(rawData) && rawData.length > 0) {
      const xField = (node.x as string) || '首单月';
      const sample = rawData[0] || {};
      const yKeys = Object.keys(sample).filter((k) => k !== xField);
      yKeys.forEach((yk, idx) => {
        const color = customPalette[idx % customPalette.length];
        series.push({
          name: yk,
          type: 'line',
          smooth: true,
          showSymbol: true,
          symbol: 'circle',
          symbolSize: 9,
          data: rawData.map((r) => {
            const v = r[yk];
            return v === null || v === undefined ? null : Number(v);
          }),
          lineStyle: {
            color,
            width: 3,
            shadowColor: color,
            shadowBlur: 10,
            shadowOffsetY: 6,
          },
          itemStyle: {
            color: '#fff',
            borderColor: color,
            borderWidth: 2,
            shadowColor: color,
            shadowBlur: 10,
          },
          emphasis: { focus: 'series' },
        });
      });
    }

    const option: EChartsCoreOption = {
      backgroundColor: 'transparent',
      title: titleText
        ? {
            text: titleText,
            left: 'center',
            top: 14,
            textStyle: { color: '#1E293B', fontSize: 16, fontWeight: 700 },
          }
        : undefined,
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(255, 255, 255, 0.88)',
        borderColor: '#E2E8F0',
        borderWidth: 1,
        textStyle: { color: '#475569', fontWeight: 600 },
        extraCssText: 'box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); backdrop-filter: blur(8px); border-radius: 12px;',
      },
      toolbox: {
        right: 16,
        top: 8,
        feature: {
          saveAsImage: {
            name: titleText || 'chart',
            title: '下载图片',
            backgroundColor: 'rgba(255,255,255,0)',
            iconStyle: { borderColor: '#94A3B8' },
          },
        },
      },
      legend: {
        bottom: 4,
        textStyle: { color: '#475569', fontSize: 12, fontWeight: 600 },
        itemGap: 16,
        icon: 'circle',
      },
      grid: { left: 56, right: 32, top: titleText ? 64 : 40, bottom: 48, containLabel: true },
      xAxis: {
        type: 'category',
        data: xAxisData,
        boundaryGap: false,
        axisLine: { lineStyle: { color: 'rgba(148,163,184,0.5)' } },
        axisLabel: { color: '#64748B', fontSize: 12, fontWeight: 600 },
        axisTick: { show: false },
      },
      yAxis: {
        type: 'value',
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: '#64748B', fontSize: 12, fontWeight: 500 },
        splitLine: { lineStyle: { type: 'dashed', color: 'rgba(148,163,184,0.25)' } },
      },
      series,
    };

    chart.setOption(option);
    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(chartDom);
    return () => {
      ro.disconnect();
      chart.dispose();
    };
  }, [chartNode, title]);

  // 毛玻璃卡片外壳：背景铺水彩图 + 半透明白底 + 白边 + 圆角 + 内外阴影
  return (
    <div
      style={{
        backgroundImage: `url(${背景})`,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        backgroundColor: 'rgba(255, 255, 255, 0.45)',
        backdropFilter: 'blur(24px)',
        WebkitBackdropFilter: 'blur(24px)',
        border: '1px solid rgba(255, 255, 255, 0.8)',
        borderRadius: 24,
        boxShadow: '0 10px 30px rgba(31, 41, 55, 0.18)',
        padding: 30,
      }}
    >
      <div ref={ref} style={{ width: '100%', height, borderRadius: 16 }} />
    </div>
  );
};

export default EtherealLineChart;
