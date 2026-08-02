/**
 * theme/index.ts —— 统一导出入口
 *
 * 所有模块应从这里（或细分文件）导入颜色，禁止写死。
 */

export { theme, themes, getTheme, galaxyExecutiveTheme } from './Theme';
export type { Theme } from './Theme';
export { Palette, withAlpha } from './Palette';
export type { PaletteToken } from './Palette';
export { SemanticColor } from './SemanticColor';
export type { SemanticColorToken } from './SemanticColor';
export { ChartStyle } from './ChartStyle';
export type { ChartStyleToken } from './ChartStyle';
export { Typography } from './Typography';
export type { TypographyToken } from './Typography';
export { Surface } from './Surface';
export type { SurfaceToken } from './Surface';
export { Border } from './Border';
export type { BorderToken } from './Border';
export { Shadow } from './Shadow';
export type { ShadowToken } from './Shadow';
export { Animation } from './Animation';
export type { AnimationToken } from './Animation';
