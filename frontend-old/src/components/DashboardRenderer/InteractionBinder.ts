/**
 * InteractionBinder —— Dashboard 交互绑定引擎
 *
 * 职责：读取 Interaction Schema，自动绑定：
 * - Global Filter → 筛选器 UI
 * - Cross Filter → Widget 间联动（click/hover 事件）
 * - Highlight → Hover Highlight 联动
 * - Drill Down → 下钻导航
 *
 * 不生成交互。只负责绑定。
 * 消费 Interaction Engine 输出的 InteractionSchema。
 */

import { useCallback, useRef, useState, useEffect, useMemo } from 'react';
import type {
  DashboardSchema, FilterRule, CrossFilterRule, HighlightRule,
  DrillDownRule, WidgetLinkageRule, WidgetSlot,
} from '../../types/dashboard';

// ============================================================
// Interaction State
// ============================================================

export interface InteractionState {
  /** 当前激活的 Global Filter 值 */
  globalFilterValues: Record<string, string>;
  /** 当前 Cross Filter 激活的数据名（联动高亮） */
  crossFilterLabel: string | null;
  /** Hover Highlight 激活的数据名 */
  hoverLabel: string | null;
  /** Drill Down 当前路径 */
  drillDownPath: Record<string, string>;  // widget_id → next_level
}

const INITIAL_STATE: InteractionState = {
  globalFilterValues: {},
  crossFilterLabel: null,
  hoverLabel: null,
  drillDownPath: {},
};

// ============================================================
// Interaction Binder Hook
// ============================================================

export function useInteractionBinder(schema: DashboardSchema | null) {
  const [state, setState] = useState<InteractionState>(INITIAL_STATE);

  const interactions = schema?.interactions;
  const globalFilters: FilterRule[] = interactions?.global_filters || [];
  const crossFilters: CrossFilterRule[] = interactions?.cross_filters || [];
  const highlights: HighlightRule[] = interactions?.highlights || [];
  const drillDowns: DrillDownRule[] = interactions?.drill_downs || [];
  const linkages: WidgetLinkageRule[] = interactions?.linkages || [];

  // ===== Global Filter =====
  const setGlobalFilter = useCallback((field: string, value: string) => {
    setState(prev => ({
      ...prev,
      globalFilterValues: { ...prev.globalFilterValues, [field]: value },
    }));
  }, []);

  const clearGlobalFilter = useCallback((field: string) => {
    setState(prev => {
      const next = { ...prev.globalFilterValues };
      delete next[field];
      return { ...prev, globalFilterValues: next };
    });
  }, []);

  // ===== Cross Filter =====
  const setCrossFilterLabel = useCallback((label: string | null) => {
    setState(prev => ({ ...prev, crossFilterLabel: label }));
  }, []);

  // ===== Hover Highlight =====
  const setHoverLabel = useCallback((label: string | null) => {
    setState(prev => ({ ...prev, hoverLabel: label }));
  }, []);

  // ===== Drill Down =====
  const triggerDrillDown = useCallback((widgetId: string, dimension: string, nextLevel: string) => {
    setState(prev => ({
      ...prev,
      drillDownPath: { ...prev.drillDownPath, [widgetId]: nextLevel },
    }));
  }, []);

  // ===== 派生数据 =====

  /** 哪些 Widget 受当前 Cross Filter 影响 */
  const crossFilterTargets = useMemo(() => {
    if (!state.crossFilterLabel) return [];
    return crossFilters.flatMap(cf => cf.targets);
  }, [state.crossFilterLabel, crossFilters]);

  /** 哪些 Widget 应高亮当前 hoverLabel */
  const highlightTargetWidgets = useMemo(() => {
    if (!state.hoverLabel) return [];
    // hover_highlight 类型规则的目标 Widget
    return highlights
      .filter(h => h.rule_type === 'hover_highlight')
      .map(h => h.widget_id);
  }, [state.hoverLabel, highlights]);

  /** 综合 Highlight Label（优先级：CrossFilter > HoverHighlight） */
  const activeHighlightLabel = useMemo(() => {
    if (state.crossFilterLabel) return state.crossFilterLabel;
    if (state.hoverLabel) return state.hoverLabel;
    return null;
  }, [state.crossFilterLabel, state.hoverLabel]);

  /** Global Filter 应作用于哪些 Widget */
  const globalFilterTargetWidgets = useMemo(() => {
    return globalFilters
      .filter(f => f.scope === 'global')
      .flatMap(f => f.target_widgets);
  }, [globalFilters]);

  /** Section scope Filter 应作用于哪些 Section */
  const sectionFilterMap = useMemo(() => {
    const map: Record<string, FilterRule[]> = {};
    globalFilters
      .filter(f => f.scope === 'section')
      .forEach(f => {
        for (const secId of f.target_sections) {
          if (!map[secId]) map[secId] = [];
          map[secId].push(f);
        }
      });
    return map;
  }, [globalFilters]);

  /** Widget scope Filter 应作用于哪些 Widget */
  const widgetFilterMap = useMemo(() => {
    const map: Record<string, FilterRule[]> = {};
    globalFilters
      .filter(f => f.scope === 'widget')
      .forEach(f => {
        for (const wid of f.target_widgets) {
          if (!map[wid]) map[wid] = [];
          map[wid].push(f);
        }
      });
    return map;
  }, [globalFilters]);

  /** Widget → CrossFilter 源映射（某个 Widget 作为 cross filter 源时，影响的 targets） */
  const crossFilterSourceMap = useMemo(() => {
    const map: Record<string, CrossFilterRule[]> = {};
    crossFilters.forEach(cf => {
      if (!map[cf.source_widget]) map[cf.source_widget] = [];
      map[cf.source_widget].push(cf);
    });
    return map;
  }, [crossFilters]);

  /** Widget → DrillDown 映射 */
  const drillDownMap = useMemo(() => {
    const map: Record<string, DrillDownRule[]> = {};
    drillDowns.forEach(dd => {
      if (!map[dd.widget_id]) map[dd.widget_id] = [];
      map[dd.widget_id].push(dd);
    });
    return map;
  }, [drillDowns]);

  /** 某个 Widget 是否有下钻能力 */
  const hasDrillDown = useCallback((widgetId: string): boolean => {
    return drillDownMap[widgetId]?.length > 0;
  }, [drillDownMap]);

  /** 某个 Widget 是否是 cross filter 源 */
  const isCrossFilterSource = useCallback((widgetId: string): boolean => {
    return crossFilterSourceMap[widgetId]?.length > 0;
  }, [crossFilterSourceMap]);

  /** 重置所有交互状态 */
  const resetAll = useCallback(() => {
    setState(INITIAL_STATE);
  }, []);

  return {
    state,
    interactions,
    globalFilters,
    crossFilters,
    highlights,
    drillDowns,
    linkages,
    // actions
    setGlobalFilter,
    clearGlobalFilter,
    setCrossFilterLabel,
    setHoverLabel,
    triggerDrillDown,
    resetAll,
    // derived
    crossFilterTargets,
    highlightTargetWidgets,
    activeHighlightLabel,
    globalFilterTargetWidgets,
    sectionFilterMap,
    widgetFilterMap,
    crossFilterSourceMap,
    drillDownMap,
    hasDrillDown,
    isCrossFilterSource,
  };
}
