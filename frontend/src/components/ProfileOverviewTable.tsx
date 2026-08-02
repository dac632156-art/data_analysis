export interface OverviewCell {
  value?: unknown;
  rank?: number;
  direction?: string;   // good(绿)/equal(黄)/bad(红)/neutral(不染色)
  cell_type?: string;   // number/percentage/category/neutral
  highlight?: boolean;  // 该行（该类用户）人均净毛利最高的地区高亮
  count?: number;       // 该组合客户数，用于副标防误导
}

const DIR_STYLE: Record<string, { bar: string; text: string }> = {
  good: { bar: 'rgba(52,211,153,0.18)', text: '#6EE7B7' },
  equal: { bar: 'rgba(251,191,36,0.18)', text: '#FCD34D' },
  bad: { bar: 'rgba(251,113,133,0.18)', text: '#FDA4AF' },
  neutral: { bar: 'rgba(148,163,184,0.07)', text: '#CBD5E1' },
};

const pct = (v: unknown) =>
  typeof v === 'number' ? `${(v * 100).toFixed(1)}%` : (v ?? '—');

export function Cell({ cell }: { cell: OverviewCell }) {
  const { value, rank = 0, direction = 'neutral', cell_type = 'text', highlight = false, count } = cell;
  const c = DIR_STYLE[direction] || DIR_STYLE.neutral;
  const widthPct = `${Math.max(0, Math.min(1, rank)) * 100}%`;

  // 高亮：该行（该类用户）人均净毛利最高的地区 → 银河紫半透明底 + 描边 + 加粗白字
  const highlightStyle = highlight
    ? {
        background: 'rgba(139,92,246,0.22)',
        boxShadow: 'inset 0 0 0 1px rgba(139,92,246,0.6)',
        color: '#F8FAFC',
        fontWeight: 700,
      }
    : {};

  // 客户数副标：防小样本误导（n=xx 让决策者一眼看数值可信度）
  const countSub = typeof count === 'number' ? (
    <span style={{ fontSize: 9, color: highlight ? 'rgba(248,250,252,0.7)' : '#64748B', marginLeft: 4 }}>
      n={count}
    </span>
  ) : null;

  if (cell_type === 'category') {
    return (
      <td className="px-3 py-2 relative">
        <span
          style={{
            background: 'rgba(56,189,248,0.15)',
            color: '#7DD3FC',
            padding: '2px 10px',
            borderRadius: '9999px',
            fontSize: '11px',
            whiteSpace: 'nowrap',
          }}
        >
          {value ?? '—'}
        </span>
      </td>
    );
  }

  if (cell_type === 'percentage' || cell_type === 'number') {
    const display = cell_type === 'percentage' ? pct(value) : (value === null || value === undefined ? '—' : String(value));
    return (
      <td className="px-3 py-2 relative" style={{ ...highlightStyle, color: highlight ? '#F8FAFC' : c.text }}>
        <div
          style={{
            position: 'absolute',
            left: 0,
            top: 0,
            bottom: 0,
            width: widthPct,
            background: c.bar,
            pointerEvents: 'none',
          }}
        />
        <span style={{ position: 'relative' }}>{display}{countSub}</span>
      </td>
    );
  }

  // neutral / text
  return (
    <td className="px-3 py-2 text-slate-300 relative" style={highlightStyle}>
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: 0,
          bottom: 0,
          width: widthPct,
          background: c.bar,
          pointerEvents: 'none',
        }}
      />
      <span style={{ position: 'relative' }}>{value ?? '—'}{countSub}</span>
    </td>
  );
}

// 业务动作建议：纯前端映射（后端只下发 direction 颜色元数据，不计算动作）。
const ACTION_RULES: Record<string, (dirs: Record<string, string>) => string> = {
  user_seg: (d) =>
    (d['消费金额(元)'] === 'good' && d['购买间隔(天)'] === 'good') ? '重点维护'
    : (d['消费金额(元)'] === 'good' && d['购买间隔(天)'] !== 'good') ? '发券召回'
    : (d['消费金额(元)'] !== 'good' && d['购买间隔(天)'] !== 'good') ? '控制营销投入'
    : '常规运营',
  sku_seg: (d) =>
    (d['毛利率(%)'] === 'good' && d['购买数量(件)'] === 'bad') ? '促销清库'
    : (d['毛利率(%)'] === 'bad' && d['购买数量(件)'] === 'good') ? '捆绑拉利'
    : '常规运营',
  geo_seg: (d) =>
    (d['地域ARPU(元)'] === 'good') ? '重点铺货'
    : (d['地域客单价(元)'] === 'bad') ? '调包邮门槛'
    : '常规运营',
  churn_seg: (d) => {
    const highRisk = d['静默天数(天)'] === 'bad' || d['投诉率(%)'] === 'bad';
    if (!highRisk) return '常规监控';
    return d['历史消费(元)'] === 'good' ? '优先挽留' : '放弃投入';
  },
  activity_seg: (d) =>
    (d['在站时长(分钟)'] === 'good') ? '夜间档推送' : '常规运营',
  category_seg: (d) =>
    (d['跨类目广度(类)'] === 'good') ? '多类目交叉销售'
    : (d['购买数量(件)'] === 'good') ? '推高购买品类周边'
    : '常规运营',
};

export default function ProfileOverviewTable({
  chart,
  hideTitle,
}: {
  chart: {
    title?: string;
    table_data?: { rows: OverviewCell[][]; columns: string[] };
    chart_config?: { blocks?: { title: string; keys: string[] }[]; module?: string; feature_cols?: string[] };
  };
  hideTitle?: boolean;
}) {
  const cfg = chart.chart_config || {};
  const blocks = cfg.blocks || [];
  const columns: string[] = chart.table_data?.columns || [];
  const rows: OverviewCell[][] = chart.table_data?.rows || [];
  const colIndex = new Map(columns.map((c, i) => [c, i]));
  // 业务动作建议列：前端按 direction 映射（后端仅下发颜色元数据，不计算动作）
  const actIdx = columns.indexOf('业务动作建议');
  const rule = cfg.module ? ACTION_RULES[cfg.module] : undefined;
  const displayRows: OverviewCell[][] = (actIdx >= 0 && rule)
    ? rows.map((row) => {
        const dirs: Record<string, string> = {};
        (cfg.feature_cols || []).forEach((f: string) => {
          const idx = colIndex.get(f);
          dirs[f] = (idx != null && row[idx]) ? String((row[idx] as OverviewCell).direction || 'equal') : 'equal';
        });
        const action = rule(dirs) || '';
        const newRow = [...row] as OverviewCell[];
        newRow[actIdx] = { ...(newRow[actIdx] || {}), value: action, cell_type: 'category' } as OverviewCell;
        return newRow;
      })
    : rows;

  return (
    <div
      style={{
        padding: '12px',
        background: 'rgba(10,14,30,0.95)',
        borderRadius: '8px',
        maxHeight: '520px',
        overflow: 'auto',
      }}
    >
      {!hideTitle && chart.title && (
        <h3 className="text-sm font-semibold text-[#7DD3FC] mb-3">{chart.title}</h3>
      )}
      <table className="w-full text-xs" style={{ borderCollapse: 'separate', borderSpacing: '0' }}>
        <thead className="sticky top-0 z-10">
          {/* 区块表头 */}
          <tr>
            {blocks.map((b) => (
              <th
                key={b.title}
                colSpan={b.keys.length}
                className="px-2 py-1.5 text-center text-[11px] font-semibold text-[#A78BFA] bg-[#8B5CF6]/10 border-b border-[#8B5CF6]/20"
              >
                {b.title}
              </th>
            ))}
          </tr>
          {/* 列名表头 */}
          <tr style={{ background: 'rgba(125,211,252,0.08)' }}>
            {columns.map((col) => (
              <th
                key={col}
                className="px-3 py-2 text-left text-slate-400 font-semibold whitespace-nowrap"
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {displayRows.map((row, ri) => (
            <tr
              key={ri}
              style={{
                borderBottom: '1px solid rgba(125,211,252,0.04)',
                background: ri % 2 === 0 ? 'rgba(15,23,42,0.5)' : undefined,
              }}
            >
              {columns.map((col) => {
                const cell = row[colIndex.get(col) as number] || { value: null };
                return <Cell key={col} cell={cell} />;
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
