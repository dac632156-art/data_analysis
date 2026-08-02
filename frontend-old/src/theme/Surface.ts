/**
 * Surface.ts —— 表面 / 背景层级
 */

import { Palette } from './Palette';

export const Surface = {
  /** 页面背景（深蓝星空） */
  pageBg: Palette.pageBg,
  /** 卡片表面 */
  card: Palette.card,
  /** 卡片 Hover 表面 */
  cardHover: Palette.cardHover,
  /** 区块头 / 表头 */
  header: Palette.header,
  /** 浮层 / 弹窗遮罩 */
  overlay: 'rgba(2,6,23,0.82)',
  /** Tooltip 背景（深空蓝卡片） */
  tooltip: Palette.card,
} as const;

export type SurfaceToken = typeof Surface;
