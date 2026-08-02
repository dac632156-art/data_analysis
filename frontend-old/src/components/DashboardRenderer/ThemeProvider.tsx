import React, { createContext, useContext, useMemo, useEffect } from 'react';
import type { DashboardTheme, DashboardThemeName } from '../../types/dashboard';
import { galaxyExecutiveTheme, Palette, withAlpha } from '../../theme';

/**
 * ThemeEngine —— 统一主题引擎
 *
 * 4 种专业主题：
 * - Professional Light：白色背景，蓝色强调
 * - Professional Dark：深色背景，紫色强调
 * - Business Blue：深蓝背景，天蓝强调
 * - Corporate Gray：深灰背景，灰色强调
 *
 * 统一控制：
 * - CSS 变量注入（:root）
 * - 字体
 * - 颜色
 * - 边框 / 阴影 / 圆角
 * - 卡片样式
 * - 动画时长
 */

// ★ Galaxy Executive Dashboard —— 整个项目唯一的 Theme 来源（theme/ 模块）。
//   所有主题名（light/dark/blue/gray）统一映射到 Galaxy Executive，
//   保证 Dashboard / Report / Insight / Chart 视觉完全一致。
//   未来新增 Light / Finance / Operations 主题：在 theme/ 的 themes 注册表扩展，
//   再在此构建一个对应的 DashboardTheme 即可，任何图表代码无需改动。
function buildGalaxyDashboardTheme(): DashboardTheme {
  const t = galaxyExecutiveTheme;
  return {
    name: 'dark',
    background: 'bg-[var(--db-bg)]',
    cardBg: 'bg-[var(--db-card-bg)]',
    cardBorder: 'border-[var(--db-card-border)]',
    text: 'text-[var(--db-text)]',
    textSecondary: 'text-[var(--db-text-secondary)]',
    accent: t.palette.primary,
    chartColors: [...t.chart.series],
    kpiGradient: 'from-[var(--db-accent)] to-[var(--db-accent-light)]',
    shadow: t.shadow.card,
    cssVars: {
      '--db-bg': t.surface.pageBg,
      '--db-card-bg': t.surface.card,
      '--db-card-border': t.border.default,
      '--db-text': t.palette.textPrimary,
      '--db-text-secondary': t.palette.textSecondary,
      '--db-accent': Palette.ai,
      '--db-accent-light': withAlpha(Palette.ai, 0.20),
      '--db-shadow': t.shadow.card,
      '--db-glow': t.shadow.glow,
    },
    fontFamily: t.typography.fontFamily,
    borderRadius: t.border.radius.md,
    cardPadding: '16px',
    animationDuration: t.animation.duration.base,
    chart: t.chart,
    palette: t.palette,
  };
}

const GALAXY = buildGalaxyDashboardTheme();

const THEMES: Record<DashboardThemeName, DashboardTheme> = {
  light: GALAXY,
  dark: GALAXY,
  blue: GALAXY,
  gray: GALAXY,
};

const ThemeContext = createContext<DashboardTheme>(THEMES.dark);

export function useDashboardTheme(): DashboardTheme {
  return useContext(ThemeContext);
}

/** 获取所有可用主题名 */
export function getAvailableThemes(): DashboardThemeName[] {
  return Object.keys(THEMES) as DashboardThemeName[];
}

export const DashboardThemeProvider: React.FC<{
  theme?: DashboardThemeName;
  darkMode?: boolean;
  children: React.ReactNode;
}> = ({ theme = 'dark', darkMode = true, children }) => {
  const active = useMemo(() => {
    const base = THEMES[theme] || THEMES.dark;
    if (!darkMode && theme === 'dark') return THEMES.light;
    return base;
  }, [theme, darkMode]);

  // 注入 CSS 变量到 ThemeProvider 容器（scoped，不污染全局 :root）
  useEffect(() => {
    const el = document.getElementById('dashboard-theme-root');
    if (!el) return;
    for (const [key, value] of Object.entries(active.cssVars)) {
      el.style.setProperty(key, value);
    }
    el.style.setProperty('--db-font-family', active.fontFamily);
    el.style.setProperty('--db-border-radius', active.borderRadius);
    el.style.setProperty('--db-card-padding', active.cardPadding);
    el.style.setProperty('--db-animation-duration', `${active.animationDuration}ms`);
  }, [active]);

  return (
    <ThemeContext.Provider value={active}>
      <div id="dashboard-theme-root"
        className="h-full min-h-screen transition-colors duration-500"
        style={{
          fontFamily: active.fontFamily,
          backgroundColor: 'var(--db-bg)',
          color: 'var(--db-text)',
          '--db-animation-duration': `${active.animationDuration}ms`,
        } as React.CSSProperties}
      >
        {/* 全局动画 CSS */}
        <style>{`
          /* Dashboard Animation Engine */
          @keyframes dbFadeIn {
            from { opacity: 0; transform: translateY(8px); }
            to { opacity: 1; transform: translateY(0); }
          }
          @keyframes dbSlideUp {
            from { opacity: 0; transform: translateY(16px); }
            to { opacity: 1; transform: translateY(0); }
          }
          @keyframes dbScaleIn {
            from { opacity: 0; transform: scale(0.95); }
            to { opacity: 1; transform: scale(1); }
          }
          @keyframes dbProgressive {
            from { opacity: 0; clip-path: inset(0 100% 0 0); }
            to { opacity: 1; clip-path: inset(0 0 0 0); }
          }
          .animate-db-fade-in {
            animation: dbFadeIn var(--db-animation-duration, 500ms) cubic-bezier(0.16, 1, 0.3, 1) both;
          }
          .animate-db-slide-up {
            animation: dbSlideUp var(--db-animation-duration, 500ms) cubic-bezier(0.16, 1, 0.3, 1) both;
          }
          .animate-db-scale-in {
            animation: dbScaleIn var(--db-animation-duration, 500ms) cubic-bezier(0.16, 1, 0.3, 1) both;
          }
          .animate-db-progressive {
            animation: dbProgressive var(--db-animation-duration, 500ms) cubic-bezier(0.16, 1, 0.3, 1) both;
          }
          /* Smooth Transition */
          .db-transition {
            transition: all var(--db-animation-duration, 500ms) cubic-bezier(0.16, 1, 0.3, 1);
          }
        `}</style>
        {children}
      </div>
    </ThemeContext.Provider>
  );
};
