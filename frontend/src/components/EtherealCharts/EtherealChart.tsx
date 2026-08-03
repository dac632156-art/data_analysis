/**
 * 仙气图表统一分发组件（React 版）
 * 对应原版「可视化模板库/utils.js → renderChartBySlot」的 CHART_REGISTRY 分发逻辑
 *
 * 用法：<EtherealChart slot="rfm_pie" chartNode={{...}} height={360} />
 *
 * slot → 组件的映射照搬原版 CHART_REGISTRY，未改动语义。
 */
import React from 'react';
import { EtherealPieChart } from './EtherealPieChart';
import { EtherealLineChart } from './EtherealLineChart';
import { EtherealBarChart } from './EtherealBarChart';
import { EtherealRadarChart } from './EtherealRadarChart';
import { EtherealBubbleChart } from './EtherealBubbleChart';
import { EtherealNetworkChart } from './EtherealNetworkChart';
import { EtherealRankChart } from './EtherealRankChart';
import { EtherealDimOffsetChart } from './EtherealDimOffsetChart';
import { EtherealRetentionMatrix } from './EtherealRetentionMatrix';
import { EtherealMetricCard } from './EtherealMetricCard';
import { EtherealTable } from './EtherealTable';
import { EtherealDualAxisChart } from './EtherealDualAxisChart';
import { EtherealFunnelChart } from './EtherealFunnelChart';
import EChartView from '../EChartView';

interface Props {
  slot: string;
  /** 图表类型（与后端 chart_type 对齐），如 pie/bar/line/radar/heatmap... 按类型分发，不依赖具体 slot 名 */
  chartType?: string;
  /** 从分析包 / mock JSON 提取的 chart 节点（含 data / series / columns 等） */
  chartNode?: Record<string, unknown>;
  /** 扁平数据（部分组件可直接传） */
  data?: Array<Record<string, unknown>>;
  title?: string;
  filter?: Record<string, string>;
  cardBgUrl?: string;
  /** 下三角矩阵专用：'percent'（留存率，默认）| 'number'（客单价/净毛利等数值） */
  valueFormat?: 'percent' | 'number';
}

/** 已实现的仙气组件类型 */
const IMPLEMENTED = new Set(['pie', 'bar', 'line', 'radar', 'dual_axis', 'heatmap', 'hbar', 'bubble', 'ranking', 'table', 'metric', 'graph', 'funnel']);

/** 把后端五花八门的 chart_type 归一化为有限的仙气组件类型；
 * 未实现的类型（funnel/ranking/sankey/graph 等）原样返回，由调用方显式报错，不静默兜底。 */
function normalizeChartType(t: string): string {
  const s = (t || '').toLowerCase();
  if (s === 'pie') return 'pie';
  if (s === 'bar') return 'bar';
  if (s === 'line' || s.endsWith('_line') || s.endsWith('_trend') || s === 'rfm_line') return 'line';
  if (s === 'radar') return 'radar';
  if (s === 'dual_axis') return 'dual_axis';
  if (s === 'heatmap' || s === 'cohort_heatmap') return 'heatmap';
  if (s === 'bubble_matrix') return 'bubble';
  if (s === 'graph' || s === 'chord' || s === 'chord_diagram') return 'graph';
  if (s === 'hbar_family') return 'hbar';
  if (s === 'ranking' || s === 'horizontal_bar' || s === 'h_bar' || s === 'hbar_rank') return 'ranking';
  if (s === 'table') return 'table';
  if (s === 'metric' || s === 'card') return 'metric';
  if (s === 'funnel') return 'funnel';
  return s; // sankey/graph 等未实现组件，原样返回走报错分支
}

/**
 * 下三角矩阵（cohort_heatmap）的 valueFormat 自动判定：
 * - 留存率（cohort_retention）是 0~1 比例 → 默认 percent（×100 + %）
 * - 客单价（cohort_arpu）/ 净毛利（cohort_c_netmargin_heat）是金额 → 强制 number（纯数值不带 %）
 * 调用方若显式传 valueFormat，以调用方为准（兼容手动覆盖）。
 */
function resolveValueFormat(
  chartType: string | undefined,
  slot: string,
  explicit?: 'percent' | 'number',
): 'percent' | 'number' {
  if (explicit) return explicit;
  if (chartType === 'cohort_heatmap' && slot !== 'cohort_retention') return 'number';
  return 'percent';
}

export const EtherealChart: React.FC<Props> = ({ slot, chartType, chartNode, data, title, filter, cardBgUrl, valueFormat }) => {
  const raw = data as Array<Record<string, unknown>> | undefined;

  // 优先用 chartType；其次从 chartNode 里取；都没有再用 slot 兜底（兼容老预览页写法）
  const rawType =
    chartType ||
    (chartNode?.chart_type as string) ||
    slot; // slot 本身有时也含类型线索（如 rfm_pie / cohort_a_line）
  const type = normalizeChartType(rawType);

  switch (type) {
    case 'pie':
      return <EtherealPieChart option={chartNode as Record<string, unknown>} title={title} cardBgUrl={cardBgUrl} />;
    case 'heatmap': {
      // 两种数据来源，最终都用仙气矩阵组件渲染（不回退老组件）：
      // 1) 分析包路径：扁平清单在 chartNode.data 或 raw(=chart.raw_data)；
      // 2) 仪表盘路径：后端 cohort 数据在 option.series[0].data，无扁平清单 → 从 series 反推。
      let matrixData = (chartNode?.data as Array<Record<string, unknown>>) || raw || [];
      if (matrixData.length === 0 && chartNode?.series?.[0]?.data) {
        // 从 ECharts heatmap option 反推仙气矩阵要的扁平清单 [{首单月, Index_j, value}]
        const seriesData = (chartNode.series[0].data as Array<[number, number, number]>);
        const xAxisData = (chartNode.xAxis?.data as Array<string>) || [];
        const yAxisData = (chartNode.yAxis?.data as Array<string>) || [];
        matrixData = seriesData.map(([xi, yi, v]) => ({
          首单月: yAxisData[yi] ?? String(yi),
          Index_j: xi,
          value: v,
        }));
      }
      return <EtherealRetentionMatrix chartNode={chartNode} rawData={matrixData} title={title} cardBgUrl={cardBgUrl} valueFormat={resolveValueFormat(rawType, slot, valueFormat)} />;
    }
    case 'bar':
      return <EtherealBarChart chartNode={chartNode} title={title} cardBgUrl={cardBgUrl} />;
    case 'line':
      return <EtherealLineChart chartNode={chartNode} title={title} cardBgUrl={cardBgUrl} />;
    case 'metric':
      return <EtherealMetricCard metricData={chartNode as { title?: string; label?: string; value?: number | string; change?: number | string; unit?: string }} />;
    case 'dual_axis':
      return <EtherealDualAxisChart chartNode={chartNode} title={title} cardBgUrl={cardBgUrl} />;
    case 'radar':
      return <EtherealRadarChart chartNode={chartNode} title={title} cardBgUrl={cardBgUrl} />;
    case 'table':
      return <EtherealTable chartNode={chartNode} title={title} cardBgUrl={cardBgUrl} />;
    case 'hbar': {
      // 维度偏移图：优先用 data prop（后端 ChartData.data 扁平清单，含 维度/维度取值/偏移值），
      // 与预览页 VisualizationRenderer 路径一致；不回退老组件、不改 EtherealDimOffsetChart 组件内部。
      const hbarData = (data && data.length > 0)
        ? data
        : (chartNode?.data as Array<Record<string, unknown>>) || [];
      return <EtherealDimOffsetChart chartNode={{ ...chartNode, data: hbarData }} title={title} filter={filter} cardBgUrl={cardBgUrl} />;
    }
    case 'ranking': {
      // 横向排行图统一走仙气排行组件（适配漏斗渠道/CLV TOP 等所有 ranking 类型）。
      // 数据来源三层兜底：chartNode.data（分析包扁平清单）→ data prop（仪表盘 raw_data）→
      //   chartNode.option 反推（ECharts 标准 option，无扁平清单时也能渲染）。
      // funnel_channel 也走此分支：EtherealRankChart 已专门支持 {渠道, CR_overall, System_Action} 形态。
      const rankData = (data && data.length > 0)
        ? data
        : (chartNode?.data as Array<Record<string, unknown>>) || [];
      return <EtherealRankChart chartNode={{ ...chartNode, data: rankData }} title={title} cardBgUrl={cardBgUrl} />;
    }
    case 'bubble': {
      // 三层数据源（从富到穷，保留后端元信息最完整的）：
      //  1) data prop = VisualizationRenderer 传入的 chart.raw_data（4 列完整：价值层/流失状态/挽回优先级/人数）
      //  2) chartNode.data（EtherealPreview / 预览页直接传扁平清单）
      //  3) chartNode.series[0].data 反推（仪表盘/大屏旧 option 路径，仅 3 元 value，丢失「挽回优先级」维度，
      //     仅作兜底；反推出的标签命名为「标签/聚类/人数」+ 空优先级，此时图例退化为按价值层涂色）。
      let bubbleData = (raw && raw.length > 0)
        ? raw
        : ((chartNode?.data as Array<Record<string, unknown>>) || []);
      if (bubbleData.length === 0 && (chartNode as { series?: Array<{ data?: Array<{ value?: [unknown, unknown, unknown] }> }> })?.series?.[0]?.data) {
        const seriesData = (chartNode as { series: Array<{ data: Array<{ value?: [unknown, unknown, unknown] }> }> }).series[0].data;
        bubbleData = seriesData.map((pt) => {
          const v = pt.value || [null, null, null];
          return {
            标签: v[0] ?? '',
            聚类: v[1] ?? '',
            人数: v[2] ?? 0,
          };
        });
      }
      return <EtherealBubbleChart chartNode={{ ...chartNode, data: bubbleData }} title={title} cardBgUrl={cardBgUrl} />;
    }
    case 'graph': {
      // 关联图（和弦图）：商品关联网络图走自研关联图组件，替换默认 ECharts graph 节点连线。
      // 数据来源三层兜底：data prop（边表，含 lift）→ chartNode.data（边表）→ option.series[0]（节点/边），
      // 组件内部再自动去重构建节点表（对齐模板库 关联图组件.js 第 71-96 行）。
      const netData = (raw && raw.length > 0)
        ? raw
        : ((chartNode?.data as Array<Record<string, unknown>>) || []);
      return <EtherealNetworkChart chartNode={{ ...chartNode, data: netData }} title={title} cardBgUrl={cardBgUrl} />;
    }
    case 'funnel': {
      // 转化漏斗图：数据来自后端 funnel.py → option.series[0].data = [{name,value}]
      // 与可视化模板库/漏斗图组件.js 渲染逻辑一致（淡彩渐变 + 右侧 CTR 标签）
      return <EtherealFunnelChart chartNode={chartNode} title={title} cardBgUrl={cardBgUrl} />;
    }
    default:
      // 暂无量身定制的仙气组件，直接用原生 ECharts 渲染（保证图表永远可见，不退化成占位）
      return <EChartView option={chartNode as never} title={title} hideTitle />;
  }
};

export default EtherealChart;
