/**
 * 智能排版大屏 · 图表注册表
 *
 * 把后端 SmartLayoutResponse.charts[] 中的单条图表，按 chart_type 映射到
 * 现有的「仙气图表组件」(EtherealChart) 渲染。EtherealChart 内部已按 chart_type
 * 归一化并分发到具体组件（pie/bar/line/radar/dual_axis/heatmap/hbar/ranking/
 * table/metric/funnel/bubble/graph），无需在此重复映射。
 *
 * 这里仅做一层薄封装：统一把后端 option 作为 chartNode 传入，并处理
 * 表格类（table）与同环比表格（table_data）的渲染优先级。
 */
import React from 'react';
import EtherealChart from '../EtherealCharts/EtherealChart';
import type { SmartLayoutChart } from '../../types/dashboard';

/**
 * 渲染单个智能排版图表。
 * @param chart 后端下发的单条图表（含 slot/option/chart_type/table_data 等）
 * @param height 可选高度覆盖（由布局容器按 sizeClass 设定）
 */
export function renderSmartChart(chart: SmartLayoutChart, height?: number): React.ReactElement {
  const { slot, chart_type, title, option, table_data, raw_data } = chart;

  // 表格类：chart_type 命中 table 系列即视为表格。
  // 优先用 table_data（同环比结构化数据），否则用 option ——
  // EtherealTable 已增强，能从 option.series(type:'table') 兜底解析 columns/rows，
  // 因此即使后端未填 table_data（恒为 null），表格也能正常渲染。
  // ★ 兼容所有以 _table 结尾或带 table 关键字的真实大屏类型（与 SmartDashboard.isTableChart 对齐）
  if (['table', 'analysis_table', 'cohort_table', 'rank_table', 'retention_table', 'cohort_retention', 'tabular', 'grid', 'list', 'detail'].includes((chart_type || '').toLowerCase()) || /_table$|^table_/.test((chart_type || '').toLowerCase())) {
    const tableNode = (table_data || option) as Record<string, unknown>;
    return (
      <EtherealChart
        slot={slot}
        chartType="table"
        chartNode={tableNode}
        title={title}
      />
    );
  }

  // 同期群热力图：把 raw_data 扁平清单一并传入，组件内部优先用扁平清单渲染
  if ((chart_type || '').toLowerCase() === 'cohort_heatmap' && raw_data) {
    return (
      <EtherealChart
        slot={slot}
        chartType={chart_type}
        chartNode={{ ...(option as Record<string, unknown>), data: raw_data } as Record<string, unknown>}
        title={title}
      />
    );
  }

  return (
    <EtherealChart
      slot={slot}
      chartType={chart_type}
      chartNode={option as Record<string, unknown>}
      data={raw_data as Array<Record<string, unknown>> | undefined}
      title={title}
    />
  );
}

/** 是否表格类（用于布局提示，与 computeLayout.isFullWidth 对齐） */
export function isTableChart(chartType: string): boolean {
  const t = (chartType || '').toLowerCase();
  return t === 'table' || t === 'cohort_heatmap' || t === 'heatmap';
}
