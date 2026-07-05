import React, { useMemo } from "react";
import EChartView, { EChartsOption } from "./EChartView";

export interface CardItem {
  id: string;
  type: "kpi" | "chart" | "table" | "insight" | "warning" | "fallback";
  title: string;
  priority: number;
  size: "s" | "m" | "l" | "xl";
  score: number;
  data: Record<string, unknown>;
  chart_type?: string;
  fallback_chain?: Array<Record<string, unknown>>;
}

export interface CardMeta {
  total_cards: number;
  insight_strength: number;
  data_quality: number;
}

interface Props {
  cards: CardItem[];
  meta?: CardMeta;
  onCardClick?: (card: CardItem) => void;
}

function formatCellValue(val: unknown): string {
  if (val === null || val === undefined) return "-";
  if (typeof val === "number") {
    if (Number.isInteger(val)) return val.toLocaleString();
    return val.toFixed(2);
  }
  if (typeof val === "object") return JSON.stringify(val);
  return String(val);
}

function getChartHeight(size: string): number {
  switch (size) {
    case "xl": return 350;
    case "l": return 280;
    case "m": return 220;
    default: return 160;
  }
}

function KPICard({ card }: { card: CardItem }) {
  const d = card.data as Record<string, unknown>;
  const value = String(d?.value ?? d?.formatted ?? "0");
  const change = d?.change as string | null;
  const kpiType = d?.kpi_type as string;
  const colorMap: Record<string, string> = {
    sum: "#06b6d4", rate: "#10b981", change: "#f43f5e",
    avg: "#8b5cf6", count: "#f59e0b",
  };
  const color = colorMap[kpiType] || "#06b6d4";
  const isUp = change && !String(change).startsWith("-") && String(change) !== "0";
  const isDown = change && String(change).startsWith("-");
  return (
    <div className="p-5 rounded-2xl" style={{
      background: "linear-gradient(135deg, rgba(6,182,212,0.05) 0%, rgba(15,23,42,0.6) 100%)",
      border: "1px solid rgba(6,182,212,0.15)",
      boxShadow: "0 4px 24px rgba(0,0,0,0.3)",
    }}>
      <p className="text-[11px] text-slate-500 uppercase tracking-widest mb-3 font-medium">{card.title}</p>
      <p className="text-3xl font-bold font-mono mb-2" style={{ color }}>{value}</p>
      {change && (
        <div className="flex items-center gap-1.5">
          <span className="text-xs font-bold" style={{ color: isUp ? "#10b981" : isDown ? "#f43f5e" : "#94a3b8" }}>
            {isUp ? "\\u25B2" : isDown ? "\\u25BC" : "\\u2014"} {String(change).replace(/[+%]/g, "")}%
          </span>
        </div>
      )}
    </div>
  );
}

function ChartCard({ card }: { card: CardItem }) {
  const option = (card.data?.option as EChartsOption | undefined) || (card.data as EChartsOption | undefined);
  if (!option) {
    return (
      <div className="p-8 flex items-center justify-center rounded-2xl" style={{
        background: "rgba(15,23,42,0.4)",
        border: "1px solid rgba(34,211,238,0.08)",
        color: "#475569",
      }}>
        <p className="text-xs">图表数据缺失</p>
      </div>
    );
  }
  const chartOpt: EChartsOption = {
    ...option,
    backgroundColor: "transparent",
    toolbox: {
      show: true, right: 12, top: 8,
      feature: {
        saveAsImage: { title: "保存图片", backgroundColor: "#0a1628" },
        restore: { title: "还原" },
      },
      iconStyle: { borderColor: "#475569" },
    },
  };
  return (
    <div className="p-4 rounded-2xl" style={{
      background: "rgba(15,23,42,0.6)",
      border: "1px solid rgba(34,211,238,0.1)",
      boxShadow: "0 4px 24px rgba(0,0,0,0.2)",
    }}>
      <h3 className="text-sm font-semibold text-cyan-400 mb-3">{card.title}</h3>
      <EChartView option={chartOpt} height={getChartHeight(card.size)} />
    </div>
  );
}

function TableCard({ card }: { card: CardItem }) {
  const d = card.data as Record<string, unknown>;
  const columns = d?.columns as string[] | undefined;
  const rows = d?.rows as unknown[][] | undefined;
  if (!columns || !rows || rows.length === 0) {
    return (
      <div className="p-8 flex items-center justify-center rounded-2xl" style={{
        background: "rgba(15,23,42,0.4)",
        border: "1px solid rgba(34,211,238,0.08)",
        color: "#475569",
      }}>
        <p className="text-xs">表格数据为空</p>
      </div>
    );
  }
  return (
    <div className="p-4 rounded-2xl" style={{
      background: "rgba(15,23,42,0.6)",
      border: "1px solid rgba(34,211,238,0.1)",
      boxShadow: "0 4px 24px rgba(0,0,0,0.2)",
    }}>
      <h3 className="text-sm font-semibold text-violet-400 mb-3">{card.title}</h3>
      <div style={{ overflow: "auto", maxHeight: getChartHeight(card.size) - 40 }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11 }}>
          <thead>
            <tr style={{ background: "rgba(34,211,238,0.08)" }}>
              {columns.map((col, i) => (
                <th key={i} style={{ padding: "8px 12px", textAlign: "left", color: "#94a3b8", fontSize: 10, borderBottom: "1px solid rgba(34,211,238,0.15)", fontWeight: 600 }}>{col}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, 30).map((row, ri) => (
              <tr key={ri} style={ri % 2 === 0 ? { background: "rgba(15,23,42,0.3)" } : undefined}>
                {(row as unknown[]).map((cell, ci) => (
                  <td key={ci} style={{ padding: "6px 12px", color: "#cbd5e1", borderBottom: "1px solid rgba(34,211,238,0.04)" }}>
                    {formatCellValue(typeof cell === "object" && cell !== null && "value" in cell ? (cell as any).value : cell)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function InsightCard({ card }: { card: CardItem }) {
  const d = card.data as Record<string, unknown>;
  const text = d?.text as string || card.title;
  const isHint = d?.is_hint;
  const isConclusion = d?.is_conclusion;
  if (isHint) {
    return (
      <div className="p-4 rounded-2xl" style={{
        background: "rgba(100,116,139,0.08)",
        border: "1px solid rgba(100,116,139,0.2)",
      }}>
        <p className="text-xs text-slate-500">{String(text)}</p>
      </div>
    );
  }
  return (
    <div className="p-4 rounded-2xl" style={{
      background: isConclusion ? "rgba(139,92,246,0.08)" : "rgba(34,211,238,0.05)",
      border: "1px solid " + (isConclusion ? "rgba(139,92,246,0.2)" : "rgba(34,211,238,0.15)"),
    }}>
      <p className="text-xs text-slate-300 leading-relaxed">{String(text)}</p>
    </div>
  );
}

function WarningCard({ card }: { card: CardItem }) {
  const d = card.data as Record<string, unknown>;
  const text = d?.text || d?.message || card.title;
  return (
    <div className="p-4 rounded-2xl" style={{
      background: "rgba(245,158,11,0.06)",
      border: "1px solid rgba(245,158,11,0.25)",
    }}>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-sm">{"\\u26A0\\uFE0F"}</span>
        <span className="text-xs font-semibold text-amber-400">预警</span>
      </div>
      <p className="text-xs text-slate-300">{String(text)}</p>
    </div>
  );
}

function FallbackCard({ card }: { card: CardItem }) {
  const d = card.data as Record<string, unknown>;
  const hint = d?.hint as string || "当前分析未完成，建议补充数据";
  return (
    <div className="p-4 rounded-2xl" style={{
      background: "rgba(245,158,11,0.04)",
      border: "1px dashed rgba(245,158,11,0.3)",
    }}>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs px-2 py-0.5 rounded bg-amber-500/20 text-amber-400 text-[10px] font-semibold">待补充</span>
        <span className="text-xs text-slate-500">{card.title}</span>
      </div>
      <p className="text-xs text-slate-400">{hint}</p>
      {card.fallback_chain && card.fallback_chain.length > 0 && (
        <div className="mt-3 space-y-1">
          <p className="text-[10px] text-slate-600">建议替代方案：</p>
          {card.fallback_chain.map((fc, i) => (
            <p key={i} className="text-[10px] text-slate-500">{"\\u2022"} {String(fc.hint || JSON.stringify(fc))}</p>
          ))}
        </div>
      )}
    </div>
  );
}

function CardRenderer({ card }: { card: CardItem }) {
  const renderBody = () => {
    switch (card.type) {
      case "kpi": return <KPICard card={card} />;
      case "chart": return <ChartCard card={card} />;
      case "table": return <TableCard card={card} />;
      case "insight": return <InsightCard card={card} />;
      case "warning": return <WarningCard card={card} />;
      case "fallback": return <FallbackCard card={card} />;
      default: return <FallbackCard card={card} />;
    }
  };
  const minHeight: Record<string, number> = { xl: 300, l: 240, m: 180, s: 120 };
  return (
    <div className="transition-all duration-200 hover:scale-[1.01] cursor-pointer" style={{
      minHeight: minHeight[card.size] || 120,
    }}>
      {renderBody()}
    </div>
  );
}

function getColumns(): number {
  if (typeof window !== "undefined") {
    if (window.innerWidth >= 1600) return 4;
    if (window.innerWidth >= 1200) return 3;
  }
  return 2;
}

function calcSpan(size: string, cols: number): number {
  switch (size) {
    case "xl": return cols;
    case "l": return Math.ceil(cols / 2);
    case "m": return Math.max(1, Math.floor(cols / 2));
    default: return 1;
  }
}

export default function CardGrid({ cards, meta, onCardClick }: Props) {
  const cols = useMemo(() => getColumns(), []);
  const sortedCards = useMemo(() => [...cards].sort((a, b) => b.score - a.score), [cards]);
  const layoutCards = useMemo(() => sortedCards.map(card => ({ ...card, span: calcSpan(card.size, cols) })), [sortedCards, cols]);

  if (cards.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-slate-500">
        <div className="text-3xl mb-3">{"📊"}</div>
        <p className="text-sm font-medium text-slate-400 mb-1">暂无分析卡片</p>
        <p className="text-xs text-slate-600">请先在「数据洞察」页面生成分析并保存</p>
      </div>
    );
  }

  return (
    <div className="p-5">
      {meta && (
        <div className="flex items-center gap-6 mb-5 px-1">
          <span className="text-[10px] text-slate-500 tracking-wider">
            共 <span className="text-cyan-400 font-mono font-semibold">{meta.total_cards}</span> 张卡片
          </span>
          <span className="text-[10px] text-slate-500 tracking-wider">
            洞察强度 <span className="text-violet-400 font-mono font-semibold">{meta.insight_strength}</span>
          </span>
          <span className="text-[10px] text-slate-500 tracking-wider">
            数据质量 <span className="text-emerald-400 font-mono font-semibold">{meta.data_quality}</span>
          </span>
        </div>
      )}
      <div className="grid gap-4" style={{ gridTemplateColumns: "repeat(" + cols + ", 1fr)" }}>
        {layoutCards.map((card) => (
          <CardRenderer key={card.id} card={card} />
        ))}
      </div>
    </div>
  );
}