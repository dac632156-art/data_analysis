/**
 * Dashboard Schema TypeScript 类型定义
 *
 * 与 Python src/dashboard/layout_schema.py + interaction_schema.py 完全对应。
 * Dashboard Renderer 的唯一数据输入。
 *
 * v2.0 支持：
 * - FilterScope（global/section/widget）
 * - WidgetLinkageRule + LinkageType
 * - Animation / Bookmark / DashboardState / Undo / ShareState 预留扩展
 */

// ============================================================
// Layout
// ============================================================

export interface LayoutConfig {
  name: string;                // "executive" | "wide" | "compact" | "geo" | "sales" | "finance"
  columns: number;             // 栅格列数（默认 12）
  section_order: string[];     // section 顺序
  section_gap: number;         // Section 间距（行）
  widget_gap: number;          // Widget 内边距（行）
  page_margin: number;         // 页面边距（行）
  /** 布局策略（后端 layout.strategy 或 schema.layout_strategy） */
  strategy?: string;           // "executive" | "sales" | "finance" | "compact" | "wide" | "geo"
  /** 栅格列数字符串（后端输出为 string） */
  grid?: string;
}

// ============================================================
// Widget Slot
// ============================================================

export interface WidgetPosition {
  x: number; y: number;        // Grid 起始列/行 (0-based)
  w: number; h: number;        // 列宽/行高
}

export interface WidgetSlot {
  widget_id: string;
  title: string;
  description: string;
  widget_type: 'chart' | 'kpi' | 'table' | 'map' | 'insight' | 'summary';
  position: WidgetPosition;
  size_class: 'hero' | 'large' | 'medium' | 'small';
  importance_score: number;
  z_index: number;
  section_id: string;
  group_id: string;
  chart_type: string | null;          // "line" | "bar" | "pie" | "map" | "scatter" | "radar" | "heatmap" | "treemap" | "funnel" | "waterfall" | "gauge" | null
  chart_config: Record<string, unknown>;
  supported_filters: { field: string; label: string; filter_type: string }[];
  metadata: Record<string, unknown>;
}

// ============================================================
// Section / Group
// ============================================================

export interface DashboardSection {
  id: string;
  role: 'header' | 'hero' | 'main' | 'secondary' | 'sidebar' | 'footer';
  title: string;
  y_start: number;
  y_end: number;
  widget_ids: string[];
}

export interface BusinessGroup {
  id: string;
  topic: string;
  widget_ids: string[];
  importance: number;
}

// ============================================================
// Interaction v2.0
// ============================================================

/** 筛选器作用范围 */
export type FilterScope = 'global' | 'section' | 'widget';

/** 筛选器类型 */
export type FilterType = 'global' | 'cross' | 'local';

/** Widget 联动类型 */
export type LinkageType = 'one_to_one' | 'one_to_many' | 'many_to_many';

/** 高亮规则类型 */
export type HighlightRuleType = 'top_n' | 'bottom_n' | 'anomaly' | 'high_growth' | 'threshold' | 'trend_change' | 'hover_highlight';

export interface FilterRule {
  id: string;
  name: string;
  field: string;
  filter_type: FilterType;
  scope: FilterScope;
  widget_type: 'date_range' | 'dropdown' | 'checkbox' | 'slider';
  target_widgets: string[];
  target_sections: string[];
  default_value: string | null;
  priority: number;
  metadata?: Record<string, unknown>;
}

export interface CrossFilterRule {
  id: string;
  source_widget: string;
  event: 'click' | 'hover' | 'select';
  field: string;
  field_label: string;
  targets: string[];
  priority: number;
  bidirectional: boolean;
  metadata?: Record<string, unknown>;
}

export interface DrillDownRule {
  id: string;
  widget_id: string;
  dimension: string;
  current_level: string;
  next_level: string;
  label: string;
  priority: number;
  metadata?: Record<string, unknown>;
}

export interface HighlightRule {
  id: string;
  widget_id: string;
  rule_type: HighlightRuleType;
  params: Record<string, unknown>;
  label: string;
  priority: number;
  metadata?: Record<string, unknown>;
}

export interface WidgetLinkageRule {
  id: string;
  source_widgets: string[];
  target_widgets: string[];
  linkage_type: LinkageType;
  business_topic: string;
  description: string;
  metadata?: Record<string, unknown>;
}

// ============================================================
// Interaction Config (Complete Dashboard Schema)
// ============================================================

export interface InteractionConfig {
  id: string;
  dashboard_id: string;
  version: string;
  global_filters: FilterRule[];
  cross_filters: CrossFilterRule[];
  drill_downs: DrillDownRule[];
  highlights: HighlightRule[];
  linkages: WidgetLinkageRule[];
  metadata: Record<string, unknown>;
  // 后端输出但前端暂不消费
  user_custom_filters?: Record<string, unknown>[];
  ai_exploration_paths?: Record<string, unknown>[];
  multi_page_routing?: Record<string, unknown>;
  permission_filters?: Record<string, unknown>[];
  // 预留扩展
  animation?: Record<string, unknown>;
  bookmark?: Record<string, unknown>;
  dashboard_state?: Record<string, unknown>;
  undo?: Record<string, unknown>;
  share_state?: Record<string, unknown>;
}

// ============================================================
// Dashboard Schema
// ============================================================

export interface DashboardSchema {
  id: string;
  title: string;
  created_at: string;
  version: string;
  metadata: Record<string, unknown>;
  blueprint_id: string;
  layout: LayoutConfig;
  /** 布局策略（兼容：优先读 layout.strategy，兜底读此顶层字段） */
  layout_strategy?: string;
  widgets: WidgetSlot[];
  sections: DashboardSection[];
  groups: BusinessGroup[];
  interactions: InteractionConfig;
  theme: Record<string, unknown>;
  responsive: Record<string, unknown>;
  dark_mode: boolean;
  mobile: Record<string, unknown>;
}

// ============================================================
// Renderer Props
// ============================================================

export interface DashboardRendererProps {
  schema: DashboardSchema | null;
  /** 覆盖 schema 内的 theme 设置 */
  theme?: DashboardThemeName;
  /** 加载状态 */
  loading?: boolean;
  /** 错误信息 */
  error?: string | null;
  /** 全局筛选器变更回调 */
  onFilterChange?: (field: string, value: string) => void;
  /** Widget 点击回调 */
  onWidgetClick?: (widgetId: string, data: Record<string, unknown>) => void;
  /** Drill Down 回调 */
  onDrillDown?: (widgetId: string, dimension: string, nextLevel: string) => void;
  /** 标题手动编辑保存回调 */
  onTitleChange?: (newTitle: string) => void;
  /** 点击"重新生成标题"回调 */
  onRegenerateTitle?: () => void;
}

export type DashboardThemeName = 'light' | 'dark' | 'blue' | 'gray';

export interface DashboardTheme {
  name: DashboardThemeName;
  background: string;
  cardBg: string;
  cardBorder: string;
  text: string;
  textSecondary: string;
  accent: string;
  chartColors: string[];
  kpiGradient: string;
  shadow: string;
  /** CSS 变量版本（用于 :root 注入） */
  cssVars: Record<string, string>;
  /** 字体 */
  fontFamily: string;
  /** 圆角 */
  borderRadius: string;
  /** 卡片 padding */
  cardPadding: string;
  /** 动画时长（ms） */
  animationDuration: number;
  /** 图表专用配色（来自 Theme Engine / theme/ChartStyle） */
  chart: import('../theme/ChartStyle').ChartStyleToken;
  /** 基础色板（来自 Theme Engine / theme/Palette） */
  palette: import('../theme/Palette').PaletteToken;
}

// ============================================================
// Widget Error 类型
// ============================================================

export interface WidgetError {
  widget_id: string;
  message: string;
  timestamp: number;
}

// ============================================================
// 智能排版大屏（LLM 驱动，复用经典网格数据源）
// 对应后端 POST /dashboard/smart-layout
// ============================================================

export interface SmartLayoutItem {
  slot: string;
  title: string;
  chart_type: string;
  analysis_type: string;
  /** 后端先验业务价值分 0~1 */
  suggested_business_value: number;
  /** LLM 给出的语义注意力分 0~1 */
  llm_weight: number;
  /** 融合后最终权重（决定落位档位） */
  attention_weight: number;
  // ★ 阶段B：LLM 直接输出的形状-槽位绑定（无则 undefined，computeLayout 按 attention_weight 兜底路由）
  shape?: string | null;          // kpi / hero_square / side_strip / hero_wide / side_square / full_width
  slot_id?: string | null;        // 蓝图槽位 id
  dims: number;
  series_count: number;
  row_count: number;
  metric_hint: string;
  value_hint: string;
  is_aggregated: boolean;
}

export interface SmartLayoutChart {
  slot: string;
  title: string;
  chart_type: string;
  option: Record<string, unknown> | null;
  table_data?: Record<string, unknown> | null;
  raw_data?: Record<string, unknown>[] | null;
  x: string;
  y: string;
  analysis_type: string;
}

export interface SmartLayoutResponse {
  success: boolean;
  /** "llm" | "fallback" | "empty" */
  source: string;
  model: string;
  note: string;
  items: SmartLayoutItem[];
  charts: SmartLayoutChart[];
}
