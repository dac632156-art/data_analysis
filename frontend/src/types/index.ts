/* DataMind AI - TypeScript 类型定义 */

export interface ColumnInfo {
  name: string;
  dtype: string;
  missing: number;
  missing_rate: number;
  unique: number;
  sample: string;
}

export interface DataInfo {
  rows: number;
  columns: number;
  memory_usage: string;
  total_missing: number;
  duplicate_rows: number;
}

export interface KPI {
  title: string;
  value: number | string;
  icon: string;
  color: string;
}

export interface ChartConfig {
  chart_type: string;
  x: string;
  y?: string;
  title?: string;
  color?: string;
  orientation?: string;
}

export interface CleaningStep {
  action: string;
  method?: string;
  dropped?: number;
  target_type?: string;
  sub_action?: string;
}

export interface ChartRecommendation {
  type: string;
  title: string;
  reason: string;
  x: string;
  y: string;
}

export interface MissingReport {
  total_missing: number;
  columns_with_missing: number;
  details: { column: string; missing: number; rate: number }[];
}

export interface OutlierResult {
  [column: string]: {
    count: number;
    ratio: number;
  };
}
