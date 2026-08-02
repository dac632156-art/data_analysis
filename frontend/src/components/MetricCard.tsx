/* MetricCard - 指标卡片（KPI 脉冲发光）
   ★ 颜色统一来自 theme/（Galaxy Executive Dashboard） */
import React from 'react';
import { theme } from '../theme';

const P = theme.palette;

interface Props {
  title: string;
  value: string | number;
  icon?: string;
  color?: string;
  className?: string;
}

const iconMap: Record<string, string> = {
  'database': '📊',
  'columns': '📋',
  'average': '📈',
  'sum': '💰',
  'categories': '🏷️',
  'target': '🎯',
};

export default function MetricCard({ title, value, icon, color = P.primary, className }: Props) {
  const emoji = icon ? (iconMap[icon] || '📊') : '📊';

  return (
    <div className={`${className ?? 'glass-card'} p-4 flex items-start gap-4`}>
      <div
        className="w-10 h-10 rounded-lg flex items-center justify-center text-lg flex-shrink-0"
        style={{ background: `${color}20`, color }}
      >
        {emoji}
      </div>
      <div className="min-w-0">
        <p className="text-xs text-slate-500 uppercase tracking-wider mb-0.5">{title}</p>
        <p className="kpi-glow text-xl font-bold truncate" style={{ color: 'var(--text-primary)' }}>{value}</p>
      </div>
    </div>
  );
}
