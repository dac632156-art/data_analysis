/**
 * ★ 临时预览页：验证全部「仙气水彩图表组件」React 化效果
 * 确认风格后删除本文件并移除路由。
 */
import React from 'react';
import { EtherealChart } from './components/EtherealCharts/EtherealChart';

const SECTION = (t: string) => (
  <h2 style={{ color: '#1E293B', fontSize: 18, fontWeight: 700, margin: '32px 0 12px', borderLeft: '4px solid #F472B6', paddingLeft: 12 }}>
    {t}
  </h2>
);

const DEMO = {
  pie: { title: { text: 'RFM 分层占比' }, series: [{ type: 'pie', data: [
    { name: '高价值核心客户', value: 4200 }, { name: '潜力高价值客户', value: 3100 },
    { name: '沉睡高价值客户', value: 1800 }, { name: '流失预警高价值客户', value: 1200 },
    { name: '稳定普通客户', value: 2500 }, { name: '一般挽留客户', value: 900 } ] }] },
  bar: { title: '各流量来源人数', x: '分层', data: [
    { 分层: '抖音', 人数: 8200 }, { 分层: '小红书', 人数: 6100 }, { 分层: '微信', 人数: 4300 },
    { 分层: '天猫', 人数: 3900 }, { 分层: '线下', 人数: 2100 } ] },
  line: { title: '同期群留存率', x: '首单月', y: '留存率', data: [
    { 首单月: '2025-01', 留存率: 1.0, group: '新客' }, { 首单月: '2025-02', 留存率: 0.82, group: '新客' }, { 首单月: '2025-03', 留存率: 0.71, group: '新客' }, { 首单月: '2025-04', 留存率: 0.65, group: '新客' }, { 首单月: '2025-05', 留存率: 0.58, group: '新客' },
    { 首单月: '2025-01', 留存率: 1.0, group: '老客' }, { 首单月: '2025-02', 留存率: 0.9, group: '老客' }, { 首单月: '2025-03', 留存率: 0.85, group: '老客' }, { 首单月: '2025-04', 留存率: 0.81, group: '老客' }, { 首单月: '2025-05', 留存率: 0.77, group: '老客' },
    { 首单月: '2025-01', 留存率: 1.0, group: '回流' }, { 首单月: '2025-02', 留存率: 0.74, group: '回流' }, { 首单月: '2025-03', 留存率: 0.62, group: '回流' }, { 首单月: '2025-04', 留存率: 0.55, group: '回流' }, { 首单月: '2025-05', 留存率: 0.48, group: '回流' } ] },
  radar: { title: '客户画像雷达', indicators: [
    { name: '消费力', max: 100 }, { name: '频次', max: 100 }, { name: '忠诚度', max: 100 },
    { name: '活跃度', max: 100 }, { name: '社交', max: 100 } ],
    series: [ { name: '高价值', color: '#F472B6', value: [90, 80, 95, 70, 60] },
              { name: '潜力', color: '#8B5CF6', value: [60, 75, 55, 80, 85] } ] },
  bubble: { title: '客户气泡矩阵', data: [
    { 标签: '高价值', 聚类: '高价值', 复购率: 0.8, 留存率: 0.9, 人数: 1200 },
    { 标签: '潜力', 聚类: '潜力', 复购率: 0.5, 留存率: 0.6, 人数: 2400 },
    { 标签: '一般', 聚类: '一般', 复购率: 0.3, 留存率: 0.4, 人数: 3600 },
    { 标签: '流失', 聚类: '流失', 复购率: 0.1, 留存率: 0.2, 人数: 1800 } ] },
  dimOffset: { title: '维度偏移分析', chart_config: { dims: ['城市', '省份', '类目'] }, data: [
    { 维度: '城市', 维度取值: '北京', 偏移值: 12.5 }, { 维度: '城市', 维度取值: '上海', 偏移值: 8.2 },
    { 维度: '省份', 维度取值: '广东', 偏移值: -6.1 }, { 维度: '省份', 维度取值: '浙江', 偏移值: 4.3 },
    { 维度: '类目', 维度取值: '美妆', 偏移值: -9.8 }, { 维度: '类目', 维度取值: '食品', 偏移值: 7.7 } ] },
  retention: [ { 首单月: '2024-07', Index_j: 0, value: 1 }, { 首单月: '2024-07', Index_j: 1, value: 0.82 },
    { 首单月: '2024-07', Index_j: 2, value: 0.71 }, { 首单月: '2024-07', Index_j: 3, value: 0.64 },
    { 首单月: '2024-08', Index_j: 0, value: 1 }, { 首单月: '2024-08', Index_j: 1, value: 0.78 },
    { 首单月: '2024-08', Index_j: 2, value: 0.66 }, { 首单月: '2024-09', Index_j: 0, value: 1 },
    { 首单月: '2024-09', Index_j: 1, value: 0.75 } ],
  // 各同期群客单价 ARPU（下三角，数值模式，不带百分号）
  arpu: [
    { 首单月: '2024-09', Index_j: 0, value: 256.3 }, { 首单月: '2024-09', Index_j: 1, value: 248.6 }, { 首单月: '2024-09', Index_j: 2, value: 233.1 }, { 首单月: '2024-09', Index_j: 3, value: 219.4 },
    { 首单月: '2024-10', Index_j: 0, value: 271.8 }, { 首单月: '2024-10', Index_j: 1, value: 260.2 }, { 首单月: '2024-10', Index_j: 2, value: 242.7 },
    { 首单月: '2024-11', Index_j: 0, value: 289.5 }, { 首单月: '2024-11', Index_j: 1, value: 277.3 },
    { 首单月: '2024-12', Index_j: 0, value: 305.1 },
  ],
  // 各同期群净毛利 ARPU（下三角，数值模式，不带百分号）
  netMargin: [
    { 首单月: '2024-09', Index_j: 0, value: 1234.5 }, { 首单月: '2024-09', Index_j: 1, value: 1188.2 }, { 首单月: '2024-09', Index_j: 2, value: 1102.6 }, { 首单月: '2024-09', Index_j: 3, value: 1043.9 },
    { 首单月: '2024-10', Index_j: 0, value: 1310.7 }, { 首单月: '2024-10', Index_j: 1, value: 1255.4 }, { 首单月: '2024-10', Index_j: 2, value: 1176.8 },
    { 首单月: '2024-11', Index_j: 0, value: 1398.2 }, { 首单月: '2024-11', Index_j: 1, value: 1337.5 },
    { 首单月: '2024-12', Index_j: 0, value: 1486.9 },
  ],
  card: { title: 'ARPU', value: 286.5, change: '+4.2%' },
  table: { title: 'RFM 客户分层汇总', columns: ['客户分层', '人数', '人均GMV', '复购率', '留存率'],
    rows: [ { 客户分层: '高价值核心客户', 人数: 4200, 人均GMV: 1250.5, 复购率: 0.82, 留存率: 0.91 },
            { 客户分层: '潜力高价值客户', 人数: 3100, 人均GMV: 980.2, 复购率: 0.65, 留存率: 0.78 },
            { 客户分层: '流失预警高价值客户', 人数: 1200, 人均GMV: 860.0, 复购率: 0.21, 留存率: 0.34 } ] },
  dual: { title: 'Net GMV & Net Profit', x: '首单月', data: [
    { 首单月: '2025-01', 净GMV: 120000, 净毛利: 38000 }, { 首单月: '2025-02', 净GMV: 135000, 净毛利: 42000 },
    { 首单月: '2025-03', 净GMV: 158000, 净毛利: 51000 }, { 首单月: '2025-04', 净GMV: 142000, 净毛利: 46000 } ] },
};

export default function EtherealPreview() {
  return (
    <div style={{ minHeight: '100vh', padding: 48, background: 'linear-gradient(135deg,#fdf2f8 0%,#eef2ff 50%,#ecfeff 100%)', fontFamily: 'system-ui, sans-serif' }}>
      <h1 style={{ color: '#1E293B', fontSize: 26, fontWeight: 800 }}>仙气水彩图表组件库 · 全量预览（临时）</h1>
      <p style={{ color: '#64748B', marginBottom: 8 }}>全部组件严格照「可视化模板库」原版移植，含水墨纹理、粉彩配色、毛玻璃卡片。</p>

      {SECTION('环形图')}
      <div style={{ width: 480, margin: '0 auto' }}><EtherealChart slot="rfm_pie" chartType="pie" chartNode={DEMO.pie as Record<string, unknown>} /></div>

      {SECTION('柱状图')}
      <EtherealChart slot="clv_a_流量来源" chartType="bar" chartNode={DEMO.bar as Record<string, unknown>} />

      {SECTION('折线图')}
      <EtherealChart slot="cohort_a_line" chartType="line" chartNode={DEMO.line as Record<string, unknown>} />

      {SECTION('雷达图')}
      <div style={{ width: 560, margin: '0 auto' }}><EtherealChart slot="cluster_radar" chartType="radar" chartNode={DEMO.radar as Record<string, unknown>} /></div>

      {SECTION('气泡矩阵图')}
      <EtherealChart slot="bubble_matrix__retention_priority" chartType="bubble" chartNode={DEMO.bubble as Record<string, unknown>} />

      {SECTION('维度偏移图')}
      <EtherealChart slot="hbar__attr_dim_offset" chartType="hbar" chartNode={DEMO.dimOffset as Record<string, unknown>} />

      {SECTION('同期群留存热力图')}
      <EtherealChart slot="cohort_retention" chartType="heatmap" chartNode={{ data: DEMO.retention } as Record<string, unknown>} />

      {SECTION('同期群客单价热力图（数值，不带百分号）')}
      <EtherealChart slot="cohort_arpu" chartType="heatmap" chartNode={{ data: DEMO.arpu } as Record<string, unknown>} />

      {SECTION('同期群净毛利热力图（数值，不带百分号）')}
      <EtherealChart slot="cohort_c_netmargin_heat" chartType="heatmap" chartNode={{ data: DEMO.netMargin } as Record<string, unknown>} />

      {SECTION('指标小卡片')}
      <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
        <div style={{ width: 320, height: 130 }}><EtherealChart slot="card_arpu" chartType="metric" chartNode={DEMO.card as Record<string, unknown>} /></div>
        <div style={{ width: 320, height: 130 }}><EtherealChart slot="card_revenue" chartType="metric" chartNode={{ title: 'GMV', value: 158000, change: '+12.3%' } as Record<string, unknown>} /></div>
      </div>

      {SECTION('双轴图')}
      <EtherealChart slot="dual_axis_profit" chartType="dual_axis" chartNode={DEMO.dual as Record<string, unknown>} />

      {SECTION('表格')}
      <EtherealChart slot="rfm_table" chartType="table" chartNode={DEMO.table as Record<string, unknown>} />
    </div>
  );
}
