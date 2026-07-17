/* VisualizationRenderer - V2 统一可视化渲染器
   根据 type 字段分发渲染：chart / table / kpi / insight / unsupported
   ★ 所有颜色统一来自 theme/（Galaxy Executive Dashboard），禁止写死。 */
import React from 'react';
import { marked } from 'marked';
import EChartView, { EChartsOption } from './EChartView';
import { theme } from '../theme';
import type { AnalysisPackage, PackageKPIItem, PackageTableData, PackageChartItem } from '../types/api';

const P = theme.palette;
const C = theme.chart;

// 与 AnalysisPage 的 renderMarkdown 保持一致：洞察/结论由后端 AI 生成（可信源），
// 用 marked 渲染 Markdown（## 标题、- 列表、**加粗**），避免原始 Markdown 文本裸显。
function renderMarkdown(text: string): string {
  return marked.parse(text || '') as string;
}

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
        const isChange = kpi.kpi_type === 'rate' || kpi.kpi_type === 'change';
        const valueColor = isChange
          ? (kpi.change && kpi.change.startsWith('-') ? P.danger : P.success)
          : P.primary;
        const arrow = kpi.change ? (kpi.change.startsWith('+') ? '↑' : kpi.change.startsWith('-') ? '↓' : '') : null;
        return (
          <div key={i} className="glass-card" style={{ flex: '1 1 140px', padding: '12px 16px', textAlign: 'center', minWidth: 100 }}>
            <p style={{ fontSize: 10, color: P.textSecondary, marginBottom: 4 }}>{kpi.label}</p>
            <p style={{ fontSize: 22, fontWeight: 700, color: valueColor, fontFamily: 'monospace', margin: 0 }}>
              {isChange ? (kpi.value + '%') : kpi.value}
              {arrow && <span style={{ fontSize: 14, color: arrow === '↑' ? P.success : P.danger }}> {arrow}</span>}
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
      <h4 style={{ fontSize: 12, color: P.primary, marginBottom: 6 }}>{table.title}</h4>
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
            <tr key={ri} style={ri % 2 === 0 ? { background: 'rgba(255,255,255,0.02)' } : undefined}>
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
        <span style={{ fontSize: 12, color: P.textPrimary }}>{chart.title}</span>
      </div>
      <EChartView option={chart.option as EChartsOption} height={360} />
    </div>
  );
}

function InsightBlock({ insights }: { insights: string[] }) {
  if (!insights || insights.length === 0) return null;
  return (
    <div style={{ marginTop: 8, padding: '10px 14px', background: 'rgba(139,92,246,0.059)', borderRadius: 8, border: '1px solid rgba(139,92,246,0.12)' }}>
      {insights.map((ins, i) => (
        <div key={i} className="md-body" style={{ fontSize: 12, color: P.textSecondary, margin: '4px 0', lineHeight: 1.6 }} dangerouslySetInnerHTML={{ __html: renderMarkdown(ins) }} />
      ))}
    </div>
  );
}

function ConclusionBlock({ conclusions }: { conclusions: string[] }) {
  if (!conclusions || conclusions.length === 0) return null;
  return (
    <div style={{ marginTop: 12, padding: '12px 16px', background: 'rgba(139,92,246,0.059)', borderRadius: 8, border: '1px solid rgba(139,92,246,0.15)' }}>
      <p style={{ fontSize: 11, color: '#8B5CF6', fontWeight: 600, marginBottom: 6 }}>核心结论</p>
      {conclusions.map((c, i) => (
        <div key={i} style={{ display: 'flex', gap: 6, alignItems: 'baseline', fontSize: 12, color: P.textPrimary, margin: '6px 0', lineHeight: 1.6 }}>
          <span style={{ color: '#8B5CF6', fontWeight: 700, flexShrink: 0 }}>{i + 1}.</span>
          <div className="md-body" style={{ flex: 1, minWidth: 0 }} dangerouslySetInnerHTML={{ __html: renderMarkdown(c) }} />
        </div>
      ))}
    </div>
  );
}

function UnsupportedBlock({ pkg }: { pkg: AnalysisPackage }) {
  const reasons = (pkg.insights || []).filter(s => s);
  const reasonText = reasons.length > 0 ? reasons[0] : '当前数据不支持该分析';
  const fallbackFrom = pkg.fallback_from || '无';
  // 优先使用后端按分析类型动态生成的建议；缺失时给一个通用的兜底提示
  const suggestion = (pkg.suggestion && pkg.suggestion.trim())
    ? pkg.suggestion
    : '请检查数据是否包含该分析所需的字段（如词云需要文本/分类列，趋势需要日期+数值列），或更换分析表述后重试。';

  return (
    <div style={{
      margin: '12px 0', padding: 16,
      background: `linear-gradient(135deg, ${hexA(P.warning, 0.06)} 0%, ${hexA(P.danger, 0.03)} 100%)`,
      border: `1px solid ${hexA(P.warning, 0.25)}`, borderRadius: 10,
      display: 'flex', alignItems: 'flex-start', gap: 12,
    }}>
      <div style={{
        width: 28, height: 28, borderRadius: '50%',
        background: hexA(P.warning, 0.15), display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexShrink: 0,
      }}>
        <span style={{ fontSize: 14 }}>⚠️</span>
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{ fontSize: 13, color: P.warning, fontWeight: 600, margin: 0 }}>
          无法执行分析
        </p>
        <p style={{ fontSize: 11, color: P.textPrimary, margin: '4px 0 0' }}>
          问题：{pkg.business_question}
        </p>
        <p style={{ fontSize: 10, color: P.textSecondary, margin: '4px 0 0' }}>
          原因：{reasonText} | 降级来源：{fallbackFrom}
        </p>
        <p style={{ fontSize: 10, color: P.textDisabled, margin: '6px 0 0', lineHeight: 1.5 }}>
          💡 建议：{suggestion}
        </p>
      </div>
    </div>
  );
}

/* ===== 主组件 ===== */

export default function VisualizationRenderer({ packages, selectedPackageIndex = 0 }: Props) {
  if (!packages || packages.length === 0) {
    return (
      <div style={{ padding: 48, textAlign: 'center', color: P.textDisabled }}>
        <span style={{ fontSize: 32, display: 'block', marginBottom: 8 }}>📊</span>
        <p style={{ fontSize: 14, margin: 0 }}>暂无分析结果</p>
        <p style={{ fontSize: 11, color: P.textDisabled, margin: '4px 0 0' }}>请先在数据洞察中生成分析计划并执行</p>
      </div>
    );
  }

  const pkg = packages[Math.min(selectedPackageIndex, packages.length - 1)] || packages[0];
  if (!pkg) return null;

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
      <div style={{ marginBottom: 12 }}>
        <span style={{ fontSize: 11, color: P.textDisabled }}>分析问题：</span>
        <span style={{ fontSize: 13, color: P.textPrimary, fontWeight: 600 }}>{pkg.business_question}</span>
        <span style={{ marginLeft: 8, fontSize: 10, color: P.primary, background: hexA(P.primary, 0.1), padding: '1px 8px', borderRadius: 4 }}>
          {pkg.analysis_type}
        </span>
      </div>

      <KPIBlock kpis={pkg.kpis || []} />

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))',
        gap: 12,
      }}>
        {(pkg.charts || []).map((chart, i) => (
          <div key={i}>
            <ChartBlock chart={chart} />
          </div>
        ))}
      </div>

      {(pkg.tables || []).map((table, i) => (
        <TableBlock key={i} table={table} />
      ))}

      <InsightBlock insights={pkg.insights || []} />
      <ConclusionBlock conclusions={pkg.conclusions || []} />
    </div>
  );
}

/* ===== 内联样式 ===== */
const thStyle: React.CSSProperties = {
  padding: '6px 10px', textAlign: 'left', color: P.textSecondary, fontSize: 10,
  borderBottom: `1px solid ${C.grid}`, fontWeight: 500,
};
const tdStyle: React.CSSProperties = {
  padding: '5px 10px', borderBottom: `1px solid ${P.border}`, color: P.textPrimary,
};
/** 将 #RRGGBB 转为带 alpha 的 rgba()（用于背景/边框淡色） */
function hexA(hex: string, alpha: number): string {
  const h = hex.replace('#', '');
  const r = parseInt(h.substring(0, 2), 16);
  const g = parseInt(h.substring(2, 4), 16);
  const b = parseInt(h.substring(4, 6), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}
