/* DataTable - 数据表格组件
   ★ 颜色统一来自 theme/（Galaxy Executive Dashboard） */
import React, { useMemo } from 'react';
import { theme } from '../theme';

const P = theme.palette;

interface Props {
  data: Record<string, unknown>[];
  maxHeight?: string;
}

export default function DataTable({ data, maxHeight = '500px' }: Props) {
  const columns = useMemo(() => {
    if (!data.length) return [];
    return Object.keys(data[0]);
  }, [data]);

  if (!data.length) {
    return (
      <div className="glass-card p-8 text-center text-slate-500">
        暂无数据
      </div>
    );
  }

  return (
    <div className="glass-card overflow-hidden">
      <div style={{ maxHeight }} className="overflow-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 z-10">
            <tr style={{ background: `${P.primary}1f` }}>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">#</th>
              {columns.map((col) => (
                <th key={col} className="px-4 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, i) => (
              <tr
                key={i}
                className="border-t border-white/[0.04] hover:bg-[#8B5CF6]/[0.06] transition-colors"
              >
                <td className="px-4 py-2.5 text-xs text-slate-500">{i + 1}</td>
                {columns.map((col) => (
                  <td key={col} className="px-4 py-2.5 text-slate-300">
                    {formatValue(row[col])}
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

function formatValue(val: unknown): string {
  if (val === null || val === undefined) return '-';
  if (typeof val === 'number') {
    if (!Number.isFinite(val)) return '-';
    if (Number.isInteger(val)) return val.toLocaleString();
    return val.toFixed(4);
  }
  const str = String(val);
  // 检测 ISO 日期时间格式并美化显示（如 2024-01-15T00:00:00 → 2024-01-15）
  const isoDateMatch = str.match(/^(\d{4}-\d{2}-\d{2})T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/);
  if (isoDateMatch) return isoDateMatch[1];
  // 检测完整 ISO 格式带时区
  const isoFullMatch = str.match(/^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})/);
  if (isoFullMatch) return isoFullMatch[1].replace('T', ' ');
  return str;
}
