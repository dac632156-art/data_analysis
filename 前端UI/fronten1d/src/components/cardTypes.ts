export interface CardItem {
  id: string;
  type: "kpi" | "chart" | "table" | "insight" | "warning" | "fallback";
  title: string;
  priority: number;
  size: "s" | "m" | "l" | "xl";
  score: number;
  data: Record<string, unknown>;
  chart_type?: string;
  fallback_chain?: Array<Record<string, unknown>>;
}

export interface CardMeta {
  total_cards: number;
  insight_strength: number;
  data_quality: number;
}
