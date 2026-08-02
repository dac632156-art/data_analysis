/**
 * Theme.ts —— 主题聚合器（Galaxy AI Analytics）
 *
 * 把 Palette / SemanticColor / ChartStyle / Typography / Surface / Border / Shadow / Animation
 * 聚合为完整的 Theme 对象，作为整个项目唯一的颜色与样式来源。
 *
 * 扩展性：未来新增 Light / Finance / Operations 主题，只需在 `themes` 注册表中
 * 新增一个 Theme 对象，任何图表 / 渲染器代码都无需改动。
 */

import { Palette, PaletteToken } from './Palette';
import { SemanticColor, SemanticColorToken } from './SemanticColor';
import { ChartStyle, ChartStyleToken } from './ChartStyle';
import { Typography, TypographyToken } from './Typography';
import { Surface, SurfaceToken } from './Surface';
import { Border, BorderToken } from './Border';
import { Shadow, ShadowToken } from './Shadow';
import { Animation, AnimationToken } from './Animation';

export interface Theme {
  name: string;
  palette: PaletteToken;
  semantic: SemanticColorToken;
  chart: ChartStyleToken;
  typography: TypographyToken;
  surface: SurfaceToken;
  border: BorderToken;
  shadow: ShadowToken;
  animation: AnimationToken;
}

// ============================================================
// Galaxy AI Analytics（当前默认主题）
// ============================================================
export const galaxyExecutiveTheme: Theme = {
  name: 'galaxy',
  palette: Palette,
  semantic: SemanticColor,
  chart: ChartStyle,
  typography: Typography,
  surface: Surface,
  border: Border,
  shadow: Shadow,
  animation: Animation,
};

// ============================================================
// 主题注册表（未来新增主题只需在此注册，无需改动任何图表代码）
// ============================================================
export const themes: Record<string, Theme> = {
  galaxy: galaxyExecutiveTheme,
  // light: lightTheme,      // 未来
  // finance: financeTheme,  // 未来
  // operations: opsTheme,   // 未来
};

/** 按名称获取主题（未知名称回退到 galaxy） */
export function getTheme(name: string = 'galaxy'): Theme {
  return themes[name] ?? galaxyExecutiveTheme;
}

/**
 * 默认激活主题 = Single Source of Truth。
 * 非 React 模块（EChartView / 各种组件）直接 import 此对象即可
 * 读取统一颜色，无需 Context。
 */
export const theme: Theme = galaxyExecutiveTheme;

export default theme;
