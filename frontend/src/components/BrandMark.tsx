import React from 'react';

interface BrandMarkProps {
  size?: number;
  shape?: 'circle' | 'rounded';
  className?: string;
}

/**
 * DataMind AI 统一品牌图形（与主页 Sidebar 内联硬编码 Logo 像素一致）。
 *
 * 视觉规格（从 Sidebar 0aa3cc1 复制）：
 *   - 径向渐变：circle at 30% 30%
 *     #a1c4fd 0% → #c2e9fb 30% → #ffc3a0 70% → #ffafbd 100%
 *   - 阴影：0 2px 8px rgba(0, 0, 0, 0.05)
 *   - 形状：circle（默认） / rounded（圆角胶囊，shape="rounded"）
 */
export default function BrandMark({
  size = 32,
  shape = 'circle',
  className,
}: BrandMarkProps) {
  const radius = shape === 'circle' ? '50%' : '35%';
  return (
    <div
      aria-label="DataMind AI"
      className={className}
      style={{
        width: size,
        height: size,
        borderRadius: radius,
        flexShrink: 0,
        background:
          'radial-gradient(circle at 30% 30%, #a1c4fd 0%, #c2e9fb 30%, #ffc3a0 70%, #ffafbd 100%)',
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.05)',
      }}
    />
  );
}
