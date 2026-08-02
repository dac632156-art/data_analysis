/**
 * 仙气高级双轴图（React 版）
 * ★ 严格移植自「可视化模板库/同期群分析/双轴图组件.js」，逻辑未篡改
 * 唯一改动：echarts 用项目实例；数据由 props 传入（不再 fetch）。
 */
import React, { useEffect, useRef } from 'react';
import * as echarts from 'echarts/core';

const CARD_BG_URL = new URL('../../assets/ethereal/背景.png', import.meta.url).href;

interface Props {
  chartNode?: Record<string, unknown>;
  title?: string;
  height?: number;
  cardBgUrl?: string;
}

export const EtherealDualAxisChart: React.FC<Props> = ({ chartNode, title, height = 380, cardBgUrl = CARD_BG_URL }) => {
  const headerRef = useRef<HTMLDivElement>(null);
  const kpiRowRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!chartRef.current) return;
    const chartDom = chartRef.current;
    chartDom.style.width = '100%';
    chartDom.style.height = '380px';

    let xAxisData: string[] = [];
    let gmvData: number[] = [];
    let profitData: number[] = [];

    const node = chartNode || {};
    // 兼容三种结构：
    //  A) 标准 ECharts option（后端 /analysis/process-datasets）：series 直接在 node 上
    //  B) 私有嵌套结构：node.option.series
    //  C) 私有扁平结构：node.data = [{首单月, 净GMV, 净毛利}, ...]
    const opt: Record<string, unknown> = (node.option as Record<string, unknown>) || node;
    const seriesArr = (opt.series as Array<Record<string, unknown>>) || [];

    if (Array.isArray(node.data) && node.data.length > 0) {
      const xField = (node.x as string) || '首单月';
      const arr = node.data as Array<Record<string, unknown>>;
      xAxisData = arr.map((item) => String(item[xField] || ''));
      gmvData = arr.map((item) => Number(item['净GMV'] || item.gmv || 0));
      profitData = arr.map((item) => Number(item['净毛利'] || item.profit || 0));
    } else if (seriesArr.length > 0) {
      const xAxisNode = (opt.xAxis as Record<string, unknown>) || {};
      xAxisData = (Array.isArray(xAxisNode.data) ? xAxisNode.data : (xAxisNode as any)) as string[] || [];
      const toNumArr = (d: unknown): number[] => {
        if (!Array.isArray(d)) return [];
        return d.map((v) => (typeof v === 'object' && v !== null ? Number((v as Record<string, unknown>).value) || 0 : Number(v) || 0));
      };
      gmvData = toNumArr(seriesArr[0]?.data);
      profitData = seriesArr[1] ? toNumArr(seriesArr[1].data) : [];
    }

    const totalGMV = gmvData.reduce((a, b) => a + (Number(b) || 0), 0);
    const totalProfit = profitData.reduce((a, b) => a + (Number(b) || 0), 0);
    const avgMargin = totalGMV > 0 ? (totalProfit / totalGMV) * 100 : 0;

    if (headerRef.current) {
      const optTitle = (opt.title as Record<string, unknown>)?.text as string | undefined;
      const headerTitle = (node.title as string) || optTitle || title || 'Net GMV & Net Profit';
      headerRef.current.innerHTML = `
        <div style="font-size: 18px; font-weight: 700; color: #1E293B; letter-spacing: 0.5px; text-transform: uppercase;">
          ${headerTitle} <span style="color: #94A3B8; font-weight: 500; text-transform: none; margin-left: 8px;">| 净GMV与净毛利对比</span>
        </div>
        <div style="background: rgba(255,255,255,0.6); border: 1px solid rgba(255,255,255,0.9); padding: 6px 14px; border-radius: 12px; font-size: 12px; font-weight: 600; color: #475569;">
          Cohort View
        </div>`;
    }
    if (kpiRowRef.current) {
      kpiRowRef.current.innerHTML = `
        <div style="text-align:center; display:flex; flex-direction:column; gap:4px;">
          <div style="font-size:11px; color:#64748B; font-weight:600; text-transform:uppercase;">Total Net GMV</div>
          <div style="font-size:26px; color:#0F172A; font-weight:700;">¥${(totalGMV / 1000).toFixed(1)}K</div>
        </div>
        <div style="text-align:center; display:flex; flex-direction:column; gap:4px;">
          <div style="font-size:11px; color:#64748B; font-weight:600; text-transform:uppercase;">Total Net Profit</div>
          <div style="font-size:26px; color:#0F172A; font-weight:700;">¥${(totalProfit / 1000).toFixed(1)}K</div>
        </div>
        <div style="text-align:center; display:flex; flex-direction:column; gap:4px;">
          <div style="font-size:11px; color:#64748B; font-weight:600; text-transform:uppercase;">Avg. Profit Margin</div>
          <div style="font-size:26px; color:#0F172A; font-weight:700;">${avgMargin.toFixed(1)}%</div>
        </div>`;
    }

    const innerChart = echarts.init(chartRef.current);
    innerChart.setOption({
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(255,255,255,0.85)',
        borderColor: '#E2E8F0',
        borderWidth: 1,
        padding: [12, 16],
        textStyle: { color: '#475569', fontWeight: 'bold' },
        extraCssText: 'box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); backdrop-filter: blur(8px); border-radius: 12px;',
        axisPointer: { type: 'none' },
        formatter: (params: Array<{ name: string; seriesName: string; value: number; marker: string }>) => {
          let html = `<div style="margin-bottom:8px;color:#64748B;font-size:13px;">${params[0].name}</div>`;
          params.forEach((item) => {
            let marker = item.marker;
            if (item.seriesName.includes('Profit') || item.seriesName.includes('净毛利')) {
              marker = '<span style="display:inline-block;margin-right:6px;border-radius:50%;width:10px;height:10px;box-sizing:border-box;background-color:#fff;border:2px solid #F472B6;"></span>';
            }
            const valueStr = Number(item.value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            html += `<div style="display:flex;justify-content:space-between;align-items:center;gap:20px;margin-bottom:4px;">
              <span style="display:flex;align-items:center;">${marker}${item.seriesName}</span>
              <span style="color:#0F172A;font-weight:700;">${valueStr}</span></div>`;
          });
          return html;
        },
      },
      legend: { data: ['Net GMV (净GMV)', 'Net Profit (净毛利)'], bottom: 0, itemGap: 30, textStyle: { color: '#64748B', fontWeight: 600, fontSize: 13 }, icon: 'circle' },
      grid: { top: 30, left: 10, right: 10, bottom: 40, containLabel: true },
      xAxis: {
        type: 'category',
        data: xAxisData,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: '#64748B', fontWeight: 600, fontSize: 12, margin: 16 },
      },
      yAxis: [
        {
          type: 'value',
          name: 'NET GMV (¥)',
          nameTextStyle: { color: '#94A3B8', fontWeight: 600, fontSize: 11, padding: [0, 0, 0, 30] },
          position: 'left',
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: { color: '#94A3B8', fontWeight: 600, formatter: (val: number) => (val === 0 ? '0' : val / 1000 + 'K') },
          splitLine: { lineStyle: { type: 'dashed', color: 'rgba(0,0,0,0.05)' } },
        },
        {
          type: 'value',
          name: 'NET PROFIT (¥)',
          nameTextStyle: { color: '#94A3B8', fontWeight: 600, fontSize: 11, padding: [0, 30, 0, 0] },
          position: 'right',
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: { color: '#94A3B8', fontWeight: 600, formatter: (val: number) => (val === 0 ? '0' : val / 1000 + 'K') },
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: 'Net GMV (净GMV)',
          type: 'bar',
          yAxisIndex: 0,
          data: gmvData,
          barWidth: 26,
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(195,225,250,0.95)' },
              { offset: 1, color: 'rgba(195,225,250,0.6)' },
            ]),
            borderRadius: 14,
          },
        },
        {
          name: 'Net Profit (净毛利)',
          type: 'line',
          yAxisIndex: 1,
          data: profitData,
          smooth: true,
          symbol: 'circle',
          symbolSize: 8,
          itemStyle: { color: '#ffffff', borderColor: '#F472B6', borderWidth: 2, shadowColor: 'rgba(244,114,182,0.8)', shadowBlur: 6 },
          lineStyle: { color: '#F472B6', width: 3, shadowColor: 'rgba(244,114,182,0.3)', shadowBlur: 10, shadowOffsetY: 6 },
        },
      ],
    } as echarts.EChartsCoreOption);

    const onResize = () => innerChart.resize();
    window.addEventListener('resize', onResize);
    return () => {
      window.removeEventListener('resize', onResize);
      innerChart.dispose();
    };
  }, [chartNode, title]);

  return (
    <div
      style={{
        background: 'rgba(255,255,255,0.45)',
        backdropFilter: 'blur(24px)',
        WebkitBackdropFilter: 'blur(24px)',
        border: '1px solid rgba(255,255,255,0.8)',
        borderRadius: 24,
        boxShadow: '0 20px 40px -10px rgba(0,0,0,0.05), inset 0 1px 0 rgba(255,255,255,0.9)',
        padding: 30,
        boxSizing: 'border-box',
        display: 'flex',
        flexDirection: 'column',
        gap: 20,
        width: '100%',
        height,
      }}
    >
      <div ref={headerRef} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid rgba(0,0,0,0.05)', paddingBottom: 15 }} />
      <div ref={kpiRowRef} style={{ display: 'flex', justifyContent: 'space-around', alignItems: 'center', padding: '5px 20px 0' }} />
      <div ref={chartRef} />
    </div>
  );
};
