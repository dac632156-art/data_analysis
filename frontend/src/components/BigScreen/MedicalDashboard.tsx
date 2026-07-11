import React, { useMemo } from 'react';
import EChartView, { type EChartsOption } from '../EChartView';
import KPICards, { type KPIItem } from '../KPICards';
import type { CardItem, CardMeta } from '../CardGrid';

interface Props {
  cards?: CardItem[];
  meta?: CardMeta;
  title?: string;
}

/* ─────────────────────────────────────────────
   BI Dashboard — 固定分区大屏布局
   ───────────────────────────────────────────── */

export default function BigScreenDashboard({ cards = [], meta, title = '数据看板' }: Props) {
  const { kpis, trendCharts, mapCharts, rankingCards, tableCards, insightCards, warningCards } = useMemo(() => {
    const kpis: CardItem[] = [];
    const trendCharts: CardItem[] = [];
    const mapCharts: CardItem[] = [];
    const rankingCards: CardItem[] = [];
    const tableCards: CardItem[] = [];
    const insightCards: CardItem[] = [];
    const warningCards: CardItem[] = [];

    for (const c of cards) {
      const t = c.type;
      const ti = (c.title || '').toLowerCase();
      const isTrend = /trend|趋势|growth|增长|累计|cumul/i.test(ti) || t === 'chart';
      const isMap = /map|地图|region|区域|省份|geo/i.test(ti);
      const isRank = /rank|排名|top|排行/i.test(ti);
      const isTable = t === 'table';
      const isInsight = t === 'insight';
      const isWarning = t === 'warning';
      const isKpi = t === 'kpi';

      if (isKpi) kpis.push(c);
      else if (isWarning) warningCards.push(c);
      else if (isInsight) insightCards.push(c);
      else if (isMap) mapCharts.push(c);
      else if (isRank) rankingCards.push(c);
      else if (isTable) tableCards.push(c);
      else if (isTrend) trendCharts.push(c);
      else kpis.push(c);
    }

    return { kpis, trendCharts, mapCharts, rankingCards, tableCards, insightCards, warningCards };
  }, [cards]);

  // 取前8个KPI放第一行
  const topKpis = kpis.slice(0, 8);

  // 主趋势图：选最大的chart
  const mainTrend = trendCharts.find(c => c.size === 'xl' || c.size === 'l') || trendCharts[0];
  const subTrends = trendCharts.filter(c => c !== mainTrend).slice(0, 2);

  // 地图区域
  const mainMap = mapCharts[0];
  const sideMaps = mapCharts.slice(1, 3);

  // 排行
  const mainRank = rankingCards[0];
  const sideRanks = rankingCards.slice(1, 3);

  // 预警
  const warnings = warningCards.slice(0, 2);

  // 洞察
  const insights = insightCards.slice(0, 4);

  return (
    <div className="big-screen w-full h-full flex flex-col overflow-auto"
      style={{
        background: 'linear-gradient(180deg, #020518 0%, #060d2a 50%, #0a0a1e 100%)',
        fontFamily: "'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif",
      }}
    >
      {/* ═══ 顶部标题栏 ═══ */}
      <div className="relative flex items-center justify-between px-8 py-4 border-b"
        style={{ borderBottomColor: 'rgba(125,211,252,0.15)' }}>
        <div className="flex items-center gap-4">
          <div className="w-1.5 h-10 bg-gradient-to-b from-[#7DD3FC] to-[#38BDF8] rounded-full" />
          <h1 className="text-xl font-bold text-white tracking-widest"
            style={{ textShadow: '0 0 20px rgba(125,211,252,0.4)' }}>
            {title}
          </h1>
        </div>
        <div className="flex items-center gap-6 text-xs text-slate-500">
          {meta && (
            <>
              <span>共 <span className="text-cyan-400 font-mono font-bold text-base">{meta.total_cards}</span> 张卡片</span>
              <span>洞察强度 <span className="text-violet-400 font-mono font-bold">{meta.insight_strength}</span></span>
              <span>数据质量 <span className="text-emerald-400 font-mono font-bold">{meta.data_quality}</span></span>
            </>
          )}
        </div>
      </div>

      {/* ═══ 滚动内容区 ═══ */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">

        {/* ──── Row 1: KPI 指标行 ──── */}
        {topKpis.length > 0 && (
          <section className="rounded-2xl p-5"
            style={{ background: 'rgba(6,182,212,0.03)', border: '1px solid rgba(6,182,212,0.1)' }}>
            <div className="flex items-center gap-2 mb-4">
              <div className="w-1 h-4 bg-cyan-400 rounded-full" />
              <h2 className="text-xs font-bold text-slate-400 uppercase tracking-widest">核心指标</h2>
            </div>
            <div className="grid gap-4" style={{ gridTemplateColumns: `repeat(${Math.min(topKpis.length, 4)}, 1fr)` }}>

              {topKpis.map((kpi) => (
                <KpiMiniCard key={kpi.id} card={kpi} />
              ))}
            </div>
          </section>
        )}

        {/* ──── Row 2: 趋势 + 地图 ──── */}
        <div className="grid gap-6" style={{ gridTemplateColumns: '2fr 1fr' }}>
          {/* 左侧：趋势图 */}
          <section className="rounded-2xl p-5"
            style={{ background: 'rgba(56,189,248,0.03)', border: '1px solid rgba(56,189,248,0.1)' }}>
            <div className="flex items-center gap-2 mb-4">
              <div className="w-1 h-4 bg-violet-400 rounded-full" />
              <h2 className="text-xs font-bold text-slate-400 uppercase tracking-widest">趋势分析</h2>
            </div>
            <div className="space-y-6">
              {mainTrend && <ChartBlock card={mainTrend} height={320} />}
              {subTrends.map((t) => <ChartBlock key={t.id} card={t} height={200} />)}
            </div>
          </section>

          {/* 右侧：地图 */}
          <section className="rounded-2xl p-5"
            style={{ background: 'rgba(125,211,252,0.03)', border: '1px solid rgba(125,211,252,0.1)' }}>
            <div className="flex items-center gap-2 mb-4">
              <div className="w-1 h-4 bg-cyan-400 rounded-full" />
              <h2 className="text-xs font-bold text-slate-400 uppercase tracking-widest">地理分布</h2>
            </div>
            <div className="space-y-4">
              {mainMap && <ChartBlock card={mainMap} height={280} />}
              {sideMaps.map((m) => <ChartBlock key={m.id} card={m} height={140} />)}
            </div>
          </section>
        </div>

        {/* ──── Row 3: 排行 + 表格 ──── */}
        <div className="grid gap-6" style={{ gridTemplateColumns: '1fr 1fr' }}>
          {/* 排行 */}
          <section className="rounded-2xl p-5"
            style={{ background: 'rgba(16,185,129,0.03)', border: '1px solid rgba(16,185,129,0.1)' }}>
            <div className="flex items-center gap-2 mb-4">
              <div className="w-1 h-4 bg-emerald-400 rounded-full" />
              <h2 className="text-xs font-bold text-slate-400 uppercase tracking-widest">排行榜</h2>
            </div>
            <div className="space-y-4">
              {mainRank && <RankingBlock card={mainRank} />}
              {sideRanks.map((r) => <RankingBlock key={r.id} card={r} />)}
            </div>
          </section>

          {/* 表格 */}
          <section className="rounded-2xl p-5"
            style={{ background: 'rgba(245,158,11,0.03)', border: '1px solid rgba(245,158,11,0.1)' }}>
            <div className="flex items-center gap-2 mb-4">
              <div className="w-1 h-4 bg-amber-400 rounded-full" />
              <h2 className="text-xs font-bold text-slate-400 uppercase tracking-widest">明细数据</h2>
            </div>
            <div className="space-y-4">
              {tableCards.slice(0, 2).map((t) => <TableBlock key={t.id} card={t} />)}
            </div>
          </section>
        </div>

        {/* ──── Row 4: 预警 + 洞察 ──── */}
        {(warnings.length > 0 || insights.length > 0) && (
          <section className="rounded-2xl p-5"
            style={{ background: 'rgba(244,63,94,0.03)', border: '1px solid rgba(244,63,94,0.1)' }}>
            <div className="flex items-center gap-2 mb-4">
              <div className="w-1 h-4 bg-rose-400 rounded-full" />
              <h2 className="text-xs font-bold text-slate-400 uppercase tracking-widest">分析与洞察</h2>
            </div>
            <div className="grid gap-4" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))' }}>
              {warnings.map((w) => <WarningBlock key={w.id} card={w} />)}
              {insights.map((i) => <InsightBlock key={i.id} card={i} />)}
            </div>
          </section>
        )}

      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════
   子组件
   ═══════════════════════════════════════════════ */

function KpiMiniCard({ card }: { card: CardItem }) {
  const d = card.data as Record<string, unknown>;
  const value = String(d?.value ?? d?.formatted ?? '0');
  const change = d?.change as string | null;
  const kpiType = d?.kpi_type as string;
  const colorMap: Record<string, string> = {
    sum: '#38BDF8', rate: '#34D399', change: '#FB7185',
    avg: '#38BDF8', count: '#FBBF24',
  };
  const color = colorMap[kpiType] || '#38BDF8';
  const isUp = change && !String(change).startsWith('-') && String(change) !== '0';
  const isDown = change && String(change).startsWith('-');

  return (
    <div className="rounded-xl p-4"
      style={{ background: 'rgba(15,23,42,0.6)', border: '1px solid rgba(125,211,252,0.08)' }}>
      <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-2">{card.title}</p>
      <p className="text-2xl font-bold font-mono mb-1" style={{ color }}>{value}</p>
      {change && (
        <p className="text-xs font-bold" style={{ color: isUp ? '#34D399' : isDown ? '#FB7185' : '#94a3b8' }}>
          {isUp ? '▲' : isDown ? '▼' : '—'} {String(change).replace(/[+%]/g, '')}%
        </p>
      )}
    </div>
  );
}

function ChartBlock({ card, height }: { card: CardItem; height: number }) {
  const option = (card.data?.option as EChartsOption | undefined) || (card.data as EChartsOption | undefined);
  if (!option) return null;
  return (
    <div className="rounded-xl p-4"
      style={{ background: 'rgba(15,23,42,0.5)', border: '1px solid rgba(125,211,252,0.08)' }}>
      <h3 className="text-sm font-semibold text-cyan-400 mb-3">{card.title}</h3>
      <EChartView option={option} height={height} />
    </div>
  );
}

function RankingBlock({ card }: { card: CardItem }) {
  const d = card.data as Record<string, unknown>;
  const rows = d?.rows as unknown[][] | undefined;
  const columns = d?.columns as string[] | undefined;
  if (!columns || !rows || rows.length === 0) {
    return <ChartBlock card={card} height={200} />;
  }
  return (
    <div className="rounded-xl p-4"
      style={{ background: 'rgba(15,23,42,0.5)', border: '1px solid rgba(16,185,129,0.08)' }}>
      <h3 className="text-sm font-semibold text-emerald-400 mb-3">{card.title}</h3>
      <table className="w-full text-xs" style={{ borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            {columns.map((col, i) => (
              <th key={i} className="py-2 px-3 text-left font-medium text-slate-400"
                style={{ borderBottom: '1px solid rgba(125,211,252,0.1)' }}>
                {String(col)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 6).map((row, ri) => (
            <tr key={ri} className="hover:bg-cyan-500/5">
              {row.map((cell, ci) => (
                <td key={ci} className="py-2 px-3 text-slate-300"
                  style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                  {formatCell(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TableBlock({ card }: { card: CardItem }) {
  const d = card.data as Record<string, unknown>;
  const rows = d?.rows as unknown[][] | undefined;
  const columns = d?.columns as string[] | undefined;
  if (!columns || !rows || rows.length === 0) return null;
  return (
    <div className="rounded-xl p-4 overflow-x-auto"
      style={{ background: 'rgba(15,23,42,0.5)', border: '1px solid rgba(245,158,11,0.08)' }}>
      <h3 className="text-sm font-semibold text-amber-400 mb-3">{card.title}</h3>
      <table className="w-full text-xs" style={{ borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ background: 'rgba(125,211,252,0.06)' }}>
            {columns.map((col, i) => (
              <th key={i} className="py-2 px-3 text-left font-medium text-slate-400"
                style={{ borderBottom: '1px solid rgba(125,211,252,0.1)' }}>
                {String(col)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 8).map((row, ri) => (
            <tr key={ri} className="hover:bg-cyan-500/5">
              {row.map((cell, ci) => (
                <td key={ci} className="py-2 px-3 text-slate-300"
                  style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                  {formatCell(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function WarningBlock({ card }: { card: CardItem }) {
  const d = card.data as Record<string, unknown>;
  const text = d?.text || d?.message || card.title;
  return (
    <div className="rounded-xl p-3 flex items-start gap-2"
      style={{ background: 'rgba(245,158,11,0.06)', border: '1px solid rgba(245,158,11,0.2)' }}>
      <span className="text-sm mt-0.5">⚠️</span>
      <p className="text-xs text-slate-300 leading-relaxed">{String(text)}</p>
    </div>
  );
}

function InsightBlock({ card }: { card: CardItem }) {
  const d = card.data as Record<string, unknown>;
  const text = d?.text || d?.content || card.title;
  const isConclusion = card.type === 'insight';
  return (
    <div className="rounded-xl p-3"
      style={{
        background: 'rgba(56,189,248,0.04)',
        border: isConclusion ? 'rgba(56,189,248,0.2)' : 'rgba(125,211,252,0.1)',
      }}>
      <p className="text-xs text-slate-300 leading-relaxed">{String(text)}</p>
    </div>
  );
}

function formatCell(val: unknown): string {
  if (val === null || val === undefined) return '-';
  if (typeof val === 'number') {
    if (Number.isInteger(val)) return val.toLocaleString();
    return val.toFixed(2);
  }
  if (typeof val === 'object') {
    const obj = val as Record<string, unknown>;
    if ('value' in obj) return String(obj.value);
    return '-';
  }
  return String(val);
}

