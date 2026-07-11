/**
 * Border.ts —— 边框与圆角规范
 */

import { Palette } from './Palette';

export const Border = {
  default: Palette.border,
  strong: Palette.borderStrong,
  radius: {
    sm: '8px',
    md: '12px',
    lg: '16px',
    xl: '20px',
  },
} as const;

export type BorderToken = typeof Border;
