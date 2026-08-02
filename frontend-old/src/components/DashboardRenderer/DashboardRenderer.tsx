import React, { useCallback, useEffect, useMemo, useState, useRef } from 'react';
import type { DashboardRendererProps, DashboardSchema, FilterRule, WidgetSlot, WidgetError } from '../../types/dashboard';
import { DashboardThemeProvider } from './ThemeProvider';
import { GridRenderer } from './GridRenderer';
import { useInteractionBinder } from './InteractionBinder';

/**
 * DashboardRenderer —— Dashboard Generator 的最后一层
 *
 * 唯一职责：读取 Complete Dashboard Schema，渲染专业可视化大屏。
 * 不分析数据、不计算指标、不生成 Widget、不决定布局、不设计交互。
 *
 * 完整 API：
 * - renderDashboard() ← 本组件
 * - renderSection() ← GridRenderer
 * - renderWidget() ← WidgetFactory
 * - renderInteraction() ← InteractionBinder
 * - renderTheme() ← ThemeProvider
 */

export const DashboardRenderer: React.FC<DashboardRendererProps> = ({
  schema, theme: propTheme, loading, error, onFilterChange, onWidgetClick, onDrillDown,
  onTitleChange, onRegenerateTitle,
}) => {
  // ===== Interaction Binder =====
  const binder = useInteractionBinder(schema);

  // ===== 监听 CustomEvent（ChartWidget 发出的 CrossFilter） =====
  useEffect(() => {
    const handleCrossFilter = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (detail.label) {
        binder.setCrossFilterLabel(detail.label);
      } else {
        binder.setCrossFilterLabel(null);
      }
    };

    window.addEventListener('dashboard:cross-filter', handleCrossFilter);

    return () => {
      window.removeEventListener('dashboard:cross-filter', handleCrossFilter);
    };
  }, [binder]);

  // ===== Global Filter change → 回调 =====
  const handleFilterChange = useCallback((field: string, value: string) => {
    binder.setGlobalFilter(field, value);
    onFilterChange?.(field, value);
  }, [binder, onFilterChange]);

  // ===== Drill Down =====
  const handleDrillDown = useCallback((widgetId: string, dimension: string, nextLevel: string) => {
    binder.triggerDrillDown(widgetId, dimension, nextLevel);
    onDrillDown?.(widgetId, dimension, nextLevel);
  }, [binder, onDrillDown]);

  // ===== Widget Error =====
  const handleWidgetError = useCallback((err: WidgetError) => {
    console.warn(`[DashboardRenderer] Widget ${err.widget_id} 错误:`, err.message);
  }, []);

  // ===== Loading State =====
  if (loading) {
    return (
      <DashboardThemeProvider theme={propTheme}>
        <div className="min-h-screen flex items-center justify-center">
          <DashboardSkeleton />
        </div>
      </DashboardThemeProvider>
    );
  }

  // ===== Error State =====
  if (error) {
    return (
      <DashboardThemeProvider theme={propTheme}>
        <div className="min-h-screen flex flex-col items-center justify-center gap-3 text-red-400">
          <div className="text-4xl">⚠</div>
          <p className="text-sm">{error}</p>
        </div>
      </DashboardThemeProvider>
    );
  }

  // ===== Empty State =====
  if (!schema || !schema.widgets || schema.widgets.length === 0) {
    return (
      <DashboardThemeProvider theme={propTheme}>
        <div className="min-h-screen flex flex-col items-center justify-center gap-4">
          <div className="text-5xl opacity-20">📊</div>
          <p className="text-slate-500 text-sm">Dashboard 数据为空</p>
          <p className="text-slate-600 text-xs">请先执行数据分析并生成 Dashboard Schema</p>
        </div>
      </DashboardThemeProvider>
    );
  }

  // ===== Normal State =====
  // ★ 主题解析优先级：propTheme > schema.dark_mode
  // 但 schema.dark_mode 默认 false（后端默认值），会导致即使业务场景是深色
  // 也会走 light 主题。因此业务侧应在调用方显式传入 propTheme='dark'
  return (
    <DashboardThemeProvider
      theme={propTheme || (schema.dark_mode ? 'dark' : 'dark')}
      darkMode={propTheme ? propTheme !== 'light' : schema.dark_mode}
    >
      <DashboardContent
        schema={schema}
        binder={binder}
        onFilterChange={handleFilterChange}
        onWidgetClick={onWidgetClick}
        onDrillDown={handleDrillDown}
        onWidgetError={handleWidgetError}
        onTitleChange={onTitleChange}
        onRegenerateTitle={onRegenerateTitle}
      />
    </DashboardThemeProvider>
  );
};

// ============================================================
// Dashboard Content (internal, after theme resolved)
// ============================================================

const DashboardContent: React.FC<{
  schema: DashboardSchema;
  binder: ReturnType<typeof useInteractionBinder>;
  onFilterChange: (field: string, value: string) => void;
  onWidgetClick?: (widgetId: string, data: Record<string, unknown>) => void;
  onDrillDown?: (widgetId: string, dimension: string, nextLevel: string) => void;
  onWidgetError?: (error: WidgetError) => void;
  onTitleChange?: (newTitle: string) => void;
  onRegenerateTitle?: () => void;
}> = React.memo(({ schema, binder, onFilterChange, onWidgetClick, onDrillDown, onWidgetError, onTitleChange, onRegenerateTitle }) => {
  const globalFilters = binder.globalFilters;
  const highlightLabel = binder.activeHighlightLabel;

  // ===== 标题内联编辑 state =====
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [editTitle, setEditTitle] = useState('');
  const titleInputRef = useRef<HTMLInputElement>(null);

  const handleTitleDoubleClick = useCallback(() => {
    if (!schema || !onTitleChange) return;
    setEditTitle(schema.title);
    setIsEditingTitle(true);
    setTimeout(() => titleInputRef.current?.select(), 0);
  }, [schema, onTitleChange]);

  const handleTitleSave = useCallback(() => {
    const trimmed = editTitle.trim();
    if (trimmed && trimmed !== schema?.title && onTitleChange) {
      onTitleChange(trimmed);
    }
    setIsEditingTitle(false);
  }, [editTitle, schema, onTitleChange]);

  const handleTitleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleTitleSave();
    } else if (e.key === 'Escape') {
      setIsEditingTitle(false);
    }
  }, [handleTitleSave]);

  // 提取各 field 的可选值
  // ★ 优先从 schema.filter_options[field] 取（后端从 DataFrame 直接提取 distinct 值）
  const extractOptions = useCallback((field: string): string[] => {
    const opts = new Set<string>();
    // 过滤掉明显的时间戳/日期字符串（避免 line chart 的 xAxis 时间轴污染非时间字段下拉）
    const isTimeLike = (s: string): boolean => {
      if (!s) return false;
      const t = s.trim();
      return /^\d{4}[-/]\d{1,2}([-/]\d{1,2})?(\s\d{1,2}:\d{2}(:\d{2})?)?$/.test(t)
          || /^\d{1,2}[-/]\d{1,2}[-/]\d{2,4}$/.test(t);
    };

    // 1) ★ 后端注入的 filter_options（最准确，来自 session DataFrame）
    const filterOpts = (schema as any).filter_options as Record<string, string[]> | undefined;
    if (filterOpts && Array.isArray(filterOpts[field])) {
      filterOpts[field].forEach(v => {
        const sv = String(v);
        if (!isTimeLike(sv)) opts.add(sv);
      });
      // 后端已提供 → 直接用，不再走兜底
      if (opts.size > 0) return Array.from(opts).slice(0, 30);
    }

    // 2) 兜底：从 widget.chart_config.dim_values 取（同样过滤时间戳）
    schema.widgets.forEach(w => {
      const cfg = w.chart_config || {};
      const dimValues = cfg.dim_values as Record<string, string[]> | undefined;
      if (dimValues && Array.isArray(dimValues[field])) {
        dimValues[field].forEach(v => {
          const sv = String(v);
          if (!isTimeLike(sv)) opts.add(sv);
        });
      }
    });
    if (opts.size > 0) return Array.from(opts).slice(0, 30);

    // 3) 最后兜底：从 xAxis / pie.data 取（仅取明显非时间值）
    schema.widgets.forEach(w => {
      const opt = (w.chart_config || {}).option || {};
      const xa = opt.xAxis;
      if (xa && Array.isArray(xa.data)) {
        (xa.data as unknown[]).forEach(v => {
          const sv = String(v);
          if (!isTimeLike(sv)) opts.add(sv);
        });
      }
      if (opt.series && Array.isArray(opt.series)) {
        (opt.series as Array<Record<string, unknown>>).forEach(s => {
          if (Array.isArray(s.data)) {
            (s.data as unknown[]).forEach(item => {
              if (typeof item === 'object' && item && 'name' in (item as object)) {
                const sv = String((item as Record<string, unknown>).name);
                if (!isTimeLike(sv)) opts.add(sv);
              }
            });
          }
        });
      }
    });
    return Array.from(opts).slice(0, 30);
  }, [schema.widgets, schema]);

  return (
    <div className="max-w-[1600px] mx-auto animate-db-fade-in">
      {/* Header */}
      <header className="px-6 pt-6 pb-2">
        <div className="flex items-center justify-center gap-3 group/title">
          {isEditingTitle ? (
            <input
              ref={titleInputRef}
              type="text"
              value={editTitle}
              onChange={e => setEditTitle(e.target.value)}
              onBlur={handleTitleSave}
              onKeyDown={handleTitleKeyDown}
              className="text-2xl font-bold tracking-tight bg-slate-800/80 text-slate-100
                border border-amber-500/60 rounded px-2 py-0.5 outline-none
                focus:border-amber-400 focus:ring-1 focus:ring-amber-500/30
                placeholder:text-slate-600 max-w-xl w-full"
              maxLength={30}
              placeholder="输入仪表盘标题"
            />
          ) : (
            <h1
              className={`text-2xl font-bold tracking-tight cursor-default select-none
                ${onTitleChange ? 'hover:text-amber-300/90 transition-colors cursor-text' : 'text-slate-100'}`}
              onDoubleClick={handleTitleDoubleClick}
              title={onTitleChange ? '双击编辑标题' : undefined}
            >
              {schema.title}
            </h1>
          )}
          {onTitleChange && !isEditingTitle && (
            <button
              onClick={handleTitleDoubleClick}
              className="opacity-0 group-hover/title:opacity-100 transition-opacity
                text-slate-500 hover:text-amber-400 cursor-pointer"
              title="编辑标题"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                <path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z" />
              </svg>
            </button>
          )}
        </div>
        <div className="flex items-center justify-center gap-4 mt-2">
          <span className="text-xs text-slate-500">
            {schema.widgets.length} Widgets · {schema.groups?.length || 0} Groups
          </span>
          {(schema.layout_strategy || schema.layout.strategy) && (
            <span className="text-xs px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              Layout: {schema.layout_strategy || schema.layout.strategy}
            </span>
          )}
          {schema.metadata?.['layout_selected'] && (
            <span className="text-xs px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              {(schema.metadata['layout_selected'] as string)}
            </span>
          )}
          {onRegenerateTitle && (
            <button
              onClick={onRegenerateTitle}
              className="text-xs px-2 py-1 rounded bg-indigo-500/15 hover:bg-indigo-500/25
                text-indigo-400 hover:text-indigo-300 border border-indigo-500/20
                transition-colors cursor-pointer"
              title="AI 重新生成标题"
            >
              🔄 重新生成标题
            </button>
          )}
        </div>
      </header>

      {/* Global Filter Bar */}
      {globalFilters.length > 0 && (
        <div className="px-6 pb-3">
          <GlobalFilterBar
            filters={globalFilters}
            widgets={schema.widgets}
            extractOptions={extractOptions}
            onChange={onFilterChange}
          />
        </div>
      )}

      {/* Highlight 状态提示 */}
      {highlightLabel && (
        <div className="flex items-center justify-center gap-3 px-4 py-2"
          style={{ background: 'rgba(59,130,246,0.12)', borderBottom: '1px solid rgba(59,130,246,0.15)' }}>
          <span className="text-xs text-blue-400">
            🔗 联动高亮：<strong className="text-white">{highlightLabel}</strong>
          </span>
          <button onClick={() => binder.setCrossFilterLabel(null)}
            className="px-2 py-0.5 text-xs rounded bg-indigo-500/30 text-indigo-400
              hover:bg-indigo-500/50 db-transition border border-indigo-500/30">
            ✕ 清除
          </button>
        </div>
      )}

      {/* Global Filter 状态提示（筛选高亮 feedback） */}
      {Object.entries(binder.state.globalFilterValues).filter(([, v]) => v).length > 0 && (
        <div className="flex items-center justify-center gap-3 px-4 py-2 flex-wrap"
          style={{ background: 'rgba(139,92,246,0.10)', borderBottom: '1px solid rgba(139,92,246,0.15)' }}>
          <span className="text-xs text-[#A78BFA]">🔍 筛选高亮：</span>
          {Object.entries(binder.state.globalFilterValues).filter(([, v]) => v).map(([field, value]) => (
            <span key={field} className="flex items-center gap-1 text-xs px-2 py-0.5 rounded
              bg-[#8B5CF6]/15 text-[#C4B5FD] border border-[#8B5CF6]/30">
              <strong className="text-white">{value}</strong>
              <button onClick={() => binder.clearGlobalFilter(field)}
                className="text-[#C4B5FD] hover:text-white">✕</button>
            </span>
          ))}
        </div>
      )}

      {/* Grid */}
      <GridRenderer
        widgets={schema.widgets}
        sections={schema.sections}
        layout={schema.layout}
        onFilter={onFilterChange}
        onWidgetClick={onWidgetClick}
        onDrillDown={onDrillDown}
        onWidgetError={onWidgetError}
        highlightLabel={highlightLabel}
        globalFilterValues={binder.state.globalFilterValues}
        crossFilterSourceMap={binder.crossFilterSourceMap}
        drillDownMap={binder.drillDownMap}
      />
    </div>
  );
});

DashboardContent.displayName = 'DashboardContent';

// ============================================================
// Global Filter Bar
// ============================================================

const GlobalFilterBar: React.FC<{
  filters: FilterRule[];
  widgets: WidgetSlot[];
  extractOptions: (field: string) => string[];
  onChange: (field: string, value: string) => void;
}> = React.memo(({ filters, extractOptions, onChange }) => {
  return (
    <div className="flex flex-wrap items-center gap-3">
      {filters.map(f => {
        const options = f.widget_type === 'date_range' ? [] : extractOptions(f.field);
        const scopeBadge = f.scope === 'global' ? '🌐' : f.scope === 'section' ? '📦' : '📌';
        return (
          <div key={f.id} className="flex items-center gap-2 animate-db-scale-in">
            <label className="text-xs text-slate-400">
              {scopeBadge} {f.name}
            </label>
            {f.widget_type === 'date_range' ? (
              <input
                type="date"
                className="bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-1.5 text-xs text-slate-300
                  focus:outline-none focus:border-indigo-500/50 db-transition"
                onChange={e => onChange(f.field, e.target.value)}
              />
            ) : (
              <select
                className="bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-1.5 text-xs text-slate-300
                  focus:outline-none focus:border-indigo-500/50 db-transition cursor-pointer"
                onChange={e => onChange(f.field, e.target.value)}
                defaultValue=""
              >
                <option value="">全部</option>
                {options.map(o => (
                  <option key={o} value={o}>{o}</option>
                ))}
              </select>
            )}
          </div>
        );
      })}
    </div>
  );
});

GlobalFilterBar.displayName = 'GlobalFilterBar';

// ============================================================
// Skeleton (Loading State)
// ============================================================

const DashboardSkeleton: React.FC = () => (
  <div className="w-full max-w-[1600px] mx-auto px-6 py-8 space-y-6 animate-pulse">
    <div className="h-8 w-48 bg-white/[0.04] rounded" />
    <div className="grid grid-cols-4 gap-4">
      {[1, 2, 3, 4].map(i => (
        <div key={i} className="h-24 bg-white/[0.03] rounded-xl border border-white/[0.04]" />
      ))}
    </div>
    <div className="grid grid-cols-3 gap-4">
      <div className="col-span-2 h-64 bg-white/[0.03] rounded-xl border border-white/[0.04]" />
      <div className="h-64 bg-white/[0.03] rounded-xl border border-white/[0.04]" />
    </div>
    <div className="grid grid-cols-3 gap-4">
      {[1, 2, 3].map(i => (
        <div key={i} className="h-48 bg-white/[0.03] rounded-xl border border-white/[0.04]" />
      ))}
    </div>
  </div>
);
