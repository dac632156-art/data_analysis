/* VisualizationRenderer - V2 统一可视化渲染器
   根据 type 字段分发渲染：chart / table / kpi / insight / unsupported */
import React from 'react';
import EChartView, { EChartsOption } from './EChartView';
import type { AnalysisPackage, PackageKPIItem, PackageTableData, PackageChartItem } from '../types/api';

interface Props {
  packages: AnalysisPackage[];
  selectedPackageIndex?: number;
}

/* ===== 子渲染器 ===== */

function KPIBlock({ kpis }: { kpis: PackageKPIItem[] }) {
  if (!kpis || kpis.length === 0) return null;
  return (
    <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 16 }}>
      {kpis.map((kpi, i) => {
        const colorMap: Record<string, string> = {
          sum: '#22d3ee', avg: '#a78bfa', count: '#f59e0b', rate: '#4ade80', change: '#f87171',
        };
        const color = colorMap[kpi.kpi_type] || '#22d3ee';
        const isChange = kpi.kpi_type === 'rate' || kpi.kpi_type === 'change';
        const arrow = kpi.change ? (kpi.change.startsWith('+') ? '↑' : kpi.change.startsWith('-') ? '↓' : '') : null;
        return (
          <div key={i} className="glass-card" style={{ flex: '1 1 140px', padding: '12px 16px', textAlign: 'center', minWidth: 100 }}>
            <p style={{ fontSize: 10, color: '#94a3b8', marginBottom: 4 }}>{kpi.label}</p>
            <p style={{ fontSize: 22, fontWeight: 700, color, fontFamily: 'monospace', margin: 0 }}>
              {isChange ? (kpi.value + '%') : kpi.value}
              {arrow && <span style={{ fontSize: 14, color: arrow === '↑' ? '#4ade80' : '#f87171' }}> {arrow}</span>}
            </p>
          </div>
        );
      })}
    </div>
  );
}

function TableBlock({ table }: { table: PackageTableData }) {
  if (!table || !table.rows || table.rows.length === 0) return null;
  const isRanking = table.table_type === 'ranking';
  return (
    <div style={{ marginBottom: 12, overflow: 'auto', maxHeight: 320 }}>
      <h4 style={{ fontSize: 12, color: '#a78bfa', marginBottom: 6 }}>{table.title}</h4>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
        <thead>
          <tr>
            {isRanking && <th style={thStyle}>#</th>}
            {table.columns.map((col, i) => (
              <th key={i} style={thStyle}>{col}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.rows.map((row, ri) => (
            <tr key={ri} style={ri % 2 === 0 ? { background: 'rgba(15,23,42,0.5)' } : undefined}>
              {isRanking && <td style={tdStyle}>{ri + 1}</td>}
              {Array.isArray(row) ? row.map((cell, ci) => (
                <td key={ci} style={{ ...tdStyle, fontWeight: isRanking && ri < 3 ? 700 : 400 }}>
                  {cell !== null && cell !== undefined ? String(cell) : '-'}
                </td>
              )) : (
                <td style={tdStyle}>-</td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ChartBlock({ chart }: { chart: PackageChartItem }) {
  if (!chart || !chart.option) return null;
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        {chart.role === 'primary' && <span style={badgeStyle('#22d3ee')}>主图</span>}
        {chart.role === 'secondary' && <span style={badgeStyle('#a78bfa')}>辅图</span>}
        <span style={{ fontSize: 12, color: '#cbd5e1' }}>{chart.title}</span>
      </div>
      <EChartView option={chart.option as EChartsOption} height={chart.role === 'primary' ? 380 : 280} />
    </div>
  );
}

function InsightBlock({ insights }: { insights: string[] }) {
  if (!insights || insights.length === 0) return null;
  return (
    <div style={{ marginTop: 8, padding: '10px 14px', background: 'rgba(34,211,238,0.05)', borderRadius: 8, border: '1px solid rgba(34,211,238,0.1)' }}>
      {insights.map((ins, i) => (
        <p key={i} style={{ fontSize: 12, color: '#94a3b8', margin: '4px 0', lineHeight: 1.6 }}>{ins}</p>
      ))}
    </div>
  );
}

function UnsupportedBlock({ pkg }: { pkg: AnalysisPackage }) {
  const reasons = (pkg.insights || []).filter(s => s);
  const reasonText = reasons.length > 0 ? reasons[0] : '当前数据不支持该分析';
  const fallbackFrom = pkg.fallback_from || '无';

  return (
    <div style={{
      margin: '12px 0', padding: 16,
      background: 'linear-gradient(135deg, rgba(245,158,11,0.06) 0%, rgba(239,68,68,0.03) 100%)',
      border: '1px solid rgba(245,158,11,0.25)', borderRadius: 10,
      display: 'flex', alignItems: 'flex-start', gap: 12,
    }}>
      <div style={{
        width: 28, height: 28, borderRadius: '50%',
        background: 'rgba(245,158,11,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexShrink: 0,
      }}>
        <span style={{ fontSize: 14 }}>⚠️</span>
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{ fontSize: 13, color: '#f59e0b', fontWeight: 600, margin: 0 }}>
          无法执行分析
        </p>
        <p style={{ fontSize: 11, color: '#cbd5e1', margin: '4px 0 0' }}>
          问题：{pkg.business_question}
        </p>
        <p style={{ fontSize: 10, color: '#94a3b8', margin: '4px 0 0' }}>
          原因：{reasonText} | 降级来源：{fallbackFrom}
        </p>
        <p style={{ fontSize: 10, color: '#64748b', margin: '6px 0 0', lineHeight: 1.5 }}>
          💡 建议：检查数据是否包含足够的数值列和时间列。如需分析增长趋势，请确保数据包含日期和数值字段；如需排名分析，请确保包含分类字段。
        </p>
      </div>
    </div>
  );
}

/* ===== 主组件 ===== */

export default function VisualizationRenderer({ packages, selectedPackageIndex = 0 }: Props) {
  if (!packages || packages.length === 0) {
    return (
      <div style={{ padding: 48, textAlign: 'center', color: '#64748b' }}>
        <span style={{ fontSize: 32, display: 'block', marginBottom: 8 }}>📊</span>
        <p style={{ fontSize: 14, margin: 0 }}>暂无分析结果</p>
        <p style={{ fontSize: 11, color: '#475569', margin: '4px 0 0' }}>请先在数据洞察中生成分析计划并执行</p>
      </div>
    );
  }

  const pkg = packages[Math.min(selectedPackageIndex, packages.length - 1)] || packages[0];
  if (!pkg) return null;

  // 不支持的包
  if (!pkg.can_run) {
    return (
      <div style={{ animation: 'fadeIn 0.3s ease' }}>
        <UnsupportedBlock pkg={pkg} />
      </div>
    );
  }

  return (
    <div style={{ padding: '8px 0', animation: 'fadeIn 0.35s ease' }}>
      <style>{`@keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }`}</style>
      {/* 业务问题标题 */}
      <div style={{ marginBottom: 12 }}>
        <span style={{ fontSize: 11, color: '#64748b' }}>分析问题：</span>
        <span style={{ fontSize: 13, color: '#e2e8f0', fontWeight: 600 }}>{pkg.business_question}</span>
        <span style={{ marginLeft: 8, fontSize: 10, color: '#8b5cf6', background: 'rgba(139,92,246,0.1)', padding: '1px 8px', borderRadius: 4 }}>
          {pkg.analysis_type}
        </span>
      </div>

      {/* KPI 指标 */}
      <KPIBlock kpis={pkg.kpis || []} />

      {/* 图表 — primary 优先 */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        {(pkg.charts || []).map((chart, i) => (
          <div key={i} style={chart.role === 'primary' ? { gridColumn: '1 / -1' } : undefined}>
            <ChartBlock chart={chart} />
          </div>
        ))}
      </div>

      {/* 表格 */}
      {(pkg.tables || []).map((table, i) => (
        <TableBlock key={i} table={table} />
      ))}

      {/* 洞察文字 */}
      <InsightBlock insights={pkg.insights || []} />
    </div>
  );
}

/* ===== 内联样式 ===== */
const thStyle: React.CSSProperties = {
  padding: '6px 10px', textAlign: 'left', color: '#94a3b8', fontSize: 10,
  borderBottom: '1px solid rgba(34,211,238,0.1)', fontWeight: 500,
};
const tdStyle: React.CSSProperties = {
  padding: '5px 10px', borderBottom: '1px solid rgba(34,211,238,0.04)', color: '#cbd5e1',
};
const badgeStyle = (color: string): React.CSSProperties => ({
  fontSize: 9, color, background: `${color}15`, padding: '1px 6px', borderRadius: 4,
});
