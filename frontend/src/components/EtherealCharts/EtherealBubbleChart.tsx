import React, { useEffect, useRef } from 'react';
import * as echarts from 'echarts/core';
import { ScatterChart } from 'echarts/charts';
import { GridComponent, TooltipComponent, ToolboxComponent, TitleComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import type { EChartsCoreOption } from 'echarts/core';
import 背景 from '../../assets/ethereal/背景.png';

echarts.use([ScatterChart, GridComponent, TooltipComponent, ToolboxComponent, TitleComponent, CanvasRenderer]);

// 对齐模板库 气泡图组件.js BASE_COLORS（第 57 行）：淡彩色板，按标签出现顺序抽色（含淡紫）
const BASE_COLORS = ['#FDE047', '#5AA9D6', '#A78BFA', '#A3E635', '#FB7185', '#FECDD3'];
const FALLBACK_COLOR = '#FDE047';

// 坐标排序规则（对齐原版 xOrder / yOrder）
const xOrder = ['低价值', '中价值', '高价值'];
const yOrder = ['已流失', '流失预警'];

interface Props {
  chartNode: Record<string, unknown>;
  height?: number;
}

export const EtherealBubbleChart: React.FC<Props> = ({ chartNode, height = 420 }) => {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    const chartDom = ref.current;
    // 卡片样式接管（对齐原版第 17-29 行）
    chartDom.style.backgroundImage = `url(${背景})`;
    chartDom.style.backgroundSize = 'cover';
    chartDom.style.backgroundPosition = 'center';
    chartDom.style.borderRadius = '24px';
    chartDom.style.backgroundColor = 'transparent';
    chartDom.style.backdropFilter = 'blur(18px)';
    chartDom.style.WebkitBackdropFilter = 'blur(18px)';
    chartDom.style.border = '1px solid rgba(255, 255, 255, 0.6)';
    chartDom.style.boxShadow = '0 20px 40px -10px rgba(99, 102, 241, 0.12), inset 0 1px 0 rgba(255, 255, 255, 0.8)';
    chartDom.style.padding = '30px 36px';
    chartDom.style.boxSizing = 'border-box';
    chartDom.style.overflow = 'hidden';
    chartDom.style.position = 'relative';

    const chart = echarts.init(chartDom);

    const title = (chartNode.title as string) || '气泡矩阵';
    const rawData = (chartNode.data as Array<Record<string, unknown>>) || [];
    // 字段语义映射：对齐原版 utils.js renderEtherealBubbleChart 的写法，
    // x/y/color 优先从 chartNode 读取，默认值与原版保持一致（colorField=挽回优先级）。
    // 历史 bug：React 版曾硬编码为 '标签'/'聚类'/'标签'（按价值层涂色），
    // 与「挽回优先级气泡矩阵」的语义不符，现已恢复原版契约。
    const xField = (chartNode.x as string) || '价值层';
    const yField = (chartNode.y as string) || '流失状态';
    const colorField = (chartNode.color as string) || '挽回优先级';
    const sizeField = '人数';

    const xCategories: string[] = [];
    const yCategories: string[] = [];
    const priorityLabels: string[] = [];
    const sizeValues: number[] = [];
    rawData.forEach((item) => {
      const xv = String(item[xField] ?? '');
      const yv = String(item[yField] ?? '');
      const cv = String(item[colorField] ?? '');
      if (xv && !xCategories.includes(xv)) xCategories.push(xv);
      if (yv && !yCategories.includes(yv)) yCategories.push(yv);
      if (cv && !priorityLabels.includes(cv)) priorityLabels.push(cv);
      if (item[sizeField] !== undefined) sizeValues.push(Number(item[sizeField]));
    });

    const priorityColorMap: Record<string, string> = {};
    priorityLabels.forEach((label, idx) => {
      priorityColorMap[label] = BASE_COLORS[idx % BASE_COLORS.length];
    });
    const getBubbleColor = (p: string) => priorityColorMap[p] || FALLBACK_COLOR;

    const sortedXCategories = [...xCategories].sort((a, b) => {
      const ia = xOrder.indexOf(a);
      const ib = xOrder.indexOf(b);
      return (ia !== -1 ? ia : 999) - (ib !== -1 ? ib : 999);
    });
    const sortedYCategories = [...yCategories].sort((a, b) => {
      const ia = yOrder.indexOf(a), ib = yOrder.indexOf(b);
      return (ia !== -1 ? ia : 999) - (ib !== -1 ? ib : 999);
    });

    const minSize = 20, maxSize = 75;
    const minCount = sizeValues.length ? Math.min(...sizeValues) : 1;
    const maxCount = sizeValues.length ? Math.max(...sizeValues) : 10;
    const scaleSize = (count: number) =>
      maxCount === minCount ? (minSize + maxSize) / 2 : minSize + ((count - minCount) / (maxCount - minCount)) * (maxSize - minSize);

    const scatterData = rawData.map((item) => {
      const xv = String(item[xField] ?? '');
      const yv = String(item[yField] ?? '');
      const sv = Number(item[sizeField] ?? 1);
      const priority = String(item[colorField] ?? '');
      const xi = sortedXCategories.indexOf(xv);
      const yi = sortedYCategories.indexOf(yv);
      const bubbleColor = getBubbleColor(priority);
      return {
        value: [xi, yi, sv],
        rawXLabel: xv,
        rawYLabel: yv,
        priority,
        name: `${xv} | ${yv}`,
        symbolSize: scaleSize(sv),
        itemStyle: {
          color: bubbleColor,
          opacity: 0.38,
          borderColor: 'rgba(255,255,255,0.75)',
          borderWidth: 2.5,
          shadowBlur: 20,
          shadowColor: 'rgba(0,0,0,0.06)',
        },
        label: { show: false },
      };
    });

    const option: EChartsCoreOption = {
      backgroundColor: 'transparent',
      title: { text: title, left: 'center', top: 8, textStyle: { color: '#1E293B', fontSize: 16, fontWeight: 600 } },
      tooltip: {
        trigger: 'item',
        backgroundColor: 'rgba(255, 255, 255, 0.96)',
        borderColor: '#E2E8F0',
        borderWidth: 1,
        padding: [12, 16],
        textStyle: { color: '#475569', fontWeight: 'bold' },
        extraCssText: 'box-shadow: 0 10px 20px -3px rgba(0,0,0,0.12); border-radius: 14px;',
        formatter: (p: { data: { rawXLabel: string; rawYLabel: string; priority: string; value: number[] } }) => {
          const d = p.data;
          const dc = getBubbleColor(d.priority);
          return `<div style="margin-bottom:6px;font-weight:700;color:#1E293B;font-size:13px;">${d.rawXLabel} × ${d.rawYLabel}</div>
            <div style="display:flex;align-items:center;gap:6px;margin:3px 0;">
              <span style="display:inline-block;width:11px;height:11px;border-radius:50%;background:${dc};"></span>
              <span>${colorField}: <b>${d.priority}</b></span>
            </div>
            <div style="margin:3px 0;">${sizeField}: <b>${d.value[2]}</b></div>`;
        },
      },
      toolbox: {
        right: 24, top: 12, z: 9999,
        iconStyle: { borderColor: '#8B7FB0' },
        feature: { saveAsImage: { title: '下载图片', show: true } },
      },
      legend: { show: false },
      grid: { top: 60, left: 100, right: 160, bottom: 60, containLabel: false },
      xAxis: {
        type: 'category',
        data: sortedXCategories,
        name: xField,
        nameLocation: 'middle',
        nameGap: 38,
        nameTextStyle: { color: '#64748B', fontWeight: 600, fontSize: 13 },
        axisLabel: { show: true, color: '#334155', fontWeight: 600, fontSize: 12, margin: 14 },
        axisLine: { lineStyle: { color: 'rgba(148,163,184,0.45)', width: 1.5 } },
        axisTick: { show: true, length: 5, lineStyle: { color: 'rgba(148,163,184,0.35)' } },
        splitLine: { lineStyle: { type: 'dashed', color: 'rgba(148,163,184,0.22)', width: 1 } },
      },
      yAxis: {
        type: 'category',
        data: sortedYCategories,
        name: yField,
        nameLocation: 'middle',
        nameGap: 52,
        nameTextStyle: { color: '#64748B', fontWeight: 600, fontSize: 13 },
        axisLabel: { show: true, color: '#334155', fontWeight: 600, fontSize: 12, margin: 14 },
        axisLine: { lineStyle: { color: 'rgba(148,163,184,0.45)', width: 1.5 } },
        axisTick: { show: true, length: 5, lineStyle: { color: 'rgba(148,163,184,0.35)' } },
        splitLine: { lineStyle: { type: 'dashed', color: 'rgba(148,163,184,0.22)', width: 1 } },
      },
      series: [{
        type: 'scatter',
        data: scatterData,
        symbol: 'circle',
        symbolKeepAspect: true,
        emphasis: { scale: 1.15, itemStyle: { shadowBlur: 22, shadowColor: 'rgba(0,0,0,0.18)', borderColor: '#fff', borderWidth: 3 } },
      }],
    };

    chart.setOption(option, true);

    // DOM 图例（对齐原版第 252-275 行）
    let legendEl = chartDom.querySelector('.ethereal-bubble-legend') as HTMLDivElement | null;
    if (legendEl) legendEl.remove();
    legendEl = document.createElement('div');
    legendEl.className = 'ethereal-bubble-legend';
    legendEl.style.cssText =
      'position:absolute;right:32px;top:85px;z-index:100;pointer-events:none;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;';
    let legendHtml = `<div style="font-weight:bold;font-size:13px;color:#1E293B;margin-bottom:12px;">${colorField}</div>`;
    priorityLabels.forEach((label) => {
      const c = getBubbleColor(label);
      legendHtml += `<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
        <span style="display:inline-block;width:14px;height:14px;border-radius:50%;background:${c};opacity:0.85;flex-shrink:0;"></span>
        <span style="font-size:13px;color:#334155;font-weight:500;">${label}</span></div>`;
    });
    legendEl.innerHTML = legendHtml;
    chartDom.appendChild(legendEl);

    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(chartDom);
    return () => {
      ro.disconnect();
      chart.dispose();
    };
  }, [chartNode]);

  return <div ref={ref} style={{ width: '100%', height, borderRadius: 24 }} />;
};
