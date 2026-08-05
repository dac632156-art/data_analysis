/**
 * 仙气排行图（水平条形图）
 * 对应「可视化模板库/同期群分析/排行图组件.js」的 React 化移植。
 *
 * 支持两种数据形态：
 *  1. CLV 类 ranking：{ 排名, 用户ID, 价值 } → 显示「TOP1 · 用户ID」
 *  2. 漏斗渠道质量：{ 渠道, CR_overall, System_Action } → 显示「渠道名」
 *
 * 数据来源：chartNode.data（分析包路径）或 data prop（VisualizationRenderer / EGridLayout 兜底），
 * 与气泡图方案一致。
 */
import React, { useEffect, useRef } from 'react';
import * as echarts from 'echarts/core';
import { BarChart } from 'echarts/charts';
import { GridComponent, TooltipComponent, ToolboxComponent, TitleComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import type { EChartsCoreOption } from 'echarts/core';
import 背景 from '../../assets/ethereal/背景.png';

echarts.use([BarChart, GridComponent, TooltipComponent, ToolboxComponent, TitleComponent, CanvasRenderer]);

// TOP1 → TOP15 淡彩渐变配色：低饱和、仙气柔雾风，相邻排名保持色相区分
const GRADIENT_COLORS: [string, string][] = [
  ['#FECDD3', '#E9D5FF'], // 1  粉 → 紫
  ['#BFDBFE', '#BBF7D0'], // 2  蓝 → 青绿
  ['#FDE68A', '#FBCFE8'], // 3  浅黄 → 粉红
  ['#FDE68A', '#BBF7D0'], // 4  浅黄 → 浅绿
  ['#FBCFE8', '#FED7AA'], // 5  粉红 → 蜜橙
  ['#BAE6FD', '#DDD6FE'], // 6  天蓝 → 淡紫
  ['#FED7AA', '#BBF7D0'], // 7  蜜橙 → 浅绿
  ['#DDD6FE', '#93C5FD'], // 8  淡紫 → 蓝
  ['#FDA4AF', '#FEF08A'], // 9  玫瑰 → 浅黄
  ['#A7F3D0', '#FBCFE8'], // 10 薄荷 → 粉红
  ['#FDBA74', '#C7D2FE'], // 11 橙 → 靛蓝
  ['#E9D5FF', '#BAE6FD'], // 12 薰衣草 → 天蓝
  ['#FECDD3', '#FDE68A'], // 13 粉 → 浅黄
  ['#93C5FD', '#FBCFE8'], // 14 蓝 → 粉红
  ['#F5D0FE', '#BBF7D0'], // 15 丁香 → 浅绿
];

// 状态语义色（仅用于「紧急预警」——劣质/低价值渠道，用红系提示）
const WARNING_GRADIENT: [string, string] = ['#FDA4AF', '#FB7185']; // 红

function isWarning(action: string): boolean {
  return /预警|Warning|告警|Alert|劣质|Low/i.test(action);
}
// ★ 注意：原先的 HEALTHY_GRADIENT 是纯绿（#86EFAC→#34D399），
//   会导致「渠道转化质量」这类带 System_Action="优质/高价值" 的排行图
//   整图渲染成单一绿色，用户反馈「排行图应该是渐变色，这个都是绿色」。
//   现改为：除紧急预警外，一律使用 GRADIENT_COLORS 多色渐变（保留排名色相区分），
//   不再返回纯绿实色。

function buildGradient(colors: [string, string]): echarts.graphic.LinearGradient {
  return new echarts.graphic.LinearGradient(0, 0, 1, 0, [
    { offset: 0, color: colors[0] },
    { offset: 1, color: colors[1] },
  ]);
}

function getGradient(index: number, action?: string): echarts.graphic.LinearGradient {
  // 1) 仅「紧急预警」（劣质/低价值）保留红系语义色，提示风险
  if (action && isWarning(action)) return buildGradient(WARNING_GRADIENT);
  // 2) 默认仙气淡彩渐变（粉紫青绿低饱和，相邻排名保持色相区分）。
  //    ★ 不读取后端单一纯色、不使用纯绿实色——保证排行图永远是多色渐变。
  //      配色统一由仙气组件 GRADIENT_COLORS 接管（用户要求配色按组件来，不乱改）。
  const colors = GRADIENT_COLORS[index % GRADIENT_COLORS.length];
  return buildGradient(colors);
}

function formatNumber(n: number): string {
  if (!Number.isFinite(n)) return '0';
  if (n >= 10000) return (n / 10000).toFixed(1).replace(/\.0$/, '') + '万';
  if (n >= 1000) return n.toLocaleString('zh-CN');
  return String(n.toFixed(n % 1 === 0 ? 0 : 1));
}

/** 自动推断分类字段（category）和数值字段（value）。
 *
 * 简化策略（不依赖任何硬编码字段名，纯运行时类型推断）：
 *  - 数值字段：rows[0] 中第一个 number 类型的 key（排除 System_Action 等元数据列）
 *  - 分类字段：除元数据列与数值字段外，第一个非空字符串类型的 key
 *  - 状态字段：若存在 System_Action / action / status，取其作为预警/优质判定
 *
 * 这样能同时适配：
 *  - CLV ranking：{ 排名: string, 用户ID: string, 价值: number }
 *  - 漏斗渠道质量：{ 渠道: string, CR_overall: number, System_Action: string }
 *  - 任何后端 chart_type="ranking" 的图，只要给一行 {string, number, ...} 即可
 */
function inferFields(rows: Array<Record<string, unknown>>) {
  if (rows.length === 0) {
    return { categoryField: '排名', valueField: '价值', actionField: '' };
  }
  const sample = rows[0];
  const keys = Object.keys(sample);

  // 元数据列：用于着色但不参与分类/数值
  const metaKeys = new Set(['System_Action', 'action', 'status', 'chart_type', 'slot', 'title', 'type', 'color', 'x', 'y']);

  // 数值字段：第一个 number 类型的 key（最稳定的语义信号）
  const valueCandidates = keys.filter(
    (k) => !metaKeys.has(k) && typeof sample[k] === 'number',
  );
  const valueField = valueCandidates[0] || '';

  // 分类字段：除元数据列与数值字段外，第一个非空字符串/数字 key
  const categoryCandidates = keys.filter(
    (k) => !metaKeys.has(k) && k !== valueField && sample[k] != null && sample[k] !== '',
  );
  const categoryField = categoryCandidates[0] || keys.find((k) => k !== valueField) || keys[0];

  // 状态字段：用于预警/优质着色
  const actionField = keys.includes('System_Action')
    ? 'System_Action'
    : keys.includes('action')
    ? 'action'
    : keys.includes('status')
    ? 'status'
    : '';

  return { categoryField, valueField, actionField };
}

interface Props {
  /** 扁平 rows（来自 chart.raw_data），字段可自适应：CLV(排名/用户ID/价值) 或 漏斗(渠道/CR_overall/System_Action) */
  chartNode: Record<string, unknown>;
  /** VisualizationRenderer / EGridLayout 传入的扁平数据兜底 */
  data?: Array<Record<string, unknown>>;
  title?: string;
  height?: number | string;
  cardBgUrl?: string;
}

export const EtherealRankChart: React.FC<Props> = ({ chartNode, data, title, height, cardBgUrl }) => {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    const chartDom = ref.current;

    // 1. 卡片样式接管（毛玻璃 + 背景.png）
    chartDom.style.backgroundImage = `url(${cardBgUrl || 背景})`;
    chartDom.style.backgroundSize = 'cover';
    chartDom.style.backgroundPosition = 'center';
    chartDom.style.borderRadius = '24px';
    chartDom.style.backgroundColor = 'transparent';
    chartDom.style.backdropFilter = 'blur(18px)';
    chartDom.style.webkitBackdropFilter = 'blur(18px)';
    chartDom.style.border = '1px solid rgba(255, 255, 255, 0.6)';
    chartDom.style.boxShadow = '0 20px 40px -10px rgba(99, 102, 241, 0.12), inset 0 1px 0 rgba(255, 255, 255, 0.8)';
    chartDom.style.padding = '30px 36px';
    chartDom.style.boxSizing = 'border-box';
    chartDom.style.overflow = 'hidden';

    const node = chartNode || {};

    // 三层数据源兜底，保证任何入口（数据分析模块 / 仪表盘经典网格 / 已保存旧分析包）都有数据：
    //  1) chartNode.data（分析包路径扁平清单）
    //  2) data prop（VisualizationRenderer / EGridLayout 传的 chart.raw_data）
    //  3) chartNode.option（标准 ECharts option：yAxis.data + series[0].data，必定存在）
    let rows: Array<Record<string, unknown>> = [];
    const rawData = Array.isArray(node.data) ? (node.data as Array<Record<string, unknown>>) : [];
    const fallbackData = Array.isArray(data) ? (data as Array<Record<string, unknown>>) : [];
    if (rawData.length > 0) {
      rows = rawData;
    } else if (fallbackData.length > 0) {
      rows = fallbackData;
    } else {
      // 兜底：从标准 ECharts option 反推扁平清单 [{分类, 数值, 颜色}]
      const opt = (node.option ?? node) as Record<string, unknown>;
      const yData = (opt.yAxis && (opt.yAxis as Record<string, unknown>).data) as Array<unknown> | undefined;
      const series = (Array.isArray(opt.series) ? opt.series : []) as Array<Record<string, unknown>>;
      const s0Data = (series[0]?.data ?? []) as Array<Record<string, unknown> | number | string>;
      if (Array.isArray(yData) && yData.length > 0 && s0Data.length > 0) {
        rows = yData.map((cat, idx) => {
          const sd = s0Data[idx] as Record<string, unknown> | number | string;
          const val = typeof sd === 'object' && sd !== null ? (sd.value as number) : (sd as number);
          const itemStyle = typeof sd === 'object' && sd !== null ? (sd.itemStyle as Record<string, unknown> | undefined) : undefined;
          const color = itemStyle && typeof itemStyle.color === 'string' ? (itemStyle.color as string) : undefined;
          return { 渠道: String(cat), 数值: val ?? 0, __color: color } as Record<string, unknown>;
        });
      }
    }

    const { categoryField, valueField, actionField } = inferFields(rows);

    // 2. 解析数据并按数值降序（排行图习惯：大的在上）
    const sorted = rows
      .map((item) => ({
        category: String(item[categoryField] ?? ''),
        value: parseFloat(String(item[valueField] ?? '0')) || 0,
        action: actionField ? String(item[actionField] ?? '') : '',
      }))
      .sort((a, b) => b.value - a.value);

    // 3. y 轴标签：若原始分类是 TOPx 形式，则保留 TOPx · 名称；否则直接显示分类名
    const categories = sorted.map((d) => {
      const cat = d.category.trim();
      if (/^TOP\d+$/i.test(cat)) return cat; // 纯 TOP1
      const topPrefix = cat.match(/^(TOP\d+)\s*[·\.\-:]?\s*(.*)$/i);
      if (topPrefix) {
        const label = topPrefix[2].trim();
        return label ? `${topPrefix[1]} ${label}` : topPrefix[1];
      }
      return cat;
    });
    const values = sorted.map((d) => d.value);

    // 4. 构建 series data（胶囊形 + 渐变 + 右侧数值 label）
    const barData = values.map((val, idx) => ({
      value: val,
        itemStyle: {
          color: getGradient(idx, sorted[idx].action),
        borderRadius: [20, 20, 20, 20],
        opacity: 0.72,
        borderColor: 'rgba(255,255,255,0.6)',
        borderWidth: 1.5,
        shadowBlur: 16,
        shadowColor: 'rgba(0,0,0,0.07)',
        shadowOffsetY: 3,
      },
      label: {
        show: true,
        position: 'right' as const,
        formatter: (p: { value: number }) => formatNumber(p.value),
        fontSize: 13,
        fontWeight: 600,
        color: '#475569',
        offset: [10, 0] as [number, number],
      },
    }));

    // 5. y 轴最大值在最上方：categories 与 barData 需反转
    const yCategories = categories.slice().reverse();
    const yBarData = barData.slice().reverse();

    const titleText = title || (typeof node.title === 'string' ? node.title : '') || 'TOP 排行';

    const option: EChartsCoreOption = {
      backgroundColor: 'transparent',
      title: {
        text: titleText,
        left: 'center',
        top: 8,
        textStyle: { color: '#1E293B', fontSize: 16, fontWeight: 600 },
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        backgroundColor: 'rgba(255, 255, 255, 0.96)',
        borderColor: '#E2E8F0',
        borderWidth: 1,
        padding: [10, 14],
        textStyle: { color: '#475569', fontWeight: 'bold', fontSize: 13 },
        extraCssText: 'box-shadow: 0 8px 16px -3px rgba(0,0,0,0.12); border-radius: 12px;',
        formatter: (params: Array<{ name: string; value: number }>) => {
          const d = params[0];
          const actionHtml = actionField
            ? `<div style="color:#94A3B8;font-size:12px;margin-top:4px;">${actionField}: ${sorted.find((s) => String(s.category) === d.name || d.name.includes(String(s.category)))?.action || ''}</div>`
            : '';
          return `<div style="font-weight:700;color:#1E293B;margin-bottom:4px;">${d.name}</div>
            <div style="color:#64748B;">${valueField}: <b style="color:#1E293B;">${formatNumber(d.value)}</b></div>${actionHtml}`;
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
      grid: {
        top: 60,
        left: 70,
        right: 120,
        bottom: 30,
        containLabel: false,
      },
      xAxis: {
        type: 'value',
        show: false, // 隐藏 X 轴，数值通过 label 显示在条形右侧
      },
      yAxis: {
        type: 'category',
        data: yCategories,
        inverse: false,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          show: true,
          color: '#334155',
          fontWeight: 600,
          fontSize: 14,
          margin: 12,
          formatter: (name: string) => {
            const match = name.match(/^(TOP\d+)\s+(.*)$/i);
            if (match) {
              const num = parseInt(match[1].replace(/TOP/i, ''), 10);
              const label = match[2].trim();
              return `{num|${num}.} {name|${label}}`;
            }
            return `{name|${name}}`;
          },
          rich: {
            num: {
              color: '#64748B',
              fontWeight: 700,
              fontSize: 14,
              width: 28,
              align: 'right' as const,
            },
            name: {
              color: '#1E293B',
              fontWeight: 600,
              fontSize: 14,
              padding: [0, 0, 0, 6] as [number, number, number, number],
            },
          },
        },
      },
      series: [
        {
          type: 'bar',
          data: yBarData,
          barWidth: '55%',
          barGap: '25%',
          emphasis: {
            itemStyle: {
              opacity: 0.95,
              shadowBlur: 18,
              shadowColor: 'rgba(0,0,0,0.15)',
            },
          },
          animationDelay: (idx: number) => idx * 80,
          animationEasing: 'elasticOut',
        },
      ],
      animationDuration: 1200,
      animationEasing: 'cubicOut',
    };

    const chart = echarts.init(chartDom);
    chart.setOption(option, true);
    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(chartDom);
    return () => {
      ro.disconnect();
      chart.dispose();
    };
  }, [chartNode, data, title, cardBgUrl]);

  // 高度自适应：行数少则压低，避免大片空白
  const rowCount = Array.isArray(chartNode?.data)
    ? (chartNode.data as Array<unknown>).length
    : (Array.isArray(data) ? data.length : 0);
  const usedHeight = height || Math.max(240, Math.min(420, rowCount * 64 + 90));

  return <div ref={ref} style={{ width: '100%', height: usedHeight, borderRadius: 24 }} />;
};

export default EtherealRankChart;
