/**
 * Shadow.ts —— 阴影规范（柔和阴影）
 */

import { Palette, withAlpha } from './Palette';

export const Shadow = {
  none: 'none',
  /** 卡片静止阴影 */
  card: '0 2px 12px rgba(0,0,0,0.25)',
  /** 卡片 Hover 阴影 */
  cardHover: '0 8px 28px rgba(0,0,0,0.40)',
  /** 通用柔和阴影 */
  soft: '0 4px 24px rgba(0,0,0,0.35)',
  /** 主题紫辉光（用于强调 / 联动） */
  glow: `0 0 24px ${withAlpha(Palette.ai, 0.18)}`,
} as const;

export type ShadowToken = typeof Shadow;
