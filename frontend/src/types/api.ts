/* DataMind AI - API 响应类型 */

export interface ApiResponse<T = unknown> {
  success: boolean;
  [key: string]: T | boolean | string | number | undefined;
}

export interface UploadResponse {
  session_id: string;
  success: boolean;
  file_name: string;
  rows: number;
  columns: number;
  memory_usage: string;
  total_missing: number;
  duplicate_rows: number;
  preview: Record<string, unknown>[];
  column_info: {
    name: string;
    dtype: string;
    missing: number;
    missing_rate: number;
    unique: number;
    sample: string;
  }[];
}

export interface PreviewResponse {
  success: boolean;
  preview: Record<string, unknown>[];
  total_rows: number;
}

export interface StatsResponse {
  success: boolean;
  stats: Record<string, unknown>[] | Record<string, unknown>;
  columns: string[];
}

export interface ChartResponse {
  success: boolean;
  figure: PlotlyFigure;
}

export interface PlotlyFigure {
  data: Record<string, unknown>[];
  layout: Record<string, unknown>;
}

/** ECharts 图表响应 */
export interface EChartResponse {
  success: boolean;
  option: Record<string, unknown>;
}

/** ECharts 仪表盘图表项 */
export interface EChartItem {
  title: string;
  option: Record<string, unknown>;
  /** 图表类型：''=普通图表, 'table'=同环比表格 */
  chart_type?: string;
  /** 同环比表格数据 */
  table_data?: Record<string, unknown>;
}

export interface InsightsResponse {
  success: boolean;
  insights: string;
}

export interface ChatResponse {
  success: boolean;
  answer: string;
}

/** 报告 section（五阶段分析流水线输出） */
export interface ReportSection {
  type: 'overview' | 'kpi' | 'trend' | 'structure' | 'top' | 'anomaly' | 'conclusion' | 'suggestions' | 'next_steps' | 'error';
  title: string;
  content?: string;
  /** insights 可以是字符串或带完整规则信息的对象 */
  insights?: Array<string | ReportInsight>;
  /** next_steps section 专有字段 */
  charts_to_create?: ChartToCreate[];
  action_items?: ActionItem[];
}

/** 单条洞察（对象格式，包含规则映射） */
export interface ReportInsight {
  chart_title: string | null;
  chart_type: string | null;
  table_type: string | null;
  rule_id: string | null;
  insight_label: string | null;
  analysis: string;
}

/** next_steps：推荐生成的图表 */
export interface ChartToCreate {
  chart_title: string;
  chart_type: string;
  rule_id: string;
  x_axis: string;
  y_axis: string;
  value: string;
  guide: string;
}

/** next_steps：操作清单项 */
export interface ActionItem {
  priority: number;
  action: string;
}

export interface AIReportResponse {
  success: boolean;
  sections: ReportSection[];
  raw_analysis?: Record<string, unknown>;
  warning?: string;
}

export interface ReportResponse {
  success: boolean;
  html: string;
}

export interface KPIResponse {
  success: boolean;
  kpis: { title: string; value: number | string; icon?: string; color?: string }[];
}

/** 环形图数据项 */
export interface RingChartItem {
  name: string;
  value: number;
}

/** 环形图配置 */
export interface RingChartConfig {
  title: string;
  data: RingChartItem[];
}

/** AI 大屏布局响应 */
export interface EChartsAiLayoutResponse {
  success: boolean;
  recommended_template: string;
  reason: string;
  block_title: string;
  nav_tabs?: string[];
  ring_charts?: RingChartConfig[];
  charts: EChartItem[];
}

/* ===== V2 分析引擎类型 ===== */

/** AI 返回的分析意图 */
export interface AnalysisIntent {
  business_question: string;
  analysis_goal: string;
  priority: 'high' | 'medium' | 'low';
  reason: string;
}

/** KPI 指标项（V2） */
export interface PackageKPIItem {
  label: string;
  value: string;
  change: string | null;
  kpi_type: 'sum' | 'avg' | 'count' | 'rate' | 'change';
}

/** 表格数据（V2） */
export interface PackageTableData {
  title: string;
  table_type: 'summary' | 'ranking' | 'cross' | 'growth' | 'correlation' | 'detail' | 'exception';
  columns: string[];
  rows: unknown[][];
}

/** 图表项（V2） */
export interface PackageChartItem {
  slot: string;
  chart_type: string;
  title: string;
  role: 'primary' | 'secondary' | 'detail';
  option: Record<string, unknown>;
}

/** 分析包（全系统统一数据对象） */
export interface AnalysisPackage {
  id: string;
  analysis_type: string;
  business_question: string;
  algorithm: string;
  dimension: string;
  metric: string;
  kpis: PackageKPIItem[];
  tables: PackageTableData[];
  charts: PackageChartItem[];
  insights: string[];
  conclusions: string[];
  can_run: boolean;
  fallback_from: string | null;
  saved_at: string | null;
  data_profile: Record<string, string[]>;
}

/** /insights/generate 响应（V2） */
export interface InsightsV2Response {
  success: boolean;
  insights: string;
  intents: AnalysisIntent[];
}

/** /analysis/run 响应 */
export interface AnalysisRunResponse {
  packages: AnalysisPackage[];
}

/** /analysis/save 响应 */
export interface AnalysisSaveResponse {
  saved_count: number;
  package_ids: string[];
}

/** /dashboard/saved-packages 响应 */
export interface SavedPackagesResponse {
  success: boolean;
  packages: AnalysisPackage[];
  total: number;
}
