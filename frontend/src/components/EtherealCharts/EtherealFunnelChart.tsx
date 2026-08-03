/**
 * 仙气漏斗图（React 版）—— 自动适配单漏斗 / 对比漏斗
 *
 * ★ 单漏斗（funnel_core）：
 *   严格移植自「可视化模板库/同期群分析/漏斗图组件.js」
 *   淡彩渐变色板 + 右侧 CTR 标签
 *
 * ★ 对比漏斗（funnel_session）：
 *   两个漏斗叠在一起，冷(蓝)=总转化 vs 暖(橙)=当场转化
 *   嵌套对比风格，带图例 + 右侧双列标签
 *
 * 数据来源：后端 funnel.py
 *   funnel_core  → chart_type="funnel", slot="funnel_core"   → series[0] (1个)
 *   funnel_session→ chart_type="funnel", slot="funnel_session"→ series[0,1] (2个)
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

// ─── 单漏斗：淡彩渐变色板 ──────────────────────────────
const FUNNEL_COLORS: Array<[string, string]> = [
  ['#FECDD3', '#FBCFE8'],
  ['#BBF7D0', '#A7F3D0'],
  ['#BAE6FD', '#BFDBFE'],
  ['#DDD6FE', '#E9D5FF'],
  ['#FECDD3', '#FDE68A'],
];

function getFunnelColor(index: number): echarts.graphic.LinearGradient {
  const colors = FUNNEL_COLORS[index % FUNNEL_COLORS.length];
  return new echarts.graphic.LinearGradient(0, 0, 1, 0, [
    { offset: 0, color: colors[0] },
    { offset: 1, color: colors[1] },
  ]);
}

// ─── 对比漏斗：颜色从后端 option.series[].itemStyle.color 取（沿用原组件色板） ──

function formatNumber(val: number): string {
  if (val >= 1000000) return (val / 1000000).toFixed(1) + 'M';
  if (val >= 1000) return (val / 1000).toFixed(0) + 'K';
  return String(val);
}

/** 从 chartNode 提取 series 数组 */
function getSeries(chartNode: Record<string, unknown> | undefined): Array<Record<string, unknown>> {
  return (chartNode?.series as Array<Record<string, unknown>>) || [];
}

/** 从 series 提取 data 数组 */
function getSeriesData(series: Record<string, unknown>): Array<{ name?: string; value?: number }> {
  return (series.data as Array<{ name?: string; value?: number }>) || [];
}

export const EtherealFunnelChart: React.FC<Props> = ({
  chartNode,
  title,
  height = 360,
  cardBgUrl = CARD_BG_URL,
}) => {
  const domRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!domRef.current) return;
    const container = domRef.current;

    // ★ 延迟到下一帧再 init echarts，确保 DOM 布局已完成、容器尺寸正确
    //   （经典网格 EGridLayout 嵌套 BorderBox1 时，同步 useEffect 可能拿到 0 尺寸）
    let myChart: echarts.ECharts | null = null;
    const onResize = () => myChart?.resize();
    window.addEventListener('resize', onResize);

    const rafId = requestAnimationFrame(() => {
      // 清空容器，避免 re-render 时旧 canvas 残留导致图形不更新/空白
      container.innerHTML = '';

      // 卡片样式（毛玻璃统一）；cardBgUrl 为空时跳过（仪表盘走 theme 卡片）
      if (cardBgUrl) {
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
      } else {
        container.style.position = 'relative';
      }
      container.style.boxSizing = 'border-box';
      container.style.overflow = 'hidden';

      // chartNode 就是 option 本身（EGridLayout 传入 { ...chart.option }）
      const allSeries = getSeries(chartNode);

      // 创建 ECharts 容器
      const chartDom = document.createElement('div');
      chartDom.style.width = '100%';
      chartDom.style.height = '100%';
      container.appendChild(chartDom);

      myChart = echarts.init(chartDom, null, {
        renderer: 'canvas',
        devicePixelRatio: window.devicePixelRatio > 1 ? window.devicePixelRatio : 2,
      });

      // ════════════════════════════════════════════
      // 分支 A：对比漏斗（2 个 series）
      // ════════════════════════════════════════════
      if (allSeries.length >= 2) {
        const dataA = getSeriesData(allSeries[0]); // 总转化
        const dataB = getSeriesData(allSeries[1]); // 当场转化
        const maxVal = Math.max(
          ...(dataA.map((d) => d.value || 0)),
          ...(dataB.map((d) => d.value || 0)),
          1,
        );
        // 颜色沿用模板库仙气色板：外层=蓝渐变(第3组)，内层=粉金渐变(第5组)
        const colorA = FUNNEL_COLORS[2]; // ['#BAE6FD', '#BFDBFE']
        const colorB = FUNNEL_COLORS[4]; // ['#FECDD3', '#FDE68A']
        const nameA = String(allSeries[0].name || '总转化');
        const nameB = String(allSeries[1].name || '当场转化');

        const option: echarts.EChartsCoreOption = {
          backgroundColor: 'transparent',
          // 对比漏斗不设内部 title（外层已有标题，避免重复）
          legend: {
            data: [
              { name: nameA, icon: 'roundRect', itemStyle: { color: colorA[0] } },
              { name: nameB, icon: 'roundRect', itemStyle: { color: colorB[0] } },
            ],
            left: 'center',
            top: 10,
            textStyle: { color: '#64748B', fontSize: 12, fontWeight: 500 },
            itemWidth: 14,
            itemHeight: 14,
            itemGap: 24,
          },
          tooltip: {
            trigger: 'item',
            formatter: (p: { seriesName: string; name: string; value: number }) => {
              const pct = maxVal > 0 ? ((p.value / maxVal) * 100).toFixed(0) : '0';
              return `<b>${p.seriesName}</b><br/>${p.name}: ${formatNumber(p.value)} (${pct}%)`;
            },
            backgroundColor: 'rgba(255,255,255,0.92)',
            borderColor: 'rgba(200,210,230,0.6)',
            borderWidth: 1,
            textStyle: { color: '#334155', fontSize: 13 },
            extraCssText: 'box-shadow: 0 4px 12px rgba(0,0,0,0.08); border-radius: 8px;',
          },
          series: [
            {
              type: 'funnel',
              name: nameA,
              left: '15%',
              width: '70%',
              min: 0,
              max: maxVal,
              sort: 'none',
              gap: 4,
              label: {
                show: true,
                position: 'inside',
                formatter: '{b}',
                fontSize: 14,
                fontWeight: 'bold',
                color: '#334155',
                textBorderColor: 'transparent',
                textBorderWidth: 0,
              },
              labelLine: { show: false },
              itemStyle: {
                color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                  { offset: 0, color: colorA[0] },
                  { offset: 1, color: colorA[1] },
                ]),
                borderColor: 'rgba(255,255,255,0.7)',
                borderWidth: 1,
                shadowBlur: 12,
                shadowColor: 'rgba(0,0,0,0.06)',
                shadowOffsetY: 2,
              },
              emphasis: { label: { fontSize: 15 } },
              data: dataA.map((d) => ({ name: String(d.name || ''), value: Number(d.value ?? 0) })),
            } as echarts.FunnelSeriesOption,
            {
              type: 'funnel',
              name: nameB,
              left: '15%',
              width: '70%',
              min: 0,
              max: maxVal,
              sort: 'none',
              gap: 4,
              label: { show: false },
              itemStyle: {
                color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                  { offset: 0, color: colorB[0] },
                  { offset: 1, color: colorB[1] },
                ]),
                borderColor: 'rgba(255,255,255,0.85)',
                borderWidth: 2,
                shadowBlur: 14,
                shadowColor: 'rgba(0,0,0,0.08)',
                shadowOffsetY: 2,
              },
              emphasis: { label: { fontSize: 15 } },
              data: dataB.map((d) => ({ name: String(d.name || ''), value: Number(d.value ?? 0) })),
            } as echarts.FunnelSeriesOption,
          ],
        };

        myChart.setOption(option);

      // ════════════════════════════════════════════
      // 分支 B：单漏斗（1 个 series）—— 原有逻辑
      // ════════════════════════════════════════════
      } else {
        const seriesData = getSeriesData(allSeries[0] || {});
        const totalValue = seriesData.length > 0 ? (seriesData[0].value || 1) : 1;

        const option: echarts.EChartsCoreOption = {
          backgroundColor: 'transparent',
          title: {
            text: title || String(chartNode?.title || '转化漏斗'),
            left: 'center',
            top: 8,
            textStyle: { color: '#334155', fontSize: 16, fontWeight: 600 },
          },
          tooltip: {
            trigger: 'item',
            formatter: (p: { name: string; value: number }) => {
              const pct = ((p.value / totalValue) * 100).toFixed(0);
              return `<b>${p.name}</b><br/>数值: ${formatNumber(p.value)}<br/>占比: ${pct}%`;
            },
            backgroundColor: 'rgba(255,255,255,0.92)',
            borderColor: 'rgba(200,210,230,0.6)',
            borderWidth: 1,
            textStyle: { color: '#334155', fontSize: 13 },
            extraCssText: 'box-shadow: 0 4px 12px rgba(0,0,0,0.08); border-radius: 8px;',
          },
          series: [
            {
              type: 'funnel',
              left: '15%',
              right: '15%',
              top: 56,
              bottom: 24,
              min: 0,
              max: totalValue,
              sort: 'descending',
              minSize: '35%',
              maxSize: '100%',
              gap: 18,
              label: {
                show: true,
                position: 'inside',
                formatter: '{b}',
                fontSize: 14,
                fontWeight: 'bold',
                color: '#334155',
                textBorderColor: 'transparent',
                textBorderWidth: 0,
              },
              labelLine: { show: false },
              itemStyle: {
                borderColor: 'rgba(255,255,255,0.9)',
                borderWidth: 1,
                shadowBlur: 14,
                shadowColor: 'rgba(0,0,0,0.06)',
                shadowOffsetY: 2,
              },
              emphasis: {
                itemStyle: { shadowBlur: 28, shadowColor: 'rgba(0,0,0,0.12)' },
                label: { fontSize: 15, fontWeight: 'bold' },
              },
              data: seriesData.map((item, idx) => ({
                name: String(item.name || ''),
                value: Number(item.value ?? 0),
                itemStyle: { color: getFunnelColor(idx), opacity: 0.82 },
              })),
            } as echarts.FunnelSeriesOption,
          ],
        };

        myChart.setOption(option);
      }
    });

    return () => {
      cancelAnimationFrame(rafId);
      window.removeEventListener('resize', onResize);
      myChart?.dispose();
    };
  }, [chartNode, title]);

  return <div ref={domRef} style={{ width: '100%', height, borderRadius: 24 }} />;
};

export default EtherealFunnelChart;
