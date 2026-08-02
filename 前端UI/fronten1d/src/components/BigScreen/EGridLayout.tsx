/* EGridLayout - ECharts 网格大屏（DataV 发光边框 + AnimatedNumber + 图表 + 表格） */
import React, { useState, useMemo } from 'react';
import { BorderBox1 } from '@jiaminghi/data-view-react';
import EChartView, { EChartsOption } from '../EChartView';
import GLMapView from '../GLMapView';
import AnimatedNumber from '../AnimatedNumber';
import TbHbTable, { type TbHbRow } from '../TbHbTable';
import VisualizationRenderer from '../VisualizationRenderer';
import type { EChartItem, AnalysisPackage } from '../../types/api';

interface KPI { title: string; value: string | number; icon?: string; color?: string; change?: number | null; trend?: 'up' | 'down' | 'flat'; }
interface Props {
  kpis: KPI[];
  echarts: EChartItem[];
  title?: string;
  hideChartTitle?: boolean;
  tableData?: Record<string, unknown>[];
  /** V2：从分析引擎保存的分析包 */
  packages?: AnalysisPackage[];
}

/** 检测 ECharts option 是否为 3D GL 类型 */
function isGLOption(option: EChartsOption | null): boolean {
  if (!option) return false;
  if ((option as Record<string, unknown>).geo3D) return true;
  const series = ((option as Record<string, unknown>).series as Array<Record<string, unknown>>) || [];
  const glTypes = ['scatter3D', 'bar3D', 'line3D', 'lines3D', 'surface', 'map3D'];
  return series.some((s) => glTypes.includes(String(s.type || '')));
}

function formatTableValue(val: unknown): string {
  if (val === null || val === undefined) return '-';
  if (typeof val === 'number') {
    if (!Number.isFinite(val)) return '-';
    if (Number.isInteger(val)) return val.toLocaleString();
    return val.toFixed(4);
  }
  return String(val);
}

export default function EGridLayout({ kpis, echarts, title = '数据分析看板', hideChartTitle, tableData, packages }: Props) {
  const [highlightLabel, setHighlightLabel] = useState<string | null>(null);
  const [showTable, setShowTable] = useState(false);

  const columns = tableData && tableData.length > 0 ? Object.keys(tableData[0]) : [];
  const displayRows = showTable && tableData ? tableData : [];

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

  return (
    <div className="big-screen w-full h-full flex flex-col overflow-auto"
      style={{ background: 'transparent' }}
      onClick={(e) => { if (e.target === e.currentTarget) setHighlightLabel(null); }}
    >
      {/* ★ 顶部标题栏 - 带 DataV Decoration 装饰 */}
      <div className="relative flex items-center justify-between px-8 py-5 border-b border-white/40">
        {/* 顶部装饰线 */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2" style={{ width: '60%' }}>
          <div className="w-full h-0.5 bg-gradient-to-r from-transparent via-[#7DD3FC]/40 to-transparent" />
        </div>
        <div className="flex items-center gap-4 pt-2">
          <div className="w-2 h-8 bg-gradient-to-b from-[#7DD3FC] to-[#38BDF8] rounded-full" />
            <h1 className="text-2xl font-bold text-[#0f172a] tracking-wider"
              style={{}}>
              {title}
          </h1>
        </div>
        <div className="flex items-center gap-6 text-sm text-slate-400 pt-2">
          {tableData && tableData.length > 0 && (
            <button onClick={() => setShowTable(!showTable)}
              className={`px-3 py-1.5 text-xs rounded-lg transition-colors ${
                showTable
                  ? 'bg-[#7DD3FC]/10 text-[#7DD3FC] border border-[#7DD3FC]/20'
                  : 'bg-transparent text-slate-500 hover:text-slate-600 border border-white/30'
              }`}>
              📋 数据表格 {showTable ? '▲' : '▼'}
            </button>
          )}
          <span className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse shadow-[0_0_8px_rgba(74,222,128,0.6)]" />
            实时数据
          </span>
          <span className="font-mono text-xs">{new Date().toLocaleString('zh-CN')}</span>
          <span className="px-2 py-0.5 text-xs rounded bg-cyan-500/20 text-cyan-400 border border-cyan-500/30">
            ECharts
          </span>
        </div>
      </div>

      {/* ★ 联动高亮状态提示 */}
      {highlightLabel && (
        <div className="flex items-center justify-center gap-3 px-4 py-2"
          style={{ background: 'rgba(255,255,255,0.35)', borderBottom: '1px solid rgba(255,255,255,0.50)', backdropFilter: 'blur(10px)', WebkitBackdropFilter: 'blur(10px)' }}>
          <span className="text-xs text-[#7DD3FC]">
            🔗 联动高亮：<strong className="text-[#0f172a]">{highlightLabel}</strong>
          </span>
          <button onClick={() => setHighlightLabel(null)}
            className="px-2 py-0.5 text-xs rounded bg-[#7DD3FC]/30 text-[#7DD3FC] hover:bg-[#7DD3FC]/50 transition-colors border border-[#7DD3FC]/30">
            ✕ 清除
          </button>
        </div>
      )}

      {/* ★ KPI 指标卡 - DataV 装饰 + AnimatedNumber */}
      {kpis.length > 0 && (
        <div className="relative px-6 py-4 border-b border-white/30">
          <div className="grid grid-cols-5 gap-4">
            {kpis.slice(0, 5).map((kpi, i) => {
              const color = kpi.color || '#7DD3FC';
              const numVal = typeof kpi.value === 'number' ? kpi.value : parseFloat(String(kpi.value));
              const isNum = !isNaN(numVal);
              return (
                <div key={i} className="relative p-4 rounded-lg"
                  style={{
                    background: 'rgba(255,255,255,0.35)',
                    border: '1px solid rgba(255,255,255,0.45)',
                    backdropFilter: 'blur(10px)',
                    WebkitBackdropFilter: 'blur(10px)',
                  }}>
                  {/* 角落装饰 */}
                  <div className="absolute top-0 left-0 w-3 h-3 border-t border-l" style={{ borderColor: color }} />
                  <div className="absolute top-0 right-0 w-3 h-3 border-t border-r" style={{ borderColor: color }} />
                  <div className="absolute bottom-0 left-0 w-3 h-3 border-b border-l" style={{ borderColor: color }} />
                  <div className="absolute bottom-0 right-0 w-3 h-3 border-b border-r" style={{ borderColor: color }} />

                  <div className="flex items-center gap-3">
                    <div className="text-2xl">{kpi.icon || '📊'}</div>
                    <div className="flex-1 min-w-0">
                      <p className="text-[10px] text-slate-500 uppercase tracking-wider">{kpi.title}</p>
                      <p className="text-xl font-bold font-mono" style={{ color, textShadow: `0 0 15px ${color}40` }}>
                        {isNum ? <AnimatedNumber value={numVal} duration={1.2} decimals={numVal % 1 !== 0 ? 2 : 0} /> : String(kpi.value)}
                      </p>
                      {kpi.trend && kpi.trend !== 'flat' && kpi.change != null && kpi.change !== 0 && (
                        <p className="text-[10px] font-semibold mt-0.5" style={{ color: kpi.trend === 'up' ? '#34D399' : '#FB7185' }}>
                          {kpi.trend === 'up' ? '↑' : '↓'} {Math.abs(kpi.change) >= 100 ? Math.abs(kpi.change).toFixed(0) : Math.abs(kpi.change).toFixed(1)}%
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ★ V2 分析包区域 */}
      {packages && packages.length > 0 && (
        <div className="px-6 py-4 border-b border-white/30" style={{ animation: 'fadeIn 0.4s ease' }}>
          <h2 className="text-sm font-semibold text-[#7DD3FC] mb-3">📊 AI 分析结果</h2>
          <VisualizationRenderer packages={packages} />
        </div>
      )}

      {/* ★ 图表网格 - DataV BorderBox1 发光边框 */}
      <div className={`grid grid-cols-3 gap-4 p-6 ${showTable ? '' : 'flex-1'} overflow-auto`}>
        {echarts.length > 0 ? (
          echarts.map((chart, i) => {
            const isGL = isGLOption(chart.option);
            const isAnalysisTable = chart.chart_type === 'analysis_table' && chart.table_data;
            const gridSpan = isGL ? { gridColumn: 'span 3' } : isAnalysisTable ? { gridColumn: 'span 3' } : {};

            return (
              <div key={i} style={gridSpan}>
                <BorderBox1 color={['#7DD3FC', '#38BDF8']} style={{ padding: '6px' }}>
                  {isGL ? (
                    <GLMapView option={chart.option} height={520} title={hideChartTitle ? undefined : chart.title} />
                  ) : isAnalysisTable ? (
                    <div style={{ padding: '12px', background: 'rgba(255,255,255,0.35)', borderRadius: '8px', maxHeight: '380px', overflow: 'auto', backdropFilter: 'blur(10px)', WebkitBackdropFilter: 'blur(10px)' }}>
                      {!hideChartTitle && chart.title && (
                        <h3 className="text-sm font-semibold text-[#7DD3FC] mb-4">{chart.title}</h3>
                      )}
                      <table className="w-full text-xs">
                        <thead>
                          <tr style={{ background: 'rgba(139,92,246,0.06)' }}>
                            {chart.table_data.columns.map((col: string, ci: number) => (
                              <th key={ci} className="px-3 py-2 text-left text-slate-400 font-semibold">{col}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {chart.table_data.rows.map((row: unknown[], ri: number) => (
                            <tr key={ri} style={{ borderBottom: '1px solid rgba(255,255,255,0.30)', background: ri % 2 === 0 ? 'rgba(255,255,255,0.20)' : undefined }}>
                              {row.map((cell: unknown, ci: number) => (
                                <td key={ci} className="px-3 py-2 text-slate-700">{cell !== null && cell !== undefined ? String(cell) : '-'}</td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <EChartView
                      option={chart.option}
                      title={chart.title}
                      height={hideChartTitle ? 370 : 330}
                      hideTitle={hideChartTitle}
                      groupId="dashboard-group"
                      highlightLabel={highlightLabel}
                      onHighlight={setHighlightLabel}
                    />
                  )}
                </BorderBox1>
              </div>
            );
          })
        ) : (
          <div className="col-span-3 flex items-center justify-center h-64 text-slate-500">
            暂无图表 — 请先上传数据
          </div>
        )}
      </div>

      {/* ★ 数据表格 */}
      {showTable && displayRows.length > 0 && (
        <div className="px-6 pb-6 overflow-auto" style={{ maxHeight: '320px' }}>
          <BorderBox1 color={['#7DD3FC', '#38BDF8']} style={{ padding: '4px' }}>
            <div className="rounded-lg" style={{ background: 'rgba(255,255,255,0.35)', backdropFilter: 'blur(10px)', WebkitBackdropFilter: 'blur(10px)' }}>
              <table className="w-full text-sm">
                <thead className="sticky top-0 z-10">
                  <tr style={{ background: 'rgba(139,92,246,0.06)' }}>
                    <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">#</th>
                    {columns.map((col) => (
                      <th key={col} className="px-4 py-2.5 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {displayRows.map((row, i) => (
                    <tr key={i} className="border-t border-black/[0.05] hover:bg-black/[0.03] transition-colors">
                      <td className="px-4 py-2 text-xs text-slate-500">{i + 1}</td>
                      {columns.map((col) => (
                        <td key={col} className="px-4 py-2 text-xs text-slate-700 whitespace-nowrap">
                          {formatTableValue(row[col])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </BorderBox1>
          <p className="text-[10px] text-slate-600 mt-2 text-center">
            共 {displayRows.length} 行 · {columns.length} 列
          </p>
        </div>
      )}

      {/* ★ 同环比表格（从已保存图表中提取） */}
      {tbHbCharts.length > 0 && tbHbCharts.map((tb, idx) => (
        <div key={idx} className="px-6 pb-6">
          <BorderBox1 color={['#7DD3FC', '#38BDF8']} style={{ padding: '8px' }}>
            <div className="rounded-lg p-4" style={{ background: 'rgba(255,255,255,0.35)', backdropFilter: 'blur(10px)', WebkitBackdropFilter: 'blur(10px)' }}>
              <TbHbTable
                data={tb.rows}
                valueColumn={tb.value_column}
                currentYear={tb.current_year}
                previousYear={tb.previous_year}
                hasYoY={tb.has_yoy}
                maxHeight="380px"
              />
            </div>
          </BorderBox1>
        </div>
      ))}

      {/* ★ 底部装饰线 */}
      <div className="px-8 pb-2">
        <div className="w-full h-px bg-gradient-to-r from-transparent via-[#38BDF8]/30 to-transparent" />
      </div>
    </div>
  );
}
