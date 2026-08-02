import React, { useEffect, useRef } from 'react';
import * as echarts from 'echarts/core';
import { BarChart } from 'echarts/charts';
import { GridComponent, TooltipComponent, ToolboxComponent, GraphicComponent, TitleComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import type { EChartsCoreOption } from 'echarts/core';
import 背景 from '../../assets/ethereal/背景.png';

echarts.use([BarChart, GridComponent, TooltipComponent, ToolboxComponent, GraphicComponent, TitleComponent, CanvasRenderer]);

// 8 色粉彩调色板（严格对齐原版 echarts_柱状图.js 第 22 行）
const customPalette = ['#FCCDDF', '#C8E1F5', '#E2C9F3', '#D7EFE5', '#FCDDC8', '#E8C9CE', '#F9F1C6', '#BAC2F0'];

function withAlpha(hex: string, alpha: string): string {
  return `${hex}${alpha}`;
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

function extractSeriesValues(raw: unknown): number[] {
  if (!Array.isArray(raw)) return [];
  return raw.map((v) => {
    if (typeof v === 'number') return v;
    if (typeof v === 'object' && v !== null) return Number((v as Record<string, unknown>).value ?? 0);
    return Number(v ?? 0);
  });
}

interface Props {
  chartNode: Record<string, unknown>;
  title?: string;
  height?: number;
}

export const EtherealBarChart: React.FC<Props> = ({ chartNode, title, height = 360 }) => {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    const chartDom = ref.current;
    chartDom.style.backgroundImage = `url(${背景})`;
    chartDom.style.backgroundSize = 'cover';
    chartDom.style.backgroundPosition = 'center';
    chartDom.style.borderRadius = '24px';
    chartDom.style.backgroundColor = 'rgba(255, 255, 255, 0.32)';

    const chart = echarts.init(chartDom);
    const node = chartNode || {};

    const titleText = normalizeTitle(node, title);
    const seriesInput = ((node.series as Array<Record<string, unknown>>) || []);
    const xAxisData = getXData(node);
    const rawData = (node.data as Array<Record<string, unknown>>) || undefined;

    let categories: string[] = xAxisData.length ? xAxisData : [];
    let series: any[] = [];

    // 优先标准 option：按 series 生成柱状图（每柱独立配色，对齐原版）
    if (seriesInput.length > 0 && categories.length > 0) {
      const items: { category: string; seriesIndex: number; valueIndex: number; value: number; color: string }[] = [];
      seriesInput.forEach((s, sIdx) => {
        const vals = extractSeriesValues(s.data);
        vals.forEach((v, vIdx) => {
          items.push({
            category: categories[vIdx] ?? '',
            seriesIndex: sIdx,
            valueIndex: vIdx,
            value: v,
            color: customPalette[(sIdx * vals.length + vIdx) % customPalette.length],
          });
        });
      });

      series = seriesInput.map((s, sIdx) => ({
        name: s.name || `Series ${sIdx + 1}`,
        type: 'bar' as const,
        barWidth: 38,
        data: items
          .filter((it) => it.seriesIndex === sIdx)
          .map((it) => ({
            value: it.value,
            name: it.category,
            itemStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: withAlpha(it.color, 'F0') },
                { offset: 0.1, color: withAlpha(it.color, 'E8') },
                { offset: 1, color: withAlpha(it.color, '70') },
              ]),
              borderRadius: 19,
              borderColor: 'rgba(255, 255, 255, 0.4)',
              borderWidth: 1,
              shadowColor: withAlpha(it.color, '30'),
              shadowBlur: 8,
              shadowOffsetY: 0,
            },
          })),
        label: {
          show: true,
          position: 'top' as const,
          color: '#475569',
          fontWeight: 600,
          fontSize: 13,
          distance: 8,
        },
      }));
    } else if (Array.isArray(rawData) && rawData.length > 0) {
      // 老私有格式兜底
      const xs = (node.x as string) || 'x';
      categories = rawData.map((r) => String(r[xs] ?? ''));
      const yKeys = Object.keys(rawData[0] || {}).filter((k) => k !== xs);

      const items: { category: string; yKey: string; value: number; color: string }[] = [];
      rawData.forEach((r, i) => {
        yKeys.forEach((yk, yi) => {
          items.push({
            category: String(r[xs] ?? ''),
            yKey: yk,
            value: Number(r[yk] ?? 0),
            color: customPalette[(i * yKeys.length + yi) % customPalette.length],
          });
        });
      });

      series = yKeys.map((yKey) => ({
        name: yKey,
        type: 'bar' as const,
        barWidth: 38,
        data: items
          .filter((it) => it.yKey === yKey)
          .map((it) => ({
            value: it.value,
            name: it.category,
            itemStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: withAlpha(it.color, 'F0') },
                { offset: 0.1, color: withAlpha(it.color, 'E8') },
                { offset: 1, color: withAlpha(it.color, '70') },
              ]),
              borderRadius: 19,
              borderColor: 'rgba(255, 255, 255, 0.4)',
              borderWidth: 1,
              shadowColor: withAlpha(it.color, '30'),
              shadowBlur: 8,
              shadowOffsetY: 0,
            },
          })),
        label: {
          show: true,
          position: 'top' as const,
          color: '#475569',
          fontWeight: 600,
          fontSize: 13,
          distance: 8,
        },
      }));
    }

    const option: EChartsCoreOption = {
      title: titleText
        ? {
            text: titleText,
            left: 'center',
            top: 8,
            textStyle: { color: '#1E293B', fontSize: 16, fontWeight: 600 },
          }
        : undefined,
      tooltip: {
        trigger: 'item',
        backgroundColor: 'rgba(255, 255, 255, 0.85)',
        borderColor: '#E2E8F0',
        borderWidth: 1,
        padding: [10, 16],
        textStyle: { color: '#475569', fontWeight: 'bold' },
        extraCssText: 'box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); backdrop-filter: blur(8px); border-radius: 12px;',
        formatter: (p: { data: { value: number; name: string }; dataIndex: number; seriesIndex: number }) => {
          const color = customPalette[(p.seriesIndex * categories.length + p.dataIndex) % customPalette.length];
          return `<div style="display:flex; align-items:center; gap:8px;">
                      <span style="display:inline-block; width:10px; height:10px; border-radius:50%; background-color:${color};"></span>
                      <span>${p.data.name} : ${Number(p.data.value).toFixed(4)}</span>
                  </div>`;
        },
      },
      grid: { left: 56, right: 24, top: titleText ? 56 : 36, bottom: 36, containLabel: true },
      xAxis: {
        type: 'category',
        data: categories,
        axisLabel: { color: '#64748B', fontWeight: 600, fontSize: 13, interval: 0 },
        axisLine: { lineStyle: { color: 'rgba(148,163,184,0.45)' } },
        axisTick: { show: false },
      },
      yAxis: {
        type: 'value',
        axisLabel: { color: '#64748B', fontWeight: 500, fontSize: 13 },
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { show: true, lineStyle: { type: 'dashed', color: 'rgba(255, 255, 255, 0.45)', width: 1 } },
      },
      toolbox: {
        show: true,
        left: 'right',
        right: 20,
        top: 6,
        orient: 'horizontal',
        itemSize: 16,
        itemGap: 12,
        z: 9999,
        iconStyle: { borderColor: '#8B7FB0' },
        feature: { saveAsImage: { title: '下载图片', name: titleText || 'chart' } },
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

  return <div ref={ref} style={{ width: '100%', height, borderRadius: 24 }} />;
};

export default EtherealBarChart;
