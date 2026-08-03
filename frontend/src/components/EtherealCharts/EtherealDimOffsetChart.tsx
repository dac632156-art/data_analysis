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

    // 把 y 轴技术拼接串转成人话：
    // 连续维度区间 "(32.958, 39.0]" -> "32~39岁"；分类维度原样保留
    const humanizeLabel = (raw: string): string => {
      const m = raw.match(/^\(([-\d.]+),\s*([-\d.]+)\]$/);
      if (m) {
        const lo = Number(m[1]).toFixed(0);
        const hi = Number(m[2]).toFixed(0);
        return `${lo}~${hi}岁`;
      }
      // 形如 "商品类目|美妆个护" -> "美妆个护"
      const pipe = raw.indexOf('|');
      if (pipe >= 0) return raw.slice(pipe + 1);
      return raw;
    };

    const dimGroups: Record<string, Array<{
      name: string; value: number; rawName: string;
      churnPct: number; normalPct: number;
    }>> = {};
    rawData.forEach((item) => {
      const dim = String(item['维度'] || '未知');
      if (!dimGroups[dim]) dimGroups[dim] = [];
      const rawName = String(item['维度取值'] || '');
      dimGroups[dim].push({
        name: humanizeLabel(rawName),
        rawName,
        value: Number(item['偏移值'] ?? 0),
        churnPct: Number(item['流失占比'] ?? 0),
        normalPct: Number(item['正常占比'] ?? 0),
      });
    });

    const orderedDims = dimsConfig.length > 0 ? dimsConfig.filter((d) => dimGroups[d]) : Object.keys(dimGroups);

    const seriesData: Array<{
      category: string; rawName: string; value: number;
      dimension: string; dimIndex: number; churnPct: number; normalPct: number;
    }> = [];
    orderedDims.forEach((dimName, dimIdx) => {
      (dimGroups[dimName] || []).forEach((item) => {
        seriesData.push({
          category: item.name, rawName: item.rawName, value: item.value,
          dimension: dimName, dimIndex: dimIdx,
          churnPct: item.churnPct, normalPct: item.normalPct,
        });
      });
    });

    // 按原始偏移值降序（易流失在前），但显示时翻转方向：
    // 易流失（偏移>0）→ 红色、画在左侧（value 取负）；更稳定（偏移<0）→ 绿色、画在右侧
    seriesData.sort((a, b) => b.value - a.value);
    const sortedCategories = seriesData.map((d) => d.category);
    const sortedRawNames = seriesData.map((d) => d.rawName);
    const sortedValues = seriesData.map((d) => -d.value); // 翻转：易流失落负轴(左)
    const sortedDims = seriesData.map((d) => d.dimension);
    const sortedChurn = seriesData.map((d) => d.churnPct);
    const sortedNormal = seriesData.map((d) => d.normalPct);

    const dimPalette = ['#FCCDDF', '#C8E1F5', '#D7EFE5', '#E2C9F3', '#FCDDC8', '#BAC2F0'];
    // 重配色（做法1）：红=易流失(危险)、绿=更稳定(安全)
    const RISK_COLOR = '#FCA5A5'; // 红（易流失）
    const SAFE_COLOR = '#A7E6D7'; // 绿（更稳定）

    const getDimColor = (dimName: string) => dimPalette[orderedDims.indexOf(dimName) % dimPalette.length];

    const barData = sortedValues.map((val, i) => {
      // val 已取负：val<0 表示原始偏移>0 → 易流失；val>0 表示原始偏移<0 → 更稳定
      const isRisk = val < 0;
      const barColor = isRisk ? RISK_COLOR : SAFE_COLOR;
      const churnPct = sortedChurn[i];
      const normalPct = sortedNormal[i];
      const verdict = isRisk ? '更易流失' : (val > 0 ? '更稳定' : '持平');
      // 标签：柱顶显示带正负号的偏移值（与 X 轴 +10pp/-5pp 风格一致）
      // 负值柱(易流失)→ 标签在柱子右端外侧靠近 0pp；正值柱(更稳定)→ 标签在柱子右端外侧远 0pp
      const sign = val > 0 ? '+' : (val < 0 ? '-' : '');
      const labelText = `${sign}${Math.round(Math.abs(val))}pp`;
      const labelColor = isRisk ? '#DC2626' : (val > 0 ? '#059669' : '#64748B');
      return {
        value: val,
        itemStyle: {
          color: barColor,
          opacity: 0.9,
          borderRadius: isRisk ? [6, 0, 0, 6] : [0, 6, 6, 0],
          borderColor: 'rgba(255,255,255,0.5)',
          borderWidth: 1,
        },
        label: {
          show: true,
          position: 'outside',
          formatter: labelText,
          color: labelColor,
          fontSize: 12,
          fontWeight: 700,
          distance: 6,
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
          const churnPct = sortedChurn[p.dataIndex];
          const normalPct = sortedNormal[p.dataIndex];
          // p.value 已翻转：<0 表示原始偏移>0 → 易流失
          const isRisk = p.value < 0;
          const offset = Math.abs(p.value).toFixed(1);
          const verdict = isRisk ? '更容易流失' : (p.value > 0 ? '更稳定' : '持平');
          const verdictColor = isRisk ? '#DC2626' : (p.value > 0 ? '#059669' : '#64748B');
          return `<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
              <span style="font-weight:700;">${p.name}</span>
              <span style="color:#94A3B8;font-size:11px;">(${dimName})</span>
          </div>
          <div style="margin-top:4px;padding-top:4px;border-top:1px solid #E2E8F0;line-height:1.6;">
            已流失人群中占比：<b style="color:#DC2626">${churnPct.toFixed(1)}%</b><br/>
            正常人群中占比：<b style="color:#059669">${normalPct.toFixed(1)}%</b><br/>
            相差 <b>${offset}pp</b> → <b style="color:${verdictColor}">${verdict}</b>
          </div>`;
        },
      },
      legend: { show: false },
      toolbox: {
        right: 20,
        top: 44,
        z: 9999,
        feature: {
          saveAsImage: { title: '下载图片', show: true },
        },
      },
      grid: { top: 56, left: 110, right: 120, bottom: 50, containLabel: false },
      xAxis: {
        type: 'value',
        position: 'top',
        min: (value: { min: number }) => Math.min(value.min, -30),
        max: (value: { max: number }) => Math.max(value.max, 40),
        axisLabel: { color: '#64748B', fontWeight: 500, fontSize: 12, formatter: (v: number) => `${v > 0 ? '+' : ''}${v}pp` },
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
      graphic: [
        // 右上角装饰性图例（红=更易流失 / 绿=更稳定），与截图风格一致
        {
          type: 'rect',
          right: 168,
          top: 14,
          shape: { width: 14, height: 14, r: 3 },
          style: { fill: RISK_COLOR },
        },
        {
          type: 'text',
          right: 110,
          top: 15,
          style: { text: '更易流失', fill: '#64748B', fontSize: 12, fontWeight: 500 },
        },
        {
          type: 'rect',
          right: 60,
          top: 14,
          shape: { width: 14, height: 14, r: 3 },
          style: { fill: SAFE_COLOR },
        },
        {
          type: 'text',
          right: 8,
          top: 15,
          style: { text: '更稳定', fill: '#64748B', fontSize: 12, fontWeight: 500 },
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
