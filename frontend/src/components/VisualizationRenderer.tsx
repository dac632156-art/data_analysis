/* VisualizationRenderer - V2 统一可视化渲染器
   根据 type 字段分发渲染：chart / table / kpi / insight / unsupported
   ★ 所有颜色统一来自 theme/（Galaxy Executive Dashboard），禁止写死。 */
import React from 'react';
import { marked } from 'marked';
import EChartView, { EChartsOption } from './EChartView';
import { EtherealChart } from './EtherealCharts/EtherealChart';
import EtherealTable from './EtherealCharts/EtherealTable';
import type { AnalysisPackage, PackageKPIItem, PackageTableData, PackageChartItem } from '../types/api';

// 与 AnalysisPage 的 renderMarkdown 保持一致：洞察/结论由后端 AI 生成（可信源），
// 用 marked 渲染 Markdown（## 标题、- 列表、**加粗**），避免原始 Markdown 文本裸显。
function renderMarkdown(text: string): string {
  return marked.parse(text || '') as string;
}

/**
 * 把可能是对象/数组的「文本」归一为字符串，杜绝 [object Object]。
 * 后端 insights/conclusions/findings 偶尔返回 BusinessFinding 对象
 * （真实字段为 title / description / business_meaning，而非 .text/.content/.summary），
 * 而非纯字符串；这里优先提取常见可读字段，否则 JSON 序列化。
 */
function normalizeText(input: unknown): string {
  if (input == null) return '';
  if (typeof input === 'string') return input;
  if (typeof input === 'number' || typeof input === 'boolean') return String(input);
  if (Array.isArray(input)) return input.map((v) => normalizeText(v)).join(' ');
  if (typeof input === 'object') {
    const obj = input as Record<string, unknown>;
    const cand =
      obj.text ??
      obj.content ??
      obj.summary ??
      obj.value ??
      obj.message ??
      obj.detail ??
      obj.business_meaning ??
      obj.description ??
      obj.title;
    if (cand != null) return normalizeText(cand);
    try {
      return JSON.stringify(obj);
    } catch {
      return String(input);
    }
  }
  return String(input);
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
          ? (kpi.change && kpi.change.startsWith('-') ? '#FB7185' : '#34D399')
          : '#38BDF8';
        const arrow = kpi.change ? (kpi.change.startsWith('+') ? '↑' : kpi.change.startsWith('-') ? '↓' : '') : null;
        return (
          <div key={i} className="glass-card" style={{ flex: '1 1 140px', padding: '12px 16px', textAlign: 'center', minWidth: 100 }}>
            <p style={{ fontSize: 10, color: 'var(--text-secondary)', marginBottom: 4 }}>{kpi.label}</p>
            <p style={{ fontSize: 22, fontWeight: 700, color: valueColor, fontFamily: 'monospace', margin: 0 }}>
              {isChange ? (kpi.value + '%') : kpi.value}
              {arrow && <span style={{ fontSize: 14, color: arrow === '↑' ? '#34D399' : '#FB7185' }}> {arrow}</span>}
            </p>
          </div>
        );
      })}
    </div>
  );
}

function TableBlock({ table }: { table: PackageTableData }) {
  if (!table || !table.rows || table.rows.length === 0) return null;

  // 全站表格统一走 EtherealTable（可视化模板库仙气风格：背景.png / 第1列胶囊 / 浅色毛玻璃）。
  // EtherealTable 已内置兼容三种 rows 形态：
  //   1) 纯值 dict 行 {列名: 值}
  //   2) 含 {value} 包装的 dict 行 {列名: {value, direction, color, ...}}
  //   3) 二维 cell 数组 [{value, color, direction, highlight}, ...]（后端 RenderedCell[][]，profile_overview 走这种）
  // 当 rows 为二维数组时，必须用 columns prop 显式告知列名（EtherealTable 无法从二维数组反推）。
  return (
    <div style={{ marginBottom: 12 }}>
      <EtherealTable
        chartNode={{ title: table.title, columns: table.columns, rows: table.rows as unknown[] }}
        columns={table.columns}
      />
    </div>
  );
}

// 外部零干预：不计算、不传递 height，所有图表组件使用自身内部写好的默认高度/形状。
function ChartBlock({ chart }: { chart: PackageChartItem }) {
  if (!chart || !chart.option) return null;
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <span style={{ fontSize: 12, color: 'var(--text-primary)' }}>{chart.title}</span>
      </div>
      <EtherealChart
        slot={chart.slot}
        chartType={chart.chart_type}
        chartNode={chart.option}
        data={chart.raw_data}
        title={chart.title}
      />
    </div>
  );
}

function InsightBlock({ insights }: { insights?: unknown[] | unknown }) {
  const raw = Array.isArray(insights) ? insights : (insights != null ? [insights] : []);
  const list = raw.map((v) => normalizeText(v)).filter((s) => s.trim().length > 0);
  if (list.length === 0) return null;
  return (
    <div style={{ marginTop: 8, padding: '10px 14px', background: 'rgba(124,58,237,0.059)', borderRadius: 8, border: '1px solid rgba(124,58,237,0.12)' }}>
      {list.map((ins, i) => (
        <div key={i} className="md-body" style={{ fontSize: 12, color: 'var(--text-secondary)', margin: '4px 0', lineHeight: 1.6 }} dangerouslySetInnerHTML={{ __html: renderMarkdown(ins) }} />
      ))}
    </div>
  );
}

function ConclusionBlock({ conclusions }: { conclusions?: unknown[] | unknown }) {
  const raw = Array.isArray(conclusions) ? conclusions : (conclusions != null ? [conclusions] : []);
  const list = raw.map((v) => normalizeText(v)).filter((s) => s.trim().length > 0);
  if (list.length === 0) return null;
  return (
    <div style={{ marginTop: 12, padding: '12px 16px', background: 'rgba(124,58,237,0.059)', borderRadius: 8, border: '1px solid rgba(124,58,237,0.15)' }}>
    <p style={{ fontSize: 11, color: '#7c3aed', fontWeight: 600, marginBottom: 6 }}>核心结论</p>
      {list.map((c, i) => (
        <div key={i} style={{ display: 'flex', gap: 6, alignItems: 'baseline', fontSize: 12, color: 'var(--text-primary)', margin: '6px 0', lineHeight: 1.6 }}>
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
      <div style={{ padding: 48, textAlign: 'center', color: 'var(--text-muted)' }}>
        <span style={{ fontSize: 32, display: 'block', marginBottom: 8 }}>📊</span>
        <p style={{ fontSize: 14, margin: 0 }}>暂无分析结果</p>
        <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: '4px 0 0' }}>请先在数据洞察中生成分析计划并执行</p>
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
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>分析问题：</span>
        <span style={{ fontSize: 13, color: 'var(--text-primary)', fontWeight: 600 }}>{pkg.business_question}</span>
        <span style={{ marginLeft: 8, fontSize: 10, color: '#38BDF8', background: 'rgba(56,189,248,0.1)', padding: '1px 8px', borderRadius: 4 }}>
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
/** 将 #RRGGBB 转为带 alpha 的 rgba()（用于背景/边框淡色） */
function hexA(hex: string, alpha: number): string {
  const h = hex.replace('#', '');
  const r = parseInt(h.substring(0, 2), 16);
  const g = parseInt(h.substring(2, 4), 16);
  const b = parseInt(h.substring(4, 6), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}
