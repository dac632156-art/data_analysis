/**
 * 仙气维度偏移图（React 版）
 * ★ 严格移植自「可视化模板库/同期群分析/维度偏移图组件.js」，逻辑未篡改
 * 唯一改动：echarts 用项目实例；cardBgUrl 用 import.meta.url 解析；数据由 props 传入。
 */
import React, { useEffect, useRef } from 'react';
import * as echarts from 'echarts/core';

const CARD_BG_URL = new URL('../../assets/ethereal/背景.png', import.meta.url).href;

interface Props {
  chartNode?: Record<string, unknown>;
  title?: string;
  height?: number;
  /** 维度筛选，如 { 维度: '城市' } */
  filter?: Record<string, string>;
  cardBgUrl?: string;
}

export const EtherealDimOffsetChart: React.FC<Props> = ({
  chartNode,
  title,
  height = 360,
  filter,
  cardBgUrl = CARD_BG_URL,
}) => {
  const domRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!domRef.current) return;
    const container = domRef.current;
    container.style.backgroundImage = `url('${cardBgUrl}')`;
    container.style.backgroundSize = 'cover';
    container.style.backgroundPosition = 'center';
    container.style.borderRadius = '24px';
    container.style.backgroundColor = 'transparent';
    container.style.backdropFilter = 'blur(18px)';
    container.style.webkitBackdropFilter = 'blur(18px)';
    container.style.border = '1px solid rgba(255,255,255,0.6)';
    container.style.boxShadow = '0 20px 40px -10px rgba(99,102,241,0.12), inset 0 1px 0 rgba(255,255,255,0.8)';
    container.style.padding = '30px 36px';
    container.style.boxSizing = 'border-box';
    container.style.overflow = 'hidden';

    let rawData = (chartNode?.data as Array<Record<string, unknown>>) || [];
    const targetDim = (filter && filter['维度']) || (chartNode?._filter as Record<string, string> | undefined)?.['维度'] || null;
    if (targetDim) rawData = rawData.filter((item) => String(item['维度'] || '') === targetDim);

    const dimsConfig = ((chartNode?.chart_config as Record<string, unknown> | undefined)?.dims as string[]) || [];

    const dimGroups: Record<string, Array<{ name: string; value: number }>> = {};
    rawData.forEach((item) => {
      const dim = String(item['维度'] || '未知');
      if (!dimGroups[dim]) dimGroups[dim] = [];
      dimGroups[dim].push({
        name: String(item['维度取值'] || ''),
        value: Number(item['偏移值'] ?? 0),
      });
    });

    const orderedDims = dimsConfig.length > 0 ? dimsConfig.filter((d) => dimGroups[d]) : Object.keys(dimGroups);

    const seriesData: Array<{ category: string; value: number; dimension: string; dimIndex: number }> = [];
    orderedDims.forEach((dimName, dimIdx) => {
      (dimGroups[dimName] || []).forEach((item) => {
        seriesData.push({ category: item.name, value: item.value, dimension: dimName, dimIndex: dimIdx });
      });
    });

    seriesData.sort((a, b) => b.value - a.value);
    const sortedCategories = seriesData.map((d) => d.category);
    const sortedValues = seriesData.map((d) => d.value);
    const sortedDims = seriesData.map((d) => d.dimension);

    const dimPalette = ['#FCCDDF', '#C8E1F5', '#D7EFE5', '#E2C9F3', '#FCDDC8', '#BAC2F0'];
    const NEG_COLOR = '#A7E6D7';
    const POS_COLOR = '#FCCDDF';

    const getDimColor = (dimName: string) => dimPalette[orderedDims.indexOf(dimName) % dimPalette.length];

    const barData = sortedValues.map((val) => {
      const isPositive = val >= 0;
      const barColor = isPositive ? POS_COLOR : NEG_COLOR;
      return {
        value: val,
        itemStyle: {
          color: barColor,
          opacity: 0.85,
          borderRadius: isPositive ? [0, 6, 6, 0] : [6, 0, 0, 6],
          borderColor: 'rgba(255,255,255,0.5)',
          borderWidth: 1,
        },
        label: {
          show: true,
          position: isPositive ? 'right' : 'left',
          color: isPositive ? '#E11D48' : '#059669',
          fontWeight: 700,
          fontSize: 12,
          distance: 8,
          formatter: (p: { value: number }) => (p.value >= 0 ? '+' : '') + p.value.toFixed(1),
        },
      };
    });

    const richStyles: Record<string, object> = {};
    orderedDims.forEach((dimName) => {
      richStyles[dimName] = {
        backgroundColor: getDimColor(dimName),
        padding: [2, 6],
        borderRadius: 3,
        color: '#1E293B',
        fontSize: 12,
        fontWeight: 500,
      };
    });

    const myChart = echarts.init(container);
    myChart.setOption({
      backgroundColor: 'transparent',
      title: {
        text: title || String(chartNode?.title || '维度偏移分析'),
        left: 'center',
        top: 8,
        textStyle: { color: '#1E293B', fontSize: 16, fontWeight: 600 },
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        backgroundColor: 'rgba(255,255,255,0.95)',
        borderColor: '#E2E8F0',
        borderWidth: 1,
        padding: [10, 14],
        textStyle: { color: '#475569', fontWeight: 'bold' },
        extraCssText: 'box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); border-radius: 12px;',
        formatter: (params: Array<{ name: string; value: number; dataIndex: number }>) => {
          const p = params[0];
          const dimName = sortedDims[p.dataIndex];
          const color = getDimColor(dimName);
          const val = p.value;
          const sign = val >= 0 ? '+' : '';
          return `<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
              <span style="display:inline-block;width:10px;height:10px;border-radius:3px;background:${color};"></span>
              <span style="font-weight:700;">${p.name}</span>
              <span style="color:#94A3B8;font-size:11px;">(${dimName})</span>
          </div>
          <div style="margin-top:4px;padding-top:4px;border-top:1px solid #E2E8F0;">
              偏移值: <b style="color:${val >= 0 ? '#059669' : '#DC2626'}">${sign}${val.toFixed(1)}pp</b>
          </div>`;
        },
      },
      toolbox: {
        right: 20,
        top: 10,
        z: 9999,
        feature: {
          saveAsImage: { title: '下载图片', show: true },
        },
      },
      grid: { top: 56, left: 100, right: 56, bottom: 24, containLabel: false },
      xAxis: {
        type: 'value',
        position: 'top',
        min: (value: { min: number }) => Math.min(value.min, -30),
        max: (value: { max: number }) => Math.max(value.max, 40),
        axisLabel: { color: '#64748B', fontWeight: 500, fontSize: 12, formatter: (v: number) => `${v}` },
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { show: true, lineStyle: { type: 'dashed', color: 'rgba(148,163,184,0.25)' } },
      },
      yAxis: {
        type: 'category',
        data: sortedCategories,
        inverse: true,
        axisLabel: {
          color: '#334155',
          fontWeight: 600,
          fontSize: 13,
          margin: 14,
          formatter: (value: string) => {
            const idx = sortedCategories.indexOf(value);
            if (idx >= 0) {
              const dimName = sortedDims[idx];
              return `{${dimName}|${value}}`;
            }
            return value;
          },
          rich: richStyles,
        },
        axisLine: { show: false },
        axisTick: { show: false },
      },
      series: [
        {
          type: 'bar',
          data: barData,
          barWidth: 18,
          barGap: '20%',
          markLine: {
            silent: true,
            symbol: 'none',
            lineStyle: { color: '#94A3B8', type: 'dashed', width: 1 },
            data: [{ xAxis: 0 }],
            label: { show: false },
          },
        },
      ],
    } as echarts.EChartsCoreOption);

    const onResize = () => myChart.resize();
    window.addEventListener('resize', onResize);
    return () => {
      window.removeEventListener('resize', onResize);
      myChart.dispose();
    };
  }, [chartNode, title, filter]);

  return <div ref={domRef} style={{ width: '100%', height, borderRadius: 24 }} />;
};

export default EtherealDimOffsetChart;
