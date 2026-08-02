/* VisualizationRenderer - V2 统一可视化渲染器
   根据 type 字段分发渲染：chart / table / kpi / insight / unsupported
   ★ 所有颜色统一来自 theme/（Galaxy Executive Dashboard），禁止写死。 */
import React from 'react';
import { marked } from 'marked';
import EChartView, { EChartsOption } from './EChartView';
import ProfileOverviewTable, { Cell, type OverviewCell } from './BigScreen/ProfileOverviewTable';
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
  // 群画像总览表：cell 是 RenderedCell dict（{value, cell_type, rank, direction, ...}），
  // 普通 String(cell) 会得到 "[object Object]"。直接复用 ProfileOverviewTable 渲染，
  // 与仪表盘 EGridLayout 中的群画像表视觉完全一致（染色/进度条/区块头）。
  if (table.table_type === 'profile_overview') {
    // 后端原始 table.rows 是「按列名索引的 dict 行」：
    //   [{"分群": {value:"群0", type:"category", ...}, "人数": {value:2034, ...}, ...}, ...]
    // 但 ProfileOverviewTable 期望「按列位置索引的二维单元格数组」rows[i][j]。
    // 这里统一转换（与仪表盘 DashboardPage 中的转换逻辑一致），
    // 否则每行按数字位置取单元格会拿到 undefined → 每格显示 "—"。
    const cellRows = (table.rows as unknown[]).map((row) => {
      if (Array.isArray(row)) return row as OverviewCell[];
      return (table.columns || []).map((col) => {
        const cell =
          (row && typeof row === 'object' ? (row as Record<string, any>)[col] : null) || {};
        return {
          value: cell.value ?? null,
          rank: cell.rank ?? 0,
          direction: cell.direction ?? 'neutral',
          // 后端原始 dict 行为 type，渲染层为 cell_type，二者都兼容
          cell_type: cell.cell_type ?? cell.type ?? 'text',
        };
      });
    });
    return (
      <ProfileOverviewTable
        chart={{
          title: table.title,
          table_data: {
            rows: cellRows,
            columns: table.columns,
          },
          chart_config: (table.chart_config || {}) as { blocks?: { title: string; keys: string[] }[] },
        }}
        hideTitle={false}
      />
    );
  }
  return (
    <div style={{ marginBottom: 12, overflow: 'auto', maxHeight: 320 }}>
      {table.slot ? (
        <div style={{ marginBottom: 4 }}>
          <span style={{ fontSize: 10, color: P.primary, background: hexA(P.primary, 0.1), padding: '1px 8px', borderRadius: 4, fontFamily: 'monospace' }}>
            {table.slot}
          </span>
        </div>
      ) : null}
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
          {table.rows.map((row, ri) => {
            // 兼容 dict 行：按 columns 顺序提取值（RFM/K-means 集群画像等模块的对话协议）
            const cells: unknown[] = Array.isArray(row)
              ? row
              : typeof row === 'object' && row !== null
                ? table.columns.map(col => (row as Record<string, unknown>)[col])
                : null;
            return (
              <tr key={ri} style={ri % 2 === 0 ? { background: 'rgba(255,255,255,0.02)' } : undefined}>
                {isRanking && <td style={tdStyle}>{ri + 1}</td>}
                {cells ? cells.map((cell, ci) => {
                  const typed = cell as Record<string, unknown>;
                  const isCellObj = typeof cell === 'object' && cell !== null
                    && (('direction' in typed) || ('rank' in typed) || ('value' in typed) || ('cell_type' in typed) || ('type' in typed) || ('highlight' in typed) || ('count' in typed));
                  if (isCellObj) {
                    return (
                      <Cell
                        key={ci}
                        cell={{
                          value: (typed.value as number | string | null) ?? null,
                          rank: (typed.rank as number) ?? 0,
                          direction: ((typed.direction as string) ?? 'neutral') as OverviewCell['direction'],
                          cell_type: ((typed.cell_type as string) ?? (typed.type as string) ?? 'number') as OverviewCell['cell_type'],
                          highlight: Boolean(typed.highlight),
                          count: (typed.count as number | undefined),
                        }}
                      />
                    );
                  }
                  return (
                    <td key={ci} style={{ ...tdStyle, fontWeight: isRanking && ri < 3 ? 700 : 400 }}>
                      {cell !== null && cell !== undefined ? String(cell) : '-'}
                    </td>
                  );
                }) : (
                  <td style={tdStyle}>-</td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function _heatmapRowCount(option: any): number {
  const yAxis = option?.yAxis;
  if (!yAxis) return 0;
  const ys = Array.isArray(yAxis) ? yAxis : [yAxis];
  for (const y of ys) {
    if (y && Array.isArray(y.data) && y.data.length > 0) return y.data.length;
  }
  return 0;
}

// 同期群下三角热力图按 cohort 行数展开高度，避免 360px 被纵向挤扁、y 轴标签重叠。
function getChartHeight(chart: PackageChartItem): number {
  const type = chart.chart_type;
  const opt = chart.option as any;
  if (type === 'cohort_heatmap' || type === 'heatmap') {
    const rows = _heatmapRowCount(opt);
    if (rows > 0) return Math.max(360, 80 + rows * 38);
    return 420;
  }
  if (type === 'dual_axis' || type === 'cohort_trend') return 420;
  if (type === 'graph') return 520;  // 关系网络图：力导向布局需更大画布看清抱团
  return 360;
}

function ChartBlock({ chart }: { chart: PackageChartItem }) {
  if (!chart || !chart.option) return null;
  // 图族（hbar_family，流失归因 F）：option 不是标准 ECharts option，
  // 而是 {维度名: 子图option} 字典 —— 遍历渲染 N 张横向偏移图（每维度一张）。
  if (chart.chart_type === 'hbar_family') {
    const family = chart.option as Record<string, EChartsOption>;
    const dims = Object.keys(family).filter(
      (d) => family[d] && Object.keys(family[d]).length > 0,
    );
    if (dims.length === 0) return null;
    return (
      <div style={{ marginBottom: 12 }}>
        {chart.slot ? (
          <div style={{ marginBottom: 4 }}>
            <span style={{ fontSize: 10, color: P.primary, background: hexA(P.primary, 0.1), padding: '1px 8px', borderRadius: 4, fontFamily: 'monospace' }}>
              {chart.slot}
            </span>
          </div>
        ) : null}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
          <span style={{ fontSize: 12, color: P.textPrimary }}>{chart.title}</span>
        </div>
        {dims.map((dim) => (
          <div key={dim} style={{ marginBottom: 10 }}>
            <EChartView option={family[dim]} height={360} />
          </div>
        ))}
      </div>
    );
  }
  return (
    <div style={{ marginBottom: 12 }}>
      {chart.slot ? (
        <div style={{ marginBottom: 4 }}>
          <span style={{ fontSize: 10, color: P.primary, background: hexA(P.primary, 0.1), padding: '1px 8px', borderRadius: 4, fontFamily: 'monospace' }}>
            {chart.slot}
          </span>
        </div>
      ) : null}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <span style={{ fontSize: 12, color: P.textPrimary }}>{chart.title}</span>
      </div>
      <EChartView option={chart.option as EChartsOption} height={getChartHeight(chart)} />
    </div>
  );
}

function InsightBlock({ insights }: { insights?: string[] | string }) {
  const list = Array.isArray(insights)
    ? insights
    : (insights ? [insights] : []);
  if (list.length === 0) return null;
  return (
    <div style={{ marginTop: 8, padding: '10px 14px', background: 'rgba(139,92,246,0.059)', borderRadius: 8, border: '1px solid rgba(139,92,246,0.12)' }}>
      {list.map((ins, i) => (
        <div key={i} className="md-body" style={{ fontSize: 12, color: P.textSecondary, margin: '4px 0', lineHeight: 1.6 }} dangerouslySetInnerHTML={{ __html: renderMarkdown(ins) }} />
      ))}
    </div>
  );
}

function ConclusionBlock({ conclusions }: { conclusions?: string[] | string }) {
  const list = Array.isArray(conclusions)
    ? conclusions
    : (conclusions ? [conclusions] : []);
  if (list.length === 0) return null;
  return (
    <div style={{ marginTop: 12, padding: '12px 16px', background: 'rgba(139,92,246,0.059)', borderRadius: 8, border: '1px solid rgba(139,92,246,0.15)' }}>
      <p style={{ fontSize: 11, color: '#8B5CF6', fontWeight: 600, marginBottom: 6 }}>核心结论</p>
      {list.map((c, i) => (
        <div key={i} style={{ display: 'flex', gap: 6, alignItems: 'baseline', fontSize: 12, color: P.textPrimary, margin: '6px 0', lineHeight: 1.6 }}>
          <span style={{ color: '#8B5CF6', fontWeight: 700, flexShrink: 0 }}>{i + 1}.</span>
          <div className="md-body" style={{ flex: 1, minWidth: 0 }} dangerouslySetInnerHTML={{ __html: renderMarkdown(c) }} />
        </div>
      ))}
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

  if (!pkg.can_run) return null;

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
  position: 'sticky', top: 0, background: 'rgba(15,23,42,0.96)', zIndex: 1,
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
