/* KPICards - 通用 KPI 卡片组件（带涨跌箭头） */
import React from 'react';

export interface KPIItem {
  title: string;
  value: string | number;
  icon?: string;
  color?: string;
  unit?: string;
  change?: number | null;  // 百分比变化率，如 12.5 或 -3.2
  trend?: 'up' | 'down' | 'flat';  // 涨/跌/平
}

interface Props {
  kpis: KPIItem[];
  maxCount?: number;
  style?: React.CSSProperties;
}

/** 格式化变化率 */
function formatChange(change: number | null | undefined): string {
  if (change === null || change === undefined) return '';
  const abs = Math.abs(change);
  return abs >= 100 ? `${abs.toFixed(0)}%` : `${abs.toFixed(1)}%`;
}

export default function KPICards({ kpis, maxCount = 6, style }: Props) {
  const display = kpis.slice(0, maxCount);
  if (display.length === 0) return null;

  return (
    <div className="flex flex-wrap justify-center gap-3" style={style}>
      {display.map((kpi, i) => {
        const color = kpi.color || '#38BDF8';
        const isUp = kpi.trend === 'up';
        const isDown = kpi.trend === 'down';
        const hasTrend = kpi.trend !== 'flat' && kpi.change != null && kpi.change !== 0;

        return (
          <div
            key={i}
            className="relative flex flex-col items-center rounded-xl p-3 min-w-[120px] flex-1 max-w-[180px]"
            style={{
              // ★ 浅色玻璃：白玻璃 + 主题色淡边 + backdrop blur
              background: 'rgba(255,255,255,0.50)',
              border: `1px solid ${color}40`,
              boxShadow: `0 4px 16px ${color}18`,
              backdropFilter: 'blur(12px)',
              WebkitBackdropFilter: 'blur(12px)',
            }}
          >
            {/* 图标 */}
            {kpi.icon && <span className="text-lg mb-1">{kpi.icon}</span>}

            {/* 数值（深色高对比，去掉重辉光） */}
            <div className="text-lg font-bold" style={{ color: '#0f172a' }}>
              {kpi.value}
            </div>

            {/* 涨跌指示 */}
            {hasTrend && (
              <div className="flex items-center gap-1 mt-1">
                <span
                  className="text-xs font-semibold"
                  style={{ color: isUp ? '#059669' : '#dc2626' }}
                >
                  {isUp ? '↑' : '↓'} {formatChange(kpi.change)}
                </span>
              </div>
            )}

            {/* 标题 */}
            <div className="text-[10px] text-slate-600 mt-1 text-center leading-tight font-medium">
              {kpi.title}
            </div>
          </div>
        );
      })}
    </div>
  );
}
