/* MedicalDashboard - 数据分析看板（4Tab切换 + AI驱动标签/环形图）
   ★ 环形图和雷达图现在基于真实数据计算，不再使用硬编码假数据 */
import React, { useState, useMemo } from 'react';
import EChartView, { EChartsOption } from '../EChartView';
import TbHbTable, { type TbHbRow } from '../TbHbTable';
import VisualizationRenderer from '../VisualizationRenderer';
import type { EChartItem, AnalysisPackage } from '../../types/api';

interface RingChartData {
  title: string;
  data: { name: string; value: number }[];
}

interface KPI { title: string; value: string | number; unit?: string; color?: string; change?: number | null; trend?: 'up' | 'down' | 'flat'; }
interface Props {
  kpis: KPI[];
  echarts: EChartItem[];
  /** Tab 分类后的图表（新结构，优先使用） */
  chartTabs?: Record<string, EChartItem[]>;
  title?: string;
  tableData?: Record<string, unknown>[];
  navTabs?: string[];
  ringCharts?: RingChartData[];
  /** 列信息：列名 + dtype */
  columnInfo?: Array<{ name: string; dtype: string }>;
  /** V2：从分析引擎保存的分析包 */
  packages?: AnalysisPackage[];
}

// ---- 共享卡片样式 ----
const cardStyle: React.CSSProperties = {
  background: 'rgba(34,211,238,0.03)',
  border: '1px solid rgba(34,211,238,0.08)',
  borderRadius: '8px',
};

/** 为图表 option 注入 Toolbox 工具栏 */
function withToolbox(option: EChartsOption): EChartsOption {
  return {
    ...option,
    toolbox: {
      show: true,
      right: 8,
      top: 4,
      feature: {
        saveAsImage: { title: '保存图片', backgroundColor: '#0a1628' },
        restore: { title: '还原' },
        dataView: { title: '数据视图', readOnly: true, lang: ['数据视图', '关闭', '刷新'] },
      },
      iconStyle: { borderColor: '#64748b' },
      emphasis: { iconStyle: { borderColor: '#22d3ee' } },
    },
  } as EChartsOption;
}

/** 为趋势类图表注入 dataZoom 缩放条 */
function withDataZoom(option: EChartsOption): EChartsOption {
  return {
    ...option,
    dataZoom: [
      { type: 'slider', start: 0, end: 100, height: 18, bottom: 4,
        borderColor: 'rgba(34,211,238,0.15)', backgroundColor: 'rgba(10,22,40,0.8)',
        fillerColor: 'rgba(34,211,238,0.15)', handleStyle: { color: '#22d3ee' },
        textStyle: { color: '#64748b', fontSize: 9 } },
      { type: 'inside', start: 0, end: 100 },
    ],
  } as EChartsOption;
}

function formatTableValue(val: unknown): string {
  if (val === null || val === undefined) return '-';
  if (typeof val === 'number') {
    if (!Number.isFinite(val)) return '-';
    if (Number.isInteger(val)) return val.toLocaleString();
    return val.toFixed(2);
  }
  return String(val);
}

/** 从真实数据计算环形图数据 — 按分类列分组统计数值列占比 */
function computeRingChartsFromData(
  tableData: Record<string, unknown>[],
  columnInfo: Array<{ name: string; dtype: string }>
): RingChartData[] {
  if (!tableData || tableData.length === 0 || !columnInfo || columnInfo.length === 0) {
    return [];
  }

  const numCols = columnInfo.filter(c => ['float64', 'int64', 'int32', 'float32'].includes(c.dtype)).map(c => c.name);
  const catCols = columnInfo.filter(c => ['object', 'category', 'string'].includes(c.dtype) || !['float64', 'int64', 'int32', 'float32'].includes(c.dtype)).map(c => c.name);

  const result: RingChartData[] = [];

  // 策略1：每个分类列 × 第一个数值列 → 占比环形图
  for (const catCol of catCols.slice(0, 2)) {
    if (numCols.length === 0) continue;
    const numCol = numCols[0];
    // 按分类列分组求和
    const groups: Record<string, number> = {};
    tableData.forEach(row => {
      const key = String(row[catCol] ?? '未知');
      const val = Number(row[numCol]) || 0;
      groups[key] = (groups[key] || 0) + val;
    });
    // 按值排序，取前5 + 其他
    const sorted = Object.entries(groups).sort((a, b) => b[1] - a[1]);
    const top5 = sorted.slice(0, 5);
    const otherVal = sorted.slice(5).reduce((sum, [, v]) => sum + v, 0);
    const data = top5.map(([name, value]) => ({ name, value }));
    if (otherVal > 0) data.push({ name: '其他', value: otherVal });

    if (data.length >= 2) {
      result.push({
        title: `${catCol} ${numCol}占比`,
        data,
      });
    }
  }

  // 策略2：如果有2+数值列，做第二个数值列的占比
  if (numCols.length >= 2 && catCols.length >= 1) {
    const catCol = catCols[0];
    const numCol = numCols[1];
    const groups: Record<string, number> = {};
    tableData.forEach(row => {
      const key = String(row[catCol] ?? '未知');
      const val = Number(row[numCol]) || 0;
      groups[key] = (groups[key] || 0) + val;
    });
    const sorted = Object.entries(groups).sort((a, b) => b[1] - a[1]);
    const top5 = sorted.slice(0, 5);
    const otherVal = sorted.slice(5).reduce((sum, [, v]) => sum + v, 0);
    const data = top5.map(([name, value]) => ({ name, value }));
    if (otherVal > 0) data.push({ name: '其他', value: otherVal });

    if (data.length >= 2) {
      result.push({
        title: `${catCol} ${numCol}占比`,
        data,
      });
    }
  }

  // 策略3：如果只有分类列没有数值列，做频次占比
  if (result.length === 0 && catCols.length >= 1) {
    const catCol = catCols[0];
    const counts: Record<string, number> = {};
    tableData.forEach(row => {
      const key = String(row[catCol] ?? '未知');
      counts[key] = (counts[key] || 0) + 1;
    });
    const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]);
    const top5 = sorted.slice(0, 5);
    const otherVal = sorted.slice(5).reduce((sum, [, v]) => sum + v, 0);
    const data = top5.map(([name, value]) => ({ name, value }));
    if (otherVal > 0) data.push({ name: '其他', value: otherVal });

    if (data.length >= 2) {
      result.push({
        title: `${catCol} 分布占比`,
        data,
      });
    }
  }

  // 兜底：至少保证3个环形图（不足的用空数据占位）
  while (result.length < 3) {
    result.push({ title: '暂无数据', data: [{ name: '无数据', value: 0 }] });
  }

  return result.slice(0, 3);
}

/** 从真实数据计算雷达图数据 — 取前3个分类组，每个组在各数值列的均值 */
function computeRadarFromData(
  tableData: Record<string, unknown>[],
  columnInfo: Array<{ name: string; dtype: string }>,
  index: number
): EChartsOption | null {
  if (!tableData || tableData.length === 0 || !columnInfo || columnInfo.length === 0) {
    return null;
  }

  const numCols = columnInfo.filter(c => ['float64', 'int64', 'int32', 'float32'].includes(c.dtype)).map(c => c.name);
  const catCols = columnInfo.filter(c => ['object', 'category', 'string'].includes(c.dtype) || !['float64', 'int64', 'int32', 'float32'].includes(c.dtype)).map(c => c.name);

  if (numCols.length < 2 || catCols.length === 0) return null;

  // 最多用6个数值列做雷达维度
  const radarCols = numCols.slice(0, 6);

  // 按第一个分类列分组，取前3组
  const catCol = catCols[0];
  const groups: Record<string, Record<string, number[]>> = {};
  tableData.forEach(row => {
    const key = String(row[catCol] ?? '未知');
    if (!groups[key]) groups[key] = {};
    radarCols.forEach(c => {
      const val = Number(row[c]) || 0;
      if (!groups[key][c]) groups[key][c] = [];
      groups[key][c].push(val);
    });
  });

  // 取值最大的3组
  const topGroups = Object.entries(groups)
    .sort((a, b) => {
      const aSum = radarCols.reduce((s, c) => s + (a[1][c]?.reduce((x, y) => x + y, 0) || 0), 0);
      const bSum = radarCols.reduce((s, c) => s + (b[1][c]?.reduce((x, y) => x + y, 0) || 0), 0);
      return bSum - aSum;
    })
    .slice(0, 3);

  if (topGroups.length === 0) return null;

  // 计算每组的均值，并标准化到 0-100（百分比）
  const maxValues: Record<string, number> = {};
  radarCols.forEach(c => {
    const allVals = tableData.map(row => Number(row[c]) || 0);
    maxValues[c] = Math.max(...allVals.filter(v => Number.isFinite(v)), 1);
  });

  const radarData = topGroups.map(([name, cols]) => ({
    value: radarCols.map(c => {
      const mean = cols[c]?.reduce((a, b) => a + b, 0) / (cols[c]?.length || 1);
      return Math.round((mean / maxValues[c]) * 100); // 标准化到0-100
    }),
    name,
  }));

  // 根据index选择雷达数据项
  const selectedItem = radarData[index % radarData.length];
  if (!selectedItem) return null;

  const colors = ['#22d3ee', '#a78bfa', '#f59e0b'];
  const color = colors[index % 3];

  return {
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(10,22,40,0.95)',
      borderColor: 'rgba(34,211,238,0.3)',
      textStyle: { color: '#e2e8f0', fontSize: 11 },
    },
    radar: {
      indicator: radarCols.map(c => ({ name: c, max: 100 })),
      radius: '60%', center: ['50%', '58%'], splitNumber: 4,
      axisName: { color: '#64748b', fontSize: 9, padding: [2, 4] },
      splitLine: { lineStyle: { color: 'rgba(34,211,238,0.1)' } },
      splitArea: { areaStyle: { color: ['rgba(34,211,238,0.01)', 'rgba(34,211,238,0.04)'] } },
      axisLine: { lineStyle: { color: 'rgba(34,211,238,0.15)' } }
    },
    series: [{
      type: 'radar',
      data: [{
        value: selectedItem.value,
        name: selectedItem.name,
        areaStyle: { color: `${color}33` },
        lineStyle: { color, width: 2 },
        itemStyle: { color },
        symbol: 'circle', symbolSize: 4,
      }]
    }]
  } as EChartsOption;
}

function buildRingChartOption(title: string, data: { name: string; value: number }[], colors?: string[]): EChartsOption {
  // 如果没有真实数据，显示空状态
  if (!data || data.length === 0 || data[0].value === 0 && data.length === 1) {
    return {
      title: {
        text: title,
        left: 'center',
        top: '40%',
        textStyle: { color: '#64748b', fontSize: 12, fontWeight: 'normal' }
      },
    } as EChartsOption;
  }
  const mainItem = data.reduce((a, b) => a.value > b.value ? a : b, data[0]);
  return {
    title: {
      text: title,
      left: 'center',
      top: '8%',
      textStyle: { color: '#94a3b8', fontSize: 12, fontWeight: 'normal' }
    },
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(10,22,40,0.95)',
      borderColor: 'rgba(34,211,238,0.3)',
      textStyle: { color: '#e2e8f0', fontSize: 11 },
      formatter: '{b}: {c} ({d}%)',
    },
    legend: {
      bottom: '2%',
      textStyle: { color: '#64748b', fontSize: 10 },
      itemWidth: 8, itemHeight: 8,
    },
    series: [{
      type: 'pie',
      radius: ['50%', '75%'],
      center: ['50%', '58%'],
      avoidLabelOverlap: false,
      itemStyle: { borderRadius: 6, borderColor: '#0a1628', borderWidth: 2 },
      label: { show: false },
      emphasis: { scale: true, scaleSize: 5 },
      data: data.map((d, i) => ({
        ...d,
        itemStyle: { color: colors?.[i] || ['#22d3ee', '#6366f1', '#f59e0b', '#10b981', '#ef4444'][i % 5] }
      }))
    }, {
      type: 'pie',
      radius: ['0%', '0%'],
      center: ['50%', '58%'],
      silent: true,
      label: {
        show: true,
        position: 'center',
        formatter: `{a|${mainItem.value.toLocaleString()}}\n{b|${mainItem.name}}`,
        rich: {
          a: { fontSize: 22, fontWeight: 'bold', color: '#22d3ee', lineHeight: 30, textShadow: '0 0 10px rgba(34,211,238,0.5)' },
          b: { fontSize: 12, color: '#94a3b8', lineHeight: 18 }
        }
      },
      data: [{ value: 0, name: '' }]
    }]
  } as EChartsOption;
}

// ============================== 主组件 ==============================
export default function MedicalDashboard({ kpis, echarts, chartTabs, title = '数据分析看板', tableData, navTabs, ringCharts, columnInfo, packages }: Props) {
  const columns = tableData && tableData.length > 0 ? Object.keys(tableData[0]) : [];
  const [activeTab, setActiveTab] = useState(0);
  const [highlightLabel, setHighlightLabel] = useState<string | null>(null);
  // 明细查询专用
  const [searchText, setSearchText] = useState('');
  const [sortCol, setSortCol] = useState<string | null>(null);
  const [sortAsc, setSortAsc] = useState(true);
  const [filterCol, setFilterCol] = useState<string | null>(null);
  const [filterVal, setFilterVal] = useState('');

  const tabs = (navTabs && navTabs.length >= 4)
    ? navTabs.slice(0, 4)
    : ['数据总览', '趋势洞察', '分类分析', '明细查询'];

  // ★ 从已保存图表中提取同环比表格数据
  const tbHbCharts = useMemo(() => {
    return echarts
      .filter((c) => c.chart_type === 'table' && c.table_data)
      .map((c) => {
        const td = c.table_data!;
        return {
          title: String(c.title || '同环比分析'),
          rows: (td.rows || []) as TbHbRow[],
          value_column: String(td.value_column || ''),
          current_year: String(td.current_year || ''),
          previous_year: td.previous_year ? String(td.previous_year) : null,
          has_yoy: Boolean(td.has_yoy),
        };
      });
  }, [echarts]);

  // ★ 从真实数据计算环形图 — 如果 AI 返回了就用 AI 的，否则从数据计算
  const computedRingCharts = useMemo(() => {
    // 优先用 AI 返回的 ringCharts（数据来自 AI 分析）
    if (ringCharts && ringCharts.length >= 3 && ringCharts.some(r => r.data.some(d => d.value > 0 && d.name !== '类型A' && d.name !== '主要'))) {
      return ringCharts.slice(0, 3);
    }
    // 否则从真实数据计算
    if (tableData && columnInfo && tableData.length > 0) {
      const computed = computeRingChartsFromData(tableData, columnInfo);
      if (computed.length > 0 && computed.some(r => r.data.some(d => d.value > 0))) {
        return computed;
      }
    }
    // 兜底：仍然返回3个占位，但标题改为"暂无数据"
    return [
      { title: '暂无数据', data: [{ name: '暂无', value: 1 }] },
      { title: '暂无数据', data: [{ name: '暂无', value: 1 }] },
      { title: '暂无数据', data: [{ name: '暂无', value: 1 }] },
    ];
  }, [ringCharts, tableData, columnInfo]);

  // ★ 从真实数据计算雷达图
  const radarOptions = useMemo(() => {
    if (tableData && columnInfo && tableData.length > 0) {
      const opts: (EChartsOption | null)[] = [];
      for (let i = 0; i < 3; i++) {
        opts.push(computeRadarFromData(tableData, columnInfo, i));
      }
      return opts;
    }
    return [null, null, null];
  }, [tableData, columnInfo]);

  // ★ 从真实数据计算排行 — 按数值列排序，不是简单计数
  const topNData = useMemo(() => {
    if (!tableData || !columnInfo || tableData.length === 0) return [];

    const numCols = columnInfo.filter(c => ['float64', 'int64', 'int32', 'float32'].includes(c.dtype)).map(c => c.name);
    const catCols = columnInfo.filter(c => ['object', 'category', 'string'].includes(c.dtype) || !['float64', 'int64', 'int32', 'float32'].includes(c.dtype)).map(c => c.name);

    if (catCols.length === 0 || numCols.length === 0) return [];

    const catCol = catCols[0]; // 排名的分组列
    const numCol = numCols[0]; // 排名的数值列

    // 按分类列分组，求数值列的总和
    const groups: Record<string, number> = {};
    tableData.forEach(row => {
      const key = String(row[catCol] ?? '未知');
      const val = Number(row[numCol]) || 0;
      groups[key] = (groups[key] || 0) + val;
    });

    return Object.entries(groups)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8)
      .map(([name, value]) => ({ name, value, numCol }));
  }, [tableData, columnInfo]);

  // 按图表类型过滤
  const trendCharts = echarts.filter((c) => {
    const s = getSeries(c); const t = String(s?.type || '');
    return t.includes('line') || t.includes('area');
  });
  const categoryCharts = echarts.filter((c) => {
    const s = getSeries(c); const t = String(s?.type || '');
    return t.includes('bar') || t.includes('pie') || t.includes('radar');
  });

  // 明细排序/过滤
  const filteredRows = (() => {
    let rows = tableData || [];
    if (searchText.trim()) {
      const kw = searchText.trim().toLowerCase();
      rows = rows.filter((row) => Object.values(row).some((v) => String(v ?? '').toLowerCase().includes(kw)));
    }
    if (filterCol && filterVal.trim()) {
      const fv = filterVal.trim().toLowerCase();
      rows = rows.filter((row) => String(row[filterCol] ?? '').toLowerCase().includes(fv));
    }
    if (sortCol) {
      rows = [...rows].sort((a, b) => {
        const va = a[sortCol], vb = b[sortCol];
        if (typeof va === 'number' && typeof vb === 'number') return sortAsc ? va - vb : vb - va;
        return sortAsc ? String(va ?? '').localeCompare(String(vb ?? '')) : String(vb ?? '').localeCompare(String(va ?? ''));
      });
    }
    return rows;
  })();

  return (
    <div className="w-full h-full flex flex-col overflow-hidden" style={{
      background: 'linear-gradient(180deg, #0a0f1a 0%, #0d1525 50%, #0a1628 100%)',
      fontFamily: "'PingFang SC', 'Microsoft YaHei', system-ui, sans-serif",
    }}>
      {/* ★ 顶部导航栏 */}
      <div className="relative flex items-center justify-center px-6 py-3" style={{
        background: 'linear-gradient(90deg, transparent 0%, rgba(34,211,238,0.05) 20%, rgba(34,211,238,0.05) 80%, transparent 100%)',
        borderBottom: '1px solid rgba(34,211,238,0.15)',
      }}>
        <div className="absolute left-4 top-1/2 -translate-y-1/2 flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-[#22d3ee] animate-pulse" />
          <span className="text-xs text-slate-500">{new Date().toLocaleString('zh-CN')}</span>
        </div>
        <div className="flex flex-col items-center">
          <h1 className="text-xl font-bold text-white tracking-widest mb-2"
            style={{ textShadow: '0 0 20px rgba(34,211,238,0.5)' }}>{title}</h1>
          <div className="flex items-center gap-1">
            {tabs.map((tab, i) => (
              <button key={tab} onClick={() => setActiveTab(i)}
                className={`px-4 py-1 text-xs transition-all duration-300 ${
                  activeTab === i ? 'text-[#22d3ee] bg-[#22d3ee]/10 border-t border-[#22d3ee]/50' : 'text-slate-500 hover:text-slate-300'
                }`}
                style={{ clipPath: activeTab === i ? 'polygon(10% 0%, 90% 0%, 100% 100%, 0% 100%)' : 'none' }}>
                {tab}
              </button>
            ))}
          </div>
        </div>
        <div className="absolute right-4 top-1/2 -translate-y-1/2 flex items-center gap-3">
          <span className="flex items-center gap-2 text-xs text-[#22d3ee]">
            <span className="w-1.5 h-1.5 rounded-full bg-[#22d3ee] animate-pulse" />系统正常</span>
        </div>
      </div>

      {/* ★ KPI 条（所有Tab共用） */}
      {kpis.length > 0 && (
        <div className="px-6 py-4 flex justify-center">
          <div className="flex justify-center gap-3 flex-wrap" style={{ maxWidth: '1100px' }}>
            {kpis.slice(0, 6).map((kpi, i) => {
              const numVal = typeof kpi.value === 'number' ? kpi.value : parseFloat(String(kpi.value));
              const isNum = !isNaN(numVal);
              const digits = isNum ? String(Math.floor(numVal)).split('') : [];
              return (
                <div key={i} className="flex flex-col items-center py-3 px-6" style={{
                  minWidth: '150px',
                  background: 'linear-gradient(180deg, rgba(34,211,238,0.08) 0%, rgba(34,211,238,0.02) 100%)',
                  border: '1px solid rgba(34,211,238,0.15)', borderRadius: '4px',
                }}>
                  <span className="text-[10px] text-slate-400 mb-2">{kpi.title}</span>
                  <div className="flex items-center gap-0.5">
                    {isNum ? digits.map((d, idx) => (
                      <div key={idx} className="w-6 h-8 flex items-center justify-center text-lg font-bold font-mono" style={{
                        background: 'linear-gradient(180deg, rgba(34,211,238,0.2) 0%, rgba(34,211,238,0.05) 100%)',
                        border: '1px solid rgba(34,211,238,0.3)', color: '#22d3ee',
                        textShadow: '0 0 10px rgba(34,211,238,0.5)',
                      }}>{d}</div>
                    )) : <span className="text-lg font-bold text-[#22d3ee]">{kpi.value}</span>}
                  </div>
                  {/* 涨跌箭头 */}
                  {kpi.trend && kpi.trend !== 'flat' && kpi.change != null && kpi.change !== 0 && (
                    <div className="flex items-center gap-0.5 mt-1">
                      <span className="text-[10px] font-semibold" style={{ color: kpi.trend === 'up' ? '#4ade80' : '#f87171' }}>
                        {kpi.trend === 'up' ? '↑' : '↓'} {Math.abs(kpi.change) >= 100 ? Math.abs(kpi.change).toFixed(0) : Math.abs(kpi.change).toFixed(1)}%
                      </span>
                    </div>
                  )}
                  {kpi.unit && <span className="text-[9px] text-slate-500 mt-1">{kpi.unit}</span>}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ★ 联动高亮提示条 */}
      {highlightLabel && (
        <div className="flex items-center justify-center gap-3 px-4 py-1.5 mx-6 rounded-lg"
          style={{ background: 'rgba(34,211,238,0.1)', border: '1px solid rgba(34,211,238,0.15)' }}>
          <span className="text-xs text-[#22d3ee]">🔗 联动高亮：<strong className="text-white">{highlightLabel}</strong> — 点击图表数据点可切换或清除</span>
          <button onClick={() => setHighlightLabel(null)}
            className="px-2 py-0.5 text-xs rounded bg-[#22d3ee]/30 text-[#22d3ee] hover:bg-[#22d3ee]/50 transition-colors border border-[#22d3ee]/30">
            ✕ 清除
          </button>
        </div>
      )}

      {/* ★ Tab 内容区 */}
      <div className="flex-1 px-6 pb-4 overflow-hidden" onClick={(e) => { if (e.target === e.currentTarget) setHighlightLabel(null); }}>
        {activeTab === 0 && <TabOverview echarts={chartTabs?.['数据总览'] || echarts} ringCharts={computedRingCharts} radarOptions={radarOptions} tableData={tableData} columns={columns}
          highlightLabel={highlightLabel} onHighlight={setHighlightLabel} tbHbCharts={tbHbCharts} />}
        {activeTab === 1 && <TabTrend trendCharts={chartTabs?.['趋势洞察'] || trendCharts} allEcharts={echarts}
          highlightLabel={highlightLabel} onHighlight={setHighlightLabel} />}
        {activeTab === 2 && <TabCategory categoryCharts={chartTabs?.['分类分析'] || categoryCharts} allEcharts={echarts} ringCharts={computedRingCharts} tableData={tableData} columns={columns}
          topNData={topNData} highlightLabel={highlightLabel} onHighlight={setHighlightLabel} />}
        {activeTab === 3 && <TabDetail tableData={tableData} columns={columns} searchText={searchText} setSearchText={setSearchText}
          sortCol={sortCol} setSortCol={setSortCol} sortAsc={sortAsc} setSortAsc={setSortAsc}
          filterCol={filterCol} setFilterCol={setFilterCol} filterVal={filterVal} setFilterVal={setFilterVal}
          filteredRows={filteredRows} />}
      </div>

      {/* ★ V2：AI 分析结果（来自 saved_packages） */}
      {packages && packages.length > 0 && (
        <div className="px-6 pb-4" style={{ borderTop: '1px solid rgba(139,92,246,0.15)' }}>
          <style>{`
            .v2-details { margin-bottom: 8px; }
            .v2-details > summary {
              cursor: pointer; padding: 8px 12px; border-radius: 6px;
              background: rgba(139,92,246,0.06); border: 1px solid rgba(139,92,246,0.1);
              font-size: 12px; color: #cbd5e1; font-weight: 500;
              transition: background 0.2s, border-color 0.2s;
              user-select: none;
            }
            .v2-details > summary:hover { background: rgba(139,92,246,0.12); border-color: rgba(139,92,246,0.25); }
            .v2-details[open] > summary { border-color: rgba(139,92,246,0.3); background: rgba(139,92,246,0.1); margin-bottom: 4px; }
            .v2-details > .v2-content { padding: 8px 12px; animation: slideDown 0.2s ease; }
            @keyframes slideDown { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: translateY(0); } }
          `}</style>
          <div className="flex items-center gap-3 pt-3 mb-3">
            <div className="w-1.5 h-5 bg-gradient-to-b from-[#a78bfa] to-[#22d3ee] rounded-full" />
            <h3 className="text-sm font-semibold text-[#a78bfa]">🤖 AI 分析结果（{packages.length} 项）</h3>
          </div>
          {packages.filter(p => p.can_run).slice(0, 5).map((pkg, i) => (
            <details key={pkg.id || i} className="v2-details">
              <summary>
                {pkg.business_question}
                <span style={{ marginLeft: 8, fontSize: 10, color: '#a78bfa', background: 'rgba(139,92,246,0.1)', padding: '1px 6px', borderRadius: 3 }}>
                  {pkg.analysis_type}
                </span>
              </summary>
              <div className="v2-content">
                <VisualizationRenderer packages={[pkg]} />
              </div>
            </details>
          ))}
          {packages.filter(p => p.can_run).length > 5 && (
            <details>
              <summary style={{
                cursor: 'pointer', padding: '6px 12px', borderRadius: 6,
                background: 'rgba(139,92,246,0.03)', border: '1px solid rgba(139,92,246,0.06)',
                fontSize: 11, color: '#64748b', textAlign: 'center',
              }}>
                查看更多（共 {packages.filter(p => p.can_run).length} 项，已显示 5 项）
              </summary>
              <div className="v2-content">
                {packages.filter(p => p.can_run).slice(5).map((pkg, i) => (
                  <details key={pkg.id || i} className="v2-details">
                    <summary>{pkg.business_question}</summary>
                    <div className="v2-content">
                      <VisualizationRenderer packages={[pkg]} />
                    </div>
                  </details>
                ))}
              </div>
            </details>
          )}
          {packages.some(p => !p.can_run) && (
            <div style={{ marginTop: 8, padding: '8px 12px', borderRadius: 6, background: 'rgba(245,158,11,0.06)', border: '1px solid rgba(245,158,11,0.12)' }}>
              <span style={{ fontSize: 10, color: '#f59e0b' }}>
                ⚠️ {packages.filter(p => !p.can_run).length} 项分析因数据不支持未能执行
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ====================== Helper ======================
function getSeries(c: EChartItem) {
  const series = (c.option as Record<string, unknown>)?.series;
  return (Array.isArray(series) ? series[0] : series) as Record<string, unknown> | undefined;
}

// ====================== Tab 0 - 数据总览 ======================
function TabOverview({ echarts, ringCharts, radarOptions, tableData, columns, highlightLabel, onHighlight, tbHbCharts }: {
  echarts: EChartItem[];
  ringCharts: { title: string; data: { name: string; value: number }[] }[];
  radarOptions: (EChartsOption | null)[];
  tableData?: Record<string, unknown>[];
  columns: string[];
  highlightLabel: string | null;
  onHighlight: (v: string | null) => void;
  tbHbCharts: { title: string; rows: TbHbRow[]; value_column: string; current_year: string; previous_year: string | null; has_yoy: boolean }[];
}) {
  const gid = 'medical-overview';
  // 雷达图标题：取前三组分类名
  const radarTitles = useMemo(() => {
    if (!radarOptions || radarOptions.length === 0) return ['雷达图1', '雷达图2', '雷达图3'];
    // 从 radarOptions 的 series data 中提取 name
    return radarOptions.map((opt, i) => {
      if (!opt) return '';
      const series = (opt as Record<string, unknown>)?.series as unknown[];
      const dataItem = series?.[0] as Record<string, unknown>;
      const seriesData = dataItem?.data as unknown[];
      const firstData = seriesData?.[0] as Record<string, unknown>;
      return String(firstData?.name || `雷达图${i + 1}`);
    });
  }, [radarOptions]);

  // 维度列名（从 radarOptions 的 indicator 中提取）
  const hasRadar = radarOptions.some(o => o !== null);

  return (
    <div className="h-full flex flex-col gap-4">
      <div className="flex gap-4 flex-1">
      <div className="flex-1 flex flex-col gap-4" style={{ maxWidth: '60%' }}>
        <div className="flex gap-4" style={{ height: '45%' }}>
          <div className="flex-1 p-3" style={cardStyle}>
            <div className="text-xs text-[#22d3ee] mb-2">📈 趋势总览</div>
            {echarts[0] ? (
              <EChartView option={withDataZoom(withToolbox(echarts[0].option))} title={echarts[0].title} height={220} hideTitle
                groupId={gid} highlightLabel={highlightLabel} onHighlight={onHighlight} />
            ) : <div className="h-[220px] flex items-center justify-center text-slate-500 text-xs">暂无数据</div>}
          </div>
          <div className="w-64 p-3" style={cardStyle}>
            <div className="text-xs text-[#22d3ee] mb-2">🥧 {ringCharts[0]?.title || '占比分析'}</div>
            <div className="h-[220px]">
              <EChartView option={withToolbox(buildRingChartOption(ringCharts[0]?.title || '', ringCharts[0]?.data || []))} height={220} hideTitle
                groupId={gid} highlightLabel={highlightLabel} onHighlight={onHighlight} />
            </div>
          </div>
        </div>
        <div className="flex-1 p-3" style={cardStyle}>
          <div className="text-xs text-[#22d3ee] mb-2">📊 多维对比{hasRadar ? '（按数值列标准化对比）' : ''}</div>
          <div className="flex gap-4 h-[calc(100%-24px)]">
            {radarOptions.map((opt, i) => (
              <div key={i} className="flex-1">
                {opt ? (
                  <EChartView option={withToolbox(opt)} height={180} hideTitle
                    groupId={gid} highlightLabel={highlightLabel} onHighlight={onHighlight} />
                ) : (
                  <div className="h-[180px] flex items-center justify-center text-slate-500 text-xs">
                    暂无多维数据
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className="w-[38%] flex flex-col gap-4">
        <div className="flex-1 p-3 overflow-hidden" style={cardStyle}>
          <div className="text-xs text-[#22d3ee] mb-3 flex items-center justify-between">
            <span>📋 数据预览</span>
            <span className="text-[10px] text-slate-500">共 {tableData?.length || 0} 条</span>
          </div>
          <div className="overflow-auto" style={{ height: 'calc(100% - 28px)' }}>
            {tableData && tableData.length > 0 ? (
              <table className="w-full text-[11px]">
                <thead className="sticky top-0 z-10">
                  <tr style={{ background: 'rgba(34,211,238,0.1)' }}>
                    {columns.slice(0, 4).map((col) => <th key={col} className="px-2 py-2 text-left text-slate-400 font-medium">{col}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {tableData.slice(0, 10).map((row, i) => (
                    <tr key={i} className="border-t border-white/[0.03] hover:bg-[#22d3ee]/[0.05]">
                      {columns.slice(0, 4).map((col) => <td key={col} className="px-2 py-2 text-slate-300">{formatTableValue(row[col])}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : <div className="flex items-center justify-center h-full text-slate-500 text-xs">暂无数据</div>}
          </div>
        </div>
        <div className="flex gap-3" style={{ height: '180px' }}>
          {ringCharts.slice(1).map((chart, i) => (
            <div key={i} className="flex-1 p-2" style={cardStyle}>
              <EChartView option={withToolbox(buildRingChartOption(chart.title, chart.data))} height={160} hideTitle
                groupId={gid} highlightLabel={highlightLabel} onHighlight={onHighlight} />
            </div>
          ))}
        </div>
      </div>
      </div>
      {/* 同环比表格（仅数据总览显示，独占底部整行） */}
      {tbHbCharts.length > 0 && (
        <div className="w-full">
          {tbHbCharts.map((tb, idx) => (
            <div key={idx} className="rounded-xl p-4 mb-3" style={{ background: 'rgba(10,14,30,0.95)', border: '1px solid rgba(34,211,238,0.15)' }}>
              <TbHbTable data={tb.rows} valueColumn={tb.value_column} currentYear={tb.current_year} previousYear={tb.previous_year} hasYoY={tb.has_yoy} maxHeight="380px" />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ====================== Tab 1 - 趋势洞察 ======================
function TabTrend({ trendCharts, allEcharts, highlightLabel, onHighlight }: {
  trendCharts: EChartItem[]; allEcharts: EChartItem[];
  highlightLabel: string | null; onHighlight: (v: string | null) => void;
}) {
  const display = trendCharts.length > 0 ? trendCharts : allEcharts.filter((_, i) => i < 3);
  const hasData = display.length > 0;
  const gid = 'medical-trend';
  return (
    <div className="h-full flex flex-col">
      <div className="text-xs text-slate-500 mb-3 flex items-center justify-between">
        <span>📈 {hasData ? `${display.length} 张趋势图表` : '暂无趋势数据'} — 自动筛选折线图/面积图，点击数据点联动高亮</span>
      </div>
      {hasData ? (
        <div className="flex-1 grid grid-cols-2 gap-4 overflow-auto">
          {display.map((chart, i) => (
            <div key={i} className={`p-3 ${display.length === 1 ? 'col-span-2' : ''}`} style={cardStyle}>
              <EChartView option={withDataZoom(withToolbox(chart.option))} title={chart.title}
                height={display.length === 1 ? 380 : 250}
                groupId={gid} highlightLabel={highlightLabel} onHighlight={onHighlight} />
            </div>
          ))}
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center text-slate-500 text-sm">
          <div className="text-center">
            <div className="text-3xl mb-3">📈</div>
            <p>数据中没有检测到趋势类图表</p>
            <p className="text-xs mt-2">请回到「数据总览」或切换到其他标签查看</p>
          </div>
        </div>
      )}
    </div>
  );
}

// ====================== Tab 2 - 分类分析 ======================
function TabCategory({ categoryCharts, allEcharts, ringCharts, tableData, columns, topNData, highlightLabel, onHighlight }: {
  categoryCharts: EChartItem[];
  allEcharts: EChartItem[];
  ringCharts: { title: string; data: { name: string; value: number }[] }[];
  tableData?: Record<string, unknown>[];
  columns: string[];
  topNData: Array<{ name: string; value: number; numCol: string }>;
  highlightLabel: string | null;
  onHighlight: (v: string | null) => void;
}) {
  const display = categoryCharts.length > 0 ? categoryCharts : allEcharts.filter((_, i) => i < 4);
  const gid = 'medical-category';
  // 排行标题：显示真实的分类列和数值列名
  const rankTitle = topNData.length > 0 ? `${topNData[0].numCol} 排行 TOP8` : '分类排行 TOP8';
  return (
    <div className="h-full flex gap-4">
      <div className="flex-1 flex flex-col gap-4 overflow-auto">
        <div className={`grid ${display.length > 2 ? 'grid-cols-2' : 'grid-cols-1'} gap-4`}>
          {display.map((chart, i) => (
            <div key={i} className={`p-3 ${display.length === 1 ? 'h-64' : ''}`} style={cardStyle}>
              <EChartView option={withToolbox(chart.option)} title={chart.title} height={display.length === 1 ? 360 : 220}
                groupId={gid} highlightLabel={highlightLabel} onHighlight={onHighlight} />
            </div>
          ))}
        </div>
        <div className="flex gap-4" style={{ height: '200px' }}>
          {ringCharts.slice(0, 2).map((chart, i) => (
            <div key={i} className="flex-1 p-2" style={cardStyle}>
              <EChartView option={withToolbox(buildRingChartOption(chart.title, chart.data))} height={180} hideTitle
                groupId={gid} highlightLabel={highlightLabel} onHighlight={onHighlight} />
            </div>
          ))}
        </div>
      </div>
      <div className="w-[35%] flex flex-col gap-4">
        <div className="flex-1 p-3 overflow-hidden" style={cardStyle}>
          <div className="text-xs text-[#22d3ee] mb-3">🏆 {rankTitle}</div>
          <div className="overflow-auto" style={{ height: 'calc(100% - 28px)' }}>
            {topNData.length > 0 ? (
              <div className="flex flex-col gap-0.5">
                {topNData.map((item, i) => {
                  const badge = i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : i + 1;
                  const bg = i < 3 ? 'rgba(34,211,238,0.08)' : 'transparent';
                  return (
                    <div key={i} className="flex items-center justify-between px-2 py-1.5" style={{ background: bg, borderBottom: '1px solid rgba(34,211,238,0.04)' }}>
                      <div className="flex items-center gap-2">
                        <span className={`text-xs font-bold w-5 text-center ${i < 3 ? 'text-slate-200' : 'text-slate-500'}`}>{badge}</span>
                        <span className="text-xs text-slate-300 truncate" style={{ maxWidth: '120px' }}>{item.name}</span>
                      </div>
                      <span className="text-xs text-[#22d3ee] font-mono">{item.value.toLocaleString()}</span>
                    </div>
                  );
                })}
              </div>
            ) : <div className="flex items-center justify-center h-full text-slate-500 text-xs">暂无排行数据</div>}
          </div>
        </div>
        <div className="h-48 p-3" style={cardStyle}>
          <EChartView option={withToolbox(buildRingChartOption(ringCharts[2]?.title || '', ringCharts[2]?.data || []))} height={170} hideTitle
            groupId={gid} highlightLabel={highlightLabel} onHighlight={onHighlight} />
        </div>
      </div>
    </div>
  );
}

// ====================== Tab 3 - 明细查询 ======================
function TabDetail({ tableData, columns, searchText, setSearchText, sortCol, setSortCol, sortAsc, setSortAsc, filterCol, setFilterCol, filterVal, setFilterVal, filteredRows }: {
  tableData?: Record<string, unknown>[];
  columns: string[];
  searchText: string; setSearchText: (v: string) => void;
  sortCol: string | null; setSortCol: (v: string | null) => void;
  sortAsc: boolean; setSortAsc: (v: boolean) => void;
  filterCol: string | null; setFilterCol: (v: string | null) => void;
  filterVal: string; setFilterVal: (v: string) => void;
  filteredRows: Record<string, unknown>[];
}) {
  const allCols = columns.length > 0 ? columns : ['(空)'];
  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center gap-3 mb-3 flex-wrap">
        <input value={searchText} onChange={(e) => setSearchText(e.target.value)}
          placeholder="🔍 搜索全部列..."
          className="px-3 py-1.5 text-xs rounded-lg bg-white/[0.04] border border-white/[0.08] text-slate-300 placeholder-slate-600 w-48" />
        <select value={filterCol || ''} onChange={(e) => { setFilterCol(e.target.value || null); setFilterVal(''); }}
          className="px-2 py-1.5 text-xs rounded-lg bg-white/[0.04] border border-white/[0.08] text-slate-400">
          <option value="">📌 按列过滤</option>
          {allCols.map((col) => <option key={col} value={col}>{col}</option>)}
        </select>
        {filterCol && (
          <input value={filterVal} onChange={(e) => setFilterVal(e.target.value)}
            placeholder={`过滤 ${filterCol}...`}
            className="px-3 py-1.5 text-xs rounded-lg bg-white/[0.04] border border-white/[0.08] text-slate-300 placeholder-slate-600 w-36" />
        )}
        <div className="flex-1" />
        <span className="text-[10px] text-slate-500">
          {filteredRows.length} / {tableData?.length || 0} 条
          {searchText || filterVal ? ' (已过滤)' : ''}
        </span>
      </div>
      <div className="flex-1 overflow-auto p-2" style={cardStyle}>
        {tableData && tableData.length > 0 ? (
          <table className="w-full text-[11px]">
            <thead className="sticky top-0 z-10">
              <tr style={{ background: 'rgba(34,211,238,0.12)' }}>
                <th className="px-2 py-2 text-left text-slate-400 font-medium w-8">#</th>
                {allCols.map((col) => (
                  <th key={col} className="px-2 py-2 text-left text-slate-400 font-medium cursor-pointer hover:text-[#22d3ee] select-none"
                    onClick={() => { if (sortCol === col) setSortAsc(!sortAsc); else { setSortCol(col); setSortAsc(true); } }}>
                    <span className="flex items-center gap-1">
                      {col}
                      {sortCol === col && <span className="text-[#22d3ee] text-[9px]">{sortAsc ? '▲' : '▼'}</span>}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filteredRows.length > 0 ? (
                filteredRows.map((row, i) => (
                  <tr key={i} className="border-t border-white/[0.03] hover:bg-[#22d3ee]/[0.05]">
                    <td className="px-2 py-1.5 text-slate-600">{i + 1}</td>
                    {allCols.map((col) => (
                      <td key={col} className="px-2 py-1.5 text-slate-300 whitespace-nowrap">{formatTableValue(row[col])}</td>
                    ))}
                  </tr>
                ))
              ) : (
                <tr><td colSpan={allCols.length + 1} className="text-center py-8 text-slate-500 text-xs">没有匹配的结果</td></tr>
              )}
            </tbody>
          </table>
        ) : (
          <div className="flex items-center justify-center h-full text-slate-500 text-sm">
            <div className="text-center">
              <div className="text-3xl mb-3">📋</div>
              <p>暂无数据</p>
              <p className="text-xs mt-2">请先在「数据上传」页面上传数据文件</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
