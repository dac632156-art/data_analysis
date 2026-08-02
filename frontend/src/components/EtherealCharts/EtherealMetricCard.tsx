/**
 * 仙气指标小卡片（React 版）
 * ★ 严格移植自「可视化模板库/同期群分析/小卡片组件.js」，逻辑未篡改
 * 唯一改动：数据由 props 传入（不再操作 DOM innerHTML）。
 */
import React from 'react';

interface Props {
  metricData?: { title?: string; label?: string; value?: number | string; change?: number | string; unit?: string };
}

export const EtherealMetricCard: React.FC<Props> = ({ metricData }) => {
  const m = metricData || {};
  const title = m.title || m.label || '核心指标';
  const val = m.value !== undefined ? m.value : '--';
  const change = m.change !== undefined ? m.change : '+0.0%';

  const isPositive = !String(change).includes('-');
  const changeColor = isPositive ? '#10B981' : '#EF4444';

  let displayVal: string = String(val);
  if (!isNaN(Number(val)) && val !== '') {
    const num = Number(val);
    if (m.unit === 'ratio' || title.toLowerCase().includes('rate') || title.includes('留存')) {
      displayVal = (num * 100).toFixed(1) + '%';
    } else {
      displayVal = num.toLocaleString('en-US', { maximumFractionDigits: 2 });
    }
  }

  let finalChange = String(change).trim();
  if (isPositive && !finalChange.includes('+')) finalChange = '+' + finalChange;
  if (!finalChange.includes('%')) finalChange += '%';

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        background: '#FFFFFF',
        borderRadius: 20,
        padding: 24,
        boxShadow: '0 10px 25px -5px rgba(0,0,0,0.02), 0 0 0 1px rgba(226,232,240,0.6)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-end',
        position: 'relative',
        boxSizing: 'border-box',
      }}
    >
      <svg className="sparkle-icon" style={{ position: 'absolute', top: 20, right: 20, width: 24, height: 24 }} viewBox="0 0 24 24">
        <path d="M12 3 L13.5 9.5 L20 11 L13.5 12.5 L12 19 L10.5 12.5 L4 11 L10.5 9.5 Z" fill="#C7D2FE" />
        <path d="M19 4 L19.5 6 L21.5 6.5 L19.5 7 L19 9 L18.5 7 L16.5 6.5 L18.5 6 Z" fill="#C7D2FE" />
      </svg>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, zIndex: 2 }}>
        <span style={{ fontSize: 15, color: '#475569', fontWeight: 600 }}>{title}</span>
        <span style={{ fontSize: 32, fontWeight: 800, color: '#0F172A', letterSpacing: '-0.5px', margin: '4px 0' }}>{displayVal}</span>
        <span style={{ fontSize: 14, fontWeight: 700, color: changeColor }}>{finalChange}</span>
      </div>
      <div style={{ width: 100, height: 45, zIndex: 1 }}>
        <svg width="100%" height="100%" viewBox="0 0 100 40" preserveAspectRatio="none">
          <defs>
            <linearGradient id="grad-card" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#F472B6" />
              <stop offset="100%" stopColor="#818CF8" />
            </linearGradient>
          </defs>
          <path d="M0 35 Q 15 25, 30 30 T 60 20 T 90 10 T 100 5 L 100 40 L 0 40 Z" fill="url(#grad-card)" opacity={0.15} />
          <path d="M0 35 Q 15 25, 30 30 T 60 20 T 90 10 T 100 5" fill="none" stroke="url(#grad-card)" strokeWidth={2.5} strokeLinecap="round" />
        </svg>
      </div>
    </div>
  );
};

export default EtherealMetricCard;
