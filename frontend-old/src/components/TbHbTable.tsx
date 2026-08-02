/* TbHbTable - 同环比规范表格
 *
 * 结构：月份 | 上年值 | 本年值 | 同比增长率 | 环比增长率
 * 规则：
 *   增长 → 🔺 +xx%  红色(rgb(239,68,68))
 *   下降 → 🔻 -xx%  绿色(rgb(34,197,94))
 *   持平 → ➖ 0%   灰色(rgb(156,163,175))
 *   第一行环比 → "--"
 *   增长率保留整数或2位小数
 */

import React from 'react';

export interface TbHbRow {
  month?: number;
  period: string;
  /** 上年同期值 */
  '上年值': number | null;
  /** 本年值 */
  '本年值': number | null;
  /** 同比增长率（小数，如 0.263 表示 26.3%） */
  '同比增长率': number | null;
  /** 环比增长率（小数，如 -0.47 表示 -47%） */
  '环比增长率': number | null;
}

interface TbHbTableProps {
  data: TbHbRow[];
  valueColumn: string;       // 数值列名，如"销售金额"
  currentYear: string;       // 当前年份，如 "2025"
  previousYear: string | null; // 上年年份，如 "2024"
  hasYoY: boolean;           // 是否有同比数据
  maxHeight?: string;
}

/** 格式化金额（大数以万/亿为单位） */
function formatValue(v: number | null): string {
  if (v === null || v === undefined) return '--';
  if (Math.abs(v) >= 100_000_000) return `${(v / 100_000_000).toFixed(2)}亿`;
  if (Math.abs(v) >= 10_000) return `${(v / 10_000).toFixed(2)}万`;
  return v.toLocaleString('zh-CN', { maximumFractionDigits: 2 });
}

/** 格式化增长率：带箭头和颜色 */
function formatRate(rate: number | null, isFirstRowMoM = false): { html: string; color: string } {
  if (rate === null || rate === undefined) {
    return { html: '--', color: '#9ca3af' };
  }
  // 第一行环比显示 --
  if (isFirstRowMoM) {
    return { html: '--', color: '#9ca3af' };
  }

  // 格式化：整数或2位小数
  const pct = rate * 100;
  const formatted = Number.isInteger(pct) ? `${pct}%` : `${pct.toFixed(2)}%`;

  if (rate > 0.001) {       // 增长（>0.1%）
    return { html: `🔺 +${formatted}`, color: '#FB7185' };
  } else if (rate < -0.001) { // 下降（<-0.1%）
    return { html: `🔻 ${formatted}`, color: '#22c55e' };
  } else {                  // 持平（±0.1%以内）
    return { html: `➖ 0%`, color: '#9ca3af' };
  }
}

/** 月份名称映射 */
const MONTH_NAMES = ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'];

export default function TbHbTable({ data, valueColumn, currentYear, previousYear, hasYoY, maxHeight = '500px' }: TbHbTableProps) {
  if (!data || data.length === 0) {
    return (
      <div className="text-center text-slate-500 py-8 text-sm">
        暂无同环比数据
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* 标题行 */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-slate-300">
            📋 {valueColumn} · 同环比分析
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            {hasYoY
              ? `${previousYear}年 vs ${currentYear}年 月度对比`
              : `${currentYear}年 月度环比`
            }
          </p>
        </div>
        <span className="text-xs text-slate-500">共 {data.length} 个月</span>
      </div>

      {/* 表格 */}
      <div
        className="overflow-y-auto rounded-lg border border-white/[0.08]"
        style={{ maxHeight, scrollbarWidth: 'thin', scrollbarColor: 'rgba(139,92,246,0.3) transparent' }}
      >
        <table className="w-full text-xs text-slate-300">
          {/* 表头 */}
          <thead className="sticky top-0 z-10">
            <tr className="bg-[#1a1a2e]">
              <th className="py-2.5 px-3 text-left font-semibold text-slate-400 border-b border-white/[0.08]">
                月份
              </th>
              {hasYoY && (
                <th className="py-2.5 px-3 text-right font-semibold text-slate-400 border-b border-white/[0.08]">
                  {previousYear}年
                </th>
              )}
              <th className="py-2.5 px-3 text-right font-semibold text-[#f8fafc] border-b border-white/[0.08]">
                {currentYear}年
              </th>
              {hasYoY && (
                <th className="py-2.5 px-3 text-right font-semibold text-slate-400 border-b border-white/[0.08]">
                  同比增长率
                </th>
              )}
              <th className="py-2.5 px-3 text-right font-semibold text-slate-400 border-b border-white/[0.08]">
                环比增长率
              </th>
            </tr>
          </thead>

          {/* 表体 */}
          <tbody>
            {data.map((row, i) => {
              const yoyFmt = formatRate(row['同比增长率']);
              const momFmt = formatRate(row['环比增长率'], i === 0);
              const monthLabel = row.month ? MONTH_NAMES[row.month - 1] || row.period : row.period;
              const isEven = i % 2 === 0;

              return (
                <tr
                  key={row.period}
                  className={`border-b border-white/[0.04] transition-colors ${
                    isEven ? 'bg-white/[0.02]' : 'bg-transparent'
                  } hover:bg-white/[0.05]`}
                >
                  {/* 月份 */}
                  <td className="py-2.5 px-3 text-slate-300 font-medium whitespace-nowrap">
                    {monthLabel}
                  </td>

                  {/* 上年值 */}
                  {hasYoY && (
                    <td className="py-2.5 px-3 text-right text-slate-400 font-mono tabular-nums whitespace-nowrap">
                      {formatValue(row['上年值'])}
                    </td>
                  )}

                  {/* 本年值 */}
                  <td className={`py-2.5 px-3 text-right font-semibold font-mono tabular-nums whitespace-nowrap ${hasYoY ? 'text-[#f8fafc]' : 'text-[#f8fafc]'}`}>
                    {formatValue(row['本年值'])}
                  </td>

                  {/* 同比增长率 */}
                  {hasYoY && (
                    <td
                      className="py-2.5 px-3 text-right font-mono tabular-nums whitespace-nowrap"
                      style={{ color: yoyFmt.color }}
                    >
                      {yoyFmt.html}
                    </td>
                  )}

                  {/* 环比增长率 */}
                  <td
                    className="py-2.5 px-3 text-right font-mono tabular-nums whitespace-nowrap"
                    style={{ color: momFmt.color }}
                  >
                    {momFmt.html}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* 图例 */}
      <div className="flex items-center gap-4 text-[11px] text-slate-500">
        <span style={{ color: '#FB7185' }}>🔺 增长</span>
        <span style={{ color: '#22c55e' }}>🔻 下降</span>
        <span style={{ color: '#9ca3af' }}>➖ 持平 / 无数据</span>
      </div>
    </div>
  );
}
