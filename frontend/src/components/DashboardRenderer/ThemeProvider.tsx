import React, { createContext, useContext, useMemo, useEffect } from 'react';
import type { DashboardTheme, DashboardThemeName } from '../../types/dashboard';

/**
 * ThemeEngine —— 统一主题引擎（内联浅色玻璃/仙气紫，原 theme/ 模块已删除）
 *
 * 4 种主题名（light/dark/blue/gray）统一映射到同一套浅色仙气观感，
 * 保证 Dashboard / Report / Insight / Chart 视觉一致。
 */

// ★ 10 色有序分类数据色板（与后端 echart_generator.py 的 BLUE_PALETTE 顺序取值完全一致）
const SERIES = [
  '#38BDF8', '#818CF8', '#22D3EE', '#FBBF24', '#F472B6',
  '#FB923C', '#84CC16', '#C084FC', '#60A5FA', '#2DD4BF',
];

function buildGalaxyDashboardTheme(): DashboardTheme {
  return {
    name: 'dark',
    background: 'bg-[var(--db-bg)]',
    cardBg: 'bg-[var(--db-card-bg)]',
    cardBorder: 'border-[var(--db-card-border)]',
    text: 'text-[var(--db-text)]',
    textSecondary: 'text-[var(--db-text-secondary)]',
    accent: '#38BDF8',
    chartColors: [...SERIES],
    kpiGradient: 'from-[var(--db-accent)] to-[var(--db-accent-light)]',
    shadow: '0 2px 12px rgba(0,0,0,0.25)',
    cssVars: {
      // ★ 浅色玻璃主题：背景透明让白鹤透出，卡片/边框白色玻璃，文字深色可读
      '--db-bg': 'transparent',
      '--db-card-bg': 'rgba(255,255,255,0.45)',
      '--db-card-border': 'rgba(255,255,255,0.55)',
      '--db-text': '#0f172a',
      '--db-text-secondary': '#475569',
      '--db-accent': '#7c3aed',
      '--db-accent-light': 'rgba(124,58,237,0.20)',
      '--db-shadow': '0 8px 32px rgba(99,102,241,0.10)',
      '--db-glow': '0 0 24px rgba(124,58,237,0.18)',
    },
    fontFamily: "'Inter','SF Pro Display',-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif",
    borderRadius: '12px',
    cardPadding: '16px',
    animationDuration: 400,
    chart: {
      series: [...SERIES],
      grid: 'rgba(148,163,184,0.35)',
      axis: 'rgba(100,116,139,0.55)',
      legend: '#94A3B8',
      emphasisGlow: 'rgba(124,58,237,0.55)',
      tooltip: { background: '#0F172A', border: 'rgba(255,255,255,0.08)', content: '#CBD5E1' },
      radar: { axis: 'rgba(100,116,139,0.15)', split: 'rgba(100,116,139,0.08)', area: 'rgba(56,189,248,0.15)' },
    },
    palette: {
      primary: '#38BDF8',
      primaryHover: '#7DD3FC',
      textPrimary: '#0f172a',
      textMuted: '#94A3B8',
      pageBg: '#ffffff',
      success: '#34D399',
      danger: '#FB7185',
      border: 'rgba(148,163,184,0.25)',
    },
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
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
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
