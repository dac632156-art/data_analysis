/* DataTable - 数据表格组件
   ★ 统一改用「可视化模板库」风格的 EtherealTable 渲染（背景.png / 第1列胶囊 / 浅色毛玻璃）。
   对外契约保持不变：data: Record<string,unknown>[] + maxHeight。内部仅做「格式适配 + 滚动容器」。 */
import React, { useMemo } from 'react';
import EtherealTable from './EtherealCharts/EtherealTable';

interface Props {
  data: Record<string, unknown>[];
  maxHeight?: string;
}

/** 美化单元格显示（与旧版 DataTable 行为一致：ISO 日期规整、数字千分位） */
function formatValue(val: unknown): unknown {
  if (val === null || val === undefined) return '-';
  if (typeof val === 'number') {
    if (!Number.isFinite(val)) return '-';
    return val; // 数字原样传，EtherealTable 负责千分位/小数格式化
  }
  const str = String(val);
  const isoDateMatch = str.match(/^(\d{4}-\d{2}-\d{2})T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/);
  if (isoDateMatch) return isoDateMatch[1];
  const isoFullMatch = str.match(/^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})/);
  if (isoFullMatch) return isoFullMatch[1].replace('T', ' ');
  return str;
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

  // 适配为 EtherealTable 所需格式：rows 为纯值 dict 行，列名取自首行 key
  const rows = data.map((row) => {
    const r: Record<string, unknown> = {};
    for (const col of columns) r[col] = formatValue(row[col]);
    return r;
  });

  return (
    <div style={{ maxHeight, overflow: 'auto' }}>
      <EtherealTable
        chartNode={{ title: '数据预览', columns, rows }}
        showIndex
      />
    </div>
  );
}
