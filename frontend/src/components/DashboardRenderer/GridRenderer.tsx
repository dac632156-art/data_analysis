import React, { memo, useMemo, useCallback } from 'react';
import type { WidgetSlot, LayoutConfig, DashboardSection, WidgetError } from '../../types/dashboard';
import { WidgetFactory } from './WidgetFactory';
import { useDashboardTheme } from './ThemeProvider';

interface GridRendererProps {
  widgets: WidgetSlot[];
  sections?: DashboardSection[];
  layout: LayoutConfig;
  onFilter?: (field: string, value: string) => void;
  onWidgetClick?: (widgetId: string, data: Record<string, unknown>) => void;
  onDrillDown?: (widgetId: string, dimension: string, nextLevel: string) => void;
  onWidgetError?: (error: WidgetError) => void;
  /** Interaction Binder 传入 */
  highlightLabel?: string | null;
  crossFilterSourceMap?: Record<string, unknown[]>;
  drillDownMap?: Record<string, unknown[]>;
}

/**
 * GridRenderer —— Dashboard Grid 布局渲染器
 *
 * 负责将 WidgetSlot[] 渲染为 CSS Grid。
 * 不决定 Grid（Layout Engine 已输出）。
 * 只负责呈现。
 *
 * Responsive（Desktop）：
 * - 12 列栅格 → 每 4 列一个 medium Widget
 * - 24 列栅格 → 更精细控制
 *
 * 当前只完成 Desktop。架构预留 Tablet/Mobile。
 */

const SECTION_ROLE_NAMES: Record<string, string> = {
  header: '概览',
  hero: '核心指标',
  main: '主要分析',
  secondary: '辅助分析',
  sidebar: '侧边栏',
  footer: '补充信息',
};

export const GridRenderer: React.FC<GridRendererProps> = memo(({
  widgets, sections, layout, onFilter, onWidgetClick, onDrillDown, onWidgetError,
  highlightLabel, crossFilterSourceMap, drillDownMap,
}) => {
  const theme = useDashboardTheme();

  // ★ 过滤：剔除没有任何可渲染数据的 Widget
  // KPI → 有 value 或 sparkline data；Chart → 有 option；Table → 有 rows；Insight → 有 text
  const visibleWidgets = useMemo(() => widgets.filter(w => {
    const cfg = w.chart_config || {};
    if (w.widget_type === 'kpi') {
      const hasValue = cfg.data && Array.isArray(cfg.data) && cfg.data.length > 0;
      const hasKpi = w.metadata?.formatted || w.metadata?.value;
      return hasValue || hasKpi;
    }
    if (w.widget_type === 'chart') {
      return cfg.option && Object.keys(cfg.option).length > 0;
    }
    if (w.widget_type === 'table') {
      return (cfg.rows && Array.isArray(cfg.rows) && cfg.rows.length > 0);
    }
    if (w.widget_type === 'insight' || w.widget_type === 'summary') {
      return cfg.text || cfg.content || w.metadata?.text;
    }
    return true;  // map / 其他类型保留
  }), [widgets]);

  if (!visibleWidgets || visibleWidgets.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-slate-500 text-sm">
        暂无 Widget 数据
      </div>
    );
  }

  // fallback: 按 size_class / importance 分组（无 sections 或匹配失败时复用）
  const buildFallbackGroups = useCallback(
    (ws: WidgetSlot[]): Record<string, { role: string; title: string; widgets: WidgetSlot[] }> => {
      const groups: Record<string, { role: string; title: string; widgets: WidgetSlot[] }> = {};
      const sorted = [...ws].sort((a, b) =>
        a.position.y !== b.position.y ? a.position.y - b.position.y : a.position.x - b.position.x
      );
      for (const w of sorted) {
        const role = w.size_class === 'hero' ? 'hero'
          : w.importance_score >= 70 ? 'main'
          : w.importance_score >= 40 ? 'secondary'
          : 'footer';
        if (!groups[role]) groups[role] = { role, title: SECTION_ROLE_NAMES[role] || role, widgets: [] };
        groups[role].widgets.push(w);
      }
      return groups;
    },
    []
  );

  // 按 section 分组（如果 schema 有 sections）
  const grouped = useMemo(() => {
    if (sections && sections.length > 0) {
      // ★ 关键修复：用 sec.widget_ids（后端权威、数据驱动）匹配 widget。
      //   原逻辑用 w.section_id === sec.id，但两者前缀不一致
      //   （widget.section_id="hero" vs section.id="sec_hero"），导致全部匹配失败，
      //   所有 widget 被兜底塞进第一个 section（通常是 hero）→ 全宽渲染 → 一行一个。
      const groups: Record<string, { role: string; title: string; widgets: WidgetSlot[] }> = {};
      for (const sec of sections) {
        const ids = sec.widget_ids || [];
        const secWidgets = visibleWidgets.filter(w =>
          ids.includes(w.widget_id) || w.section_id === sec.id
        );
        if (secWidgets.length > 0) {
          groups[sec.id] = { role: sec.role, title: sec.title, widgets: secWidgets };
        }
      }
      // 极端兜底：schema 异常导致无匹配时，回退到 importance 分组
      // （避免再次把所有 widget 全塞进 hero section 导致全宽一行一个）
      if (Object.keys(groups).length === 0 && visibleWidgets.length > 0) {
        return buildFallbackGroups(visibleWidgets);
      }
      return groups;
    }
    // fallback: 按 size_class / importance 分组
    return buildFallbackGroups(visibleWidgets);
  }, [visibleWidgets, sections, buildFallbackGroups]);

  return (
    <div className="space-y-6 px-4 py-6">
      {Object.entries(grouped).map(([key, group], gi) => (
        <div key={key} className="animate-db-fade-in" style={{ animationDelay: `${gi * 80}ms` }}>
          {/* Section 标题 */}
          {group.role !== 'main' && group.title && (
            <div className="mb-3">
              <span className={`text-xs font-semibold tracking-wider uppercase ${theme.textSecondary}`}>
                {group.title}
              </span>
            </div>
          )}

          {/* Hero: 全宽 */}
          {group.role === 'hero' ? (
            <div className="mb-4">
              {group.widgets.map(w => (
                <WidgetFactory
                  key={w.widget_id}
                  widget={w}
                  onFilter={onFilter}
                  onClick={onWidgetClick}
                  onDrillDown={onDrillDown}
                  onWidgetError={onWidgetError}
                  highlightLabel={highlightLabel}
                  isCrossFilterSource={Boolean(crossFilterSourceMap?.[w.widget_id])}
                  hasDrillDown={Boolean(drillDownMap?.[w.widget_id])}
                />
              ))}
            </div>
          ) : (
            /* Other sections: CSS Grid with responsive breakpoints */
            <div
              className="grid gap-4"
              style={{
                gridTemplateColumns: `repeat(${layout.columns}, minmax(80px, 1fr))`,
              }}
            >
              {group.widgets.map(w => (
                <div
                  key={w.widget_id}
                  className="animate-db-slide-up"
                  style={{
                    gridColumn: `span ${w.position.w}`,
                    gridRow: `span ${w.position.h}`,
                    animationDelay: `${w.position.y * 40}ms`,
                  }}
                >
                  <WidgetFactory
                    widget={w}
                    onFilter={onFilter}
                    onClick={onWidgetClick}
                    onDrillDown={onDrillDown}
                    onWidgetError={onWidgetError}
                    highlightLabel={highlightLabel}
                    isCrossFilterSource={Boolean(crossFilterSourceMap?.[w.widget_id])}
                    hasDrillDown={Boolean(drillDownMap?.[w.widget_id])}
                  />
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
});

GridRenderer.displayName = 'GridRenderer';
