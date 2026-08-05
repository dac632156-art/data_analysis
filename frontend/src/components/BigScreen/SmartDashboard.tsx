/**
 * SmartDashboard —— 三模式大屏预览（用真实已保存分析包驱动）
 *
 * 数据流（真实链路，无假数据）：
 *   sessionId → 后端 saved_packages (getSavedPackages)
 *   → 提取 pkg.rendered_charts / pkg.rendered_kpis / pkg.rendered_tables
 *   → 转为 SmartLayoutChart[] + KPI 列表
 *   → 三模式切换（聚拢 / 上下 / 压顶）→ reassignSlotsByMode 重排 slot
 *   → computeLayout 算 CSS Grid → 按 slot 渲染图表
 *
 * 用法：/dashboard?mock=1 → 跳到此组件（DashboardPage 在 mock 模式渲染它）。
 * 真实大屏（/dashboard，无 mock 参数）走旧 DashboardPage 的 5 模板（已还原）。
 *
 * ★ 关键：图表数据来自用户保存的分析包，与「真实大屏」的数据源完全一致，
 *   只是排版方式（三模式 ABC）不同。绝无假数据。
 */
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { FiCpu, FiAlertTriangle } from 'react-icons/fi';
import * as api from '../../api/client';
import type { SmartLayoutItem, SmartLayoutChart } from '../../types/dashboard';
import type { ComputeLayoutResult, LayoutAssignment } from '../../layout/computeLayout';
import { computeLayout } from '../../layout/computeLayout';
import { renderSmartChart } from '../DashboardRenderer/ChartRegistry';
import MOCK_PACKAGES from './mockPackages';

/**
 * 单图级错误边界 —— 隔离 ECharts StrictMode / HMR 卸载时的
 *   `Cannot read properties of null (reading 'getBoundingClientRect')` 等异常。
 */
class ChartErrorBoundary extends React.Component<
  { children: React.ReactNode; slot: string; chartType: string },
  { hasError: boolean }
> {
  constructor(props: any) {
    super(props);
    this.state = { hasError: false };
  }
  static getDerivedStateFromError() {
    return { hasError: true };
  }
  componentDidCatch(err: any) {
    console.warn('[ChartErrorBoundary] 单图渲染降级:', this.props.slot, err?.message);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="w-full h-full flex items-center justify-center text-xs text-slate-400 bg-white/30">
          <div className="text-center">
            <FiAlertTriangle className="inline mr-1" />
            <span>图表 {this.props.chartType} 渲染降级</span>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

interface SmartDashboardProps {
  sessionId: string;
  mock?: boolean;
  mode?: 'A' | 'B' | 'C';
}

const KPI_TYPES = new Set(['metric', 'kpi', 'card', 'metric_card']);

type ChartLike = SmartLayoutChart & { slot_id?: string };

/**
 * 按指定模式（A/B/C）重新分配 charts/items 的 slot。
 *
 * 原则：
 *   1. KPI 在 A 模式占顶栏 kpi_grid_1~4，C 模式占底栏 kpi_grid_1~4，B 模式不放 KPI。
 *   2. 主槽位取自 BLUEPRINT（computeLayoutBlueprint 的 12 列蓝图），溢出图走
 *      extra_wide_* 槽位 + 序号后缀，保证 (chart,item) 一一对应、slot 唯一。
 *   3. C 模式把 KPI 移到末尾，让 full_wide 优先占 Row 1（压顶式）。
 */
/**
 * 统一 KPI 识别：chart_type 命中 KPI_TYPES，或 option.kind==='metric' /
 * option.metric 存在（后端两种 KPI 载体都兼容）。
 */
function isMetricChart(c?: { chart_type?: string | null; option?: any | null }): boolean {
  if (!c) return false;
  const t = (c.chart_type || '').toLowerCase();
  if (KPI_TYPES.has(t)) return true;
  const opt = c.option as any;
  if (opt && (opt.kind === 'metric' || opt.metric)) return true;
  return false;
}

/**
 * 表格识别：chart_type 命中 table/tabular/grid，或 option.series 含 type:'table'，
 * 或 option.tooltip.kind==='table'，或 option 自身有 columns/rows 结构（用户行为表）。
 */
function isTableChart(c?: { chart_type?: string | null; option?: any | null; table_data?: any | null }): boolean {
  if (!c) return false;
  const t = (c.chart_type || '').toLowerCase();
  // ★ 兼容多种表格类型名（实际大屏里常见：cohort_table、rank_table、
  //   同环比表、retention_table、heatmap_table、cohort_retention 等）
  if (
    t === 'table' || t === 'tabular' || t === 'grid' || t === 'list' || t === 'detail'
    || t === 'analysis_table' || t === 'cohort_table' || t === 'rank_table'
    || t === 'retention_table' || t === 'cohort_retention'
    || /_table$|^table_/.test(t)
  ) return true;
  // ★ 直接有 table_data 字段也是表（顶层字段，不是 option.table_data）
  if (c.table_data) {
    if (Array.isArray(c.table_data)) return true;
    if (typeof c.table_data === 'object') {
      const td: any = c.table_data;
      if (Array.isArray(td.rows) || Array.isArray(td.data) || Array.isArray(td.columns)) return true;
    }
  }
  const opt: any = c.option || {};
  if (opt && typeof opt === 'object') {
    // ECharts table series
    if (Array.isArray(opt.series) && opt.series.some((s: any) => s && s.type === 'table')) return true;
    // 自定义表格：含 columns + rows/data
    if (Array.isArray(opt.columns) && (Array.isArray(opt.rows) || Array.isArray(opt.data))) return true;
    if (Array.isArray(opt.table_data) || Array.isArray(opt.tableData)) return true;
    // 自定义 kind 标记
    if (opt.kind === 'table' || opt.kind === 'tabular') return true;
  }
  return false;
}

/**
 * 图表分类（用于语义化分配槽位）。
 * 返回桶数组，每个桶按"重要性优先级"排列：
 *   - kpi: KPI 卡片
 *   - full: 大环/全宽图（适合 full_wide 压顶）
 *   - heatmap: 热力图（适合双开 hero_wide_*）
 *   - pie/funnel: 环形/漏斗（适合 hero_square 中央）
 *   - line: 趋势线（适合 side_strip/hero_wide）
 *   - bar/ranking: 柱/排行（适合 side_square）
 *   - table: 表格（适合 full_wide 末位 / side_tail）
 *   - other: 其他（默认 side_square）
 */
type ChartBucket =
  | 'kpi' | 'full' | 'heatmap' | 'heatmap_wide' | 'pie' | 'funnel'
  | 'line' | 'bar' | 'bar_dense' | 'table' | 'other'
  | 'bar_rank_channel' | 'bar_rank_stage'         // ranking 排行二级子类
  | 'line_dual_axis' | 'bubble' | 'radar'         // ★ 双轴 / 气泡 / 雷达 精确子桶
  // ★ pie 按信息密度细分：rich（≥6 类，如 RFM 八大群体）抢 6 列 hero 槽；
  //   sparse（≤5 类，如三档用户占比）下沉到 3/4 列窄槽，不再与 rich 争大槽
  | 'pie_rich' | 'pie_sparse'
  // ★ 柱状图密度细分：sparse（≤5 柱，如客户生命周期价值分层）走窄槽，
  //   不再占 12 整行浪费空间
  | 'bar_sparse';

/**
 * 柱状图信息密度判定：categories 数量 ≥ 7 视为「高密度」，
 * 需单独占整行 [12]，避免被塞进 3/4 列小卡后被压扁看不清。
 * 低密度（如各渠道新增用户、品类对比）仍走常规 'bar' 桶。
 */
function isDenseBar(c: ChartLike): boolean {
  const opt = (c.option ?? {}) as Record<string, unknown>;
  // 1) 标准 ECharts option：xAxis.data / yAxis.data 长度
  const axis = (opt.xAxis ?? opt.yAxis) as Record<string, unknown> | Array<Record<string, unknown>> | undefined;
  if (axis) {
    const first = Array.isArray(axis) ? axis[0] : axis;
    const data = first?.data;
    if (Array.isArray(data) && data.length >= 7) return true;
  }
  // 2) raw_data 行数（后端扁平清单形态）
  const raw = c.raw_data as Array<unknown> | undefined;
  if (Array.isArray(raw) && raw.length >= 7) return true;
  // 3) series[].data 长度
  const series = Array.isArray(opt.series) ? (opt.series as Array<Record<string, unknown>>) : [];
  for (const s of series) {
    if (Array.isArray(s.data) && s.data.length >= 7) return true;
  }
  return false;
}

/**
 * 热力图宽度判定：列维度（周/月/阶段）数量较多（≥ 8）视为「宽幅」，
 * 如同期群分析 W0-W11（12 周）→ 占 6 列而非被挤进 4 列或强制 12 列。
 * 普通热力图（如 6 月 × 5 阶段）仍走常规 'heatmap' 桶（占 12 列或 6 列自适应）。
 */
function isWideHeatmap(c: ChartLike): boolean {
  const opt = (c.option ?? {}) as Record<string, unknown>;
  // 1) raw_data 去重列维度（如「阶段 / 周」字段的不同取值数）
  const raw = c.raw_data as Array<Record<string, unknown>> | undefined;
  if (Array.isArray(raw) && raw.length > 0) {
    // 取最长字符串/分类字段的不同取值数作为列维度数
    const keys = Object.keys(raw[0]);
    let maxDistinct = 0;
    for (const k of keys) {
      const vals = new Set(raw.map((r) => String(r[k] ?? '')));
      vals.delete('');
      maxDistinct = Math.max(maxDistinct, vals.size);
    }
    if (maxDistinct >= 8) return true;
  }
  // 2) 标准 ECharts heatmap：series[0].data 的第二个坐标（y 轴）不同取值数
  const series = Array.isArray(opt.series) ? (opt.series as Array<Record<string, unknown>>) : [];
  const s0 = series[0];
  if (s0 && Array.isArray(s0.data)) {
    const yVals = new Set(
      (s0.data as Array<unknown>).map((d) => (Array.isArray(d) ? String((d as unknown[])[1] ?? '') : '')),
    );
    yVals.delete('');
    if (yVals.size >= 8) return true;
  }
  return false;
}

function bucketOf(c: ChartLike): ChartBucket {
  if (isMetricChart(c)) return 'kpi';
  // ★ 表格优先于标题/类型识别（避免被误判为 line/bar）
  if (isTableChart(c)) return 'table';
  const t = (c.chart_type || '').toLowerCase();
  const title = (c.title || '').toLowerCase();
  // ★ 双轴 / 气泡 / 雷达 走精确子桶，避免与 line / other / other 混池
  if (/双轴|dual[\s_-]?axis|^dual$/.test(title) || t === 'dual_axis' || t === 'combo') return 'line_dual_axis';
  if (t === 'bubble' || /气泡|bubble/.test(title)) return 'bubble';
  if (t === 'radar' || /雷达|radar/.test(title)) return 'radar';
  // ★ ranking 二级子类：按标题细分，避免两条 ranking 在 blueprint 里被同一桶抢
  // 1) 先按 chart_type 精确识别（如 'ranking' / 'bar_rank' / 'rank_*'）
  if (t === 'ranking' || t === 'bar_rank' || t === 'rank' || /^rank_/.test(t)) return 'bar_rank_channel';
  if (/渠道.*排行|渠道.*价值/.test(title)) return 'bar_rank_channel';
  if (/用户阶段.*排行|用户.*阶段|阶段.*价值/.test(title)) return 'bar_rank_stage';
  // ★ 用户最新诉求：「客户生命周期价值 Top5 排行」含"客户"+TopN，应归到 channel 排行桶
  //   此前它会被后面的 bar 兜底吃掉，错位渲染成彩色柱状图
  if (/客户.*生命周期.*排行|客户.*top\s*\d|客户.*Top\s*\d|top\s*\d.*排行/i.test(title)) return 'bar_rank_channel';
  // 2) 通用 ranking 关键词默认进 channel 桶（让"Top5 排行"等通用 ranking 也有位可站）
  if (/ranking|排行|^top\s*\d|^top\d|top排行/.test(title)) return 'bar_rank_channel';
  // ★ 横向柱状图（后端 chart_type='bar' 但 slot 来自 clv_a_*）走 ranking 多色排行版
  //   兜底：标题含"各X平均…价值" / "客渠道" 等排行语义时 → 直接进 ranking，避免被柱状图吞掉
  //   兜底目的：让"各客渠道平均客户生命周期价值"等横向条形排行图，优先走到 ranking 渲染，
  //   而不是落到下方 bar 判定被错误地画成垂直柱状胶囊。
  if (typeof c.slot === 'string' && (c.slot.startsWith('clv_a_') || c.slot.startsWith('clv_'))) return 'bar_rank_channel';
  if (/各.{0,4}(客渠道|渠道|平台|来源|媒介)\s*平均|平均客户生命周期价值|各.*平均.*价值/i.test(title)) return 'bar_rank_channel';
  // 优先按标题语义匹配（更鲁棒：用户生成的 chart_type 可能不规范）
  if (/heatmap|热力/.test(title)) return 'heatmap';
  if (/funnel|漏斗/.test(title)) return 'funnel';
  // ★ 环形图按「信息密度」细分（用户诉求：三档用户占比只有 3 类，
  //   丰富度远低于 RFM 八大群体占比，不该平等竞争 row2 的 6 列 hero 大槽）
  if (/pie|环形|donut|玫瑰/.test(title)) {
    return densityOf(c) === 'sparse' ? 'pie_sparse' : 'pie_rich';
  }
  if (/line|trend|趋势|折线|曲线|活跃|留存|变化/.test(title)) return 'line';
  // ★ 柱状图按「信息密度」三档细分（用户诉求：客户生命周期价值分层只有 3 根柱，
  //   不需要 12 整行；收入关联规则柱子很多，却被挤进小槽导致信息糊成一团）
  //   - sparse（≤5 柱）→ 'bar_sparse'，走 3/4 列窄槽
  //   - compact（6-7 柱）→ 'bar'，走常规槽
  //   - dense（≥8 柱）→ 'bar_dense'，独占整行 [12]
  if (/bar|柱|对比/.test(title)) {
    if (isDenseBar(c)) return 'bar_dense';
    return densityOf(c) === 'sparse' ? 'bar_sparse' : 'bar';
  }
  // ★ 表格识别放宽：用户生成的明细表常以"…表""…明细"结尾，
  //   也支持 "…列表/…数据表/…清单"。`表` 单字匹配会误伤（"图表"也会进表桶），
  //   故改用「结尾表 / 表格 / 明细 / 列表 / 清单 / 数据表」更稳。
  if (/明细|表格|列表|清单|数据表$|^用户行为|user[\s_-]?behav.*table/i.test(title)) return 'table';
  // 标题以「X表」结尾（X 为 1~6 个字，避免"图表"误伤）
  if (/^[\u4e00-\u9fa5A-Za-z0-9\s]{1,8}(表|table|list)$/i.test(title)) return 'table';
  // 然后按 chart_type 兜底
  // ★ 修复：后端热力图 chart_type 实为 'heatmap' | 'cohort_heatmap' | 'heatmap_2d'，
  //   旧逻辑只认精确 'heatmap'，导致 cohort_heatmap/heatmap_2d 落到 other 桶被挤进 4 列窄槽。
  //   改为子串包含匹配，并保留宽幅判定（≥8 列维度走 heatmap_wide 占 6 列）。
  if (/heatmap/.test(t) || t === 'calendar') return isWideHeatmap(c) ? 'heatmap_wide' : 'heatmap';
  if (t === 'funnel') return 'funnel';
  if (t === 'pie' || t === 'donut' || t === 'rose') {
    return densityOf(c) === 'sparse' ? 'pie_sparse' : 'pie_rich';
  }
  if (t === 'line' || t === 'area') return 'line';
  if (t === 'bar' || t === 'horizontal_bar') {
    if (isDenseBar(c)) return 'bar_dense';
    return densityOf(c) === 'sparse' ? 'bar_sparse' : 'bar';
  }
  if (t === 'table' || t === 'tabular' || t === 'analysis_table' || t === 'cohort_table' || t === 'rank_table' || t === 'retention_table' || t === 'cohort_retention' || /_table$|^table_/.test(t)) return 'table';
  if (t === 'gauge' || t === 'treemap' || t === 'sunburst' || t === 'sankey' || t === 'radar') return 'full';
  return 'other';
}

/**
 * ★ 注入点①：桶内按 attention_weight 降序排序。
 * 同一桶（如多个环形图 pie）出现时，权重最高的图优先被 hero 槽选中，
 * 权重低的图留到后续槽或溢出行——彻底解决「多环形图不知定哪个 hero」。
 * 不引入额外 LLM 调用，直接复用后端融合权重。
 */
function weightOf(chart: ChartLike, items: SmartLayoutItem[]): number {
  const idx = items.findIndex((it) => it.slot === chart.slot);
  return idx >= 0 ? (items[idx].attention_weight ?? 0) : 0;
}

/**
 * 业务模型兜底：pkg.analysis_type 为空或 'default' 时，按标题关键词归类。
 * 解决痛点：聚类 / RFM / 关联 / 留存 / 转化等不同业务模型的表格，原始 analysis_type 都为 'default'，
 *   全归到 '__no_pkg__' 同一组暴聚一起。
 */
function businessGroupOf(chart: ChartLike): string {
  const pkgType = (chart.analysis_type || '').trim();
  if (pkgType && pkgType !== 'default' && pkgType !== 'manual_chart') return pkgType;
  const title = (chart.title || '').toLowerCase();
  if (/rfm|八大群体|八群体|八分层|分值|分层|价值分层|潜力/.test(title)) return 'rfm';
  if (/聚类|cluster|分群|客户画像|画像/.test(title)) return 'cluster';
  if (/关联|关联规则|购物篮|交叉表|cooccur/.test(title)) return 'correlation';
  if (/留存|同期群|cohort|归因|生命/.test(title)) return 'cohort';
  if (/转化|aarrr|漏斗|funnel/.test(title)) return 'funnel';
  if (/ranking|排行|总收|top\s*\d|tab.*?reverse/.test(title)) return 'ranking';
  if (/aov|客单价|平均单价|auction/.test(title)) return 'aov';
  if (/复购|回购|freq|recency|monetary/.test(title)) return 'repurchase';
  return pkgType || '__no_pkg__';
}

/**
 * 信息密度：按 chart_type + series 数量决定该图适合宽槽还是窄槽。
 * 'sparse' (≤5 类) → 适合 3-4 列窄槽（如三档用户、客户生命周期价值分层）
 * 'dense'  (≥7 类) → 适合 6-12 列宽槽（如 RFM 八大群体、收入关联规则）
 * 'compact' (6-7 类) → 双向兼容
 * 解决痛点：客户生命周期价值分层（3 柱）不该占 12 整行；收入关联规则（多柱）不该挤 4 列。
 */
function densityOf(chart: ChartLike): 'sparse' | 'compact' | 'dense' {
  const t = (chart.chart_type || '').toLowerCase();
  const opt = (chart.option || {}) as Record<string, any>;
  const seriesArr = Array.isArray(opt.series) ? opt.series : (opt.series ? [opt.series] : []);
  let totalCategories = 0;
  for (const s of seriesArr) {
    if (!s) continue;
    if (Array.isArray(s.data)) totalCategories += s.data.length;
    const xax = opt.xAxis;
    if (Array.isArray(xax)) {
      for (const x of xax) {
        if (x && Array.isArray(x.data)) totalCategories = Math.max(totalCategories, x.data.length);
      }
    }
  }
  if (!totalCategories && Array.isArray(chart.raw_data)) totalCategories = (chart.raw_data as unknown[]).length;
  if (t === 'bar' || t === 'horizontal_bar' || t === 'column') {
    if (totalCategories <= 5) return 'sparse';
    if (totalCategories <= 7) return 'compact';
    return 'dense';
  }
  if (t === 'pie' || t === 'donut' || t === 'rose') {
    if (totalCategories <= 5) return 'sparse';
    if (totalCategories <= 7) return 'compact';
    return 'dense';
  }
  if (t === 'line' || t === 'area') {
    if (totalCategories <= 5) return 'sparse';
    if (totalCategories <= 12) return 'compact';
    return 'dense';
  }
  return 'compact';
}
function sortByWeight(
  charts: ChartLike[],
  items: SmartLayoutItem[],
): { charts: ChartLike[]; items: SmartLayoutItem[] } {
  const paired = charts.map((c) => ({ c, it: items.find((it) => it.slot === c.slot) }));
  paired.sort((a, b) => weightOf(a.c, items) - weightOf(b.c, items)); // 升序
  // 翻转成降序（权重最高在前）
  paired.reverse();
  return {
    charts: paired.map((p) => p.c),
    items: paired.map((p) => p.it as SmartLayoutItem),
  };
}

function reorderByBuckets(charts: ChartLike[], items: SmartLayoutItem[]): {
  kpis: ChartLike[]; kpiItems: SmartLayoutItem[];
  fulls: ChartLike[]; heatmaps: ChartLike[]; heatmapWides: ChartLike[]; pies: ChartLike[]; funnels: ChartLike[];
  lines: ChartLike[]; bars: ChartLike[]; barDenses: ChartLike[]; tables: ChartLike[]; others: ChartLike[];
  // ★ ranking 二级子类：分别承载「渠道价值排行」「用户阶段价值排行」
  rankChannels: ChartLike[]; rankStages: ChartLike[];
  // ★ 三种非典型图精确子桶
  dualAxes: ChartLike[]; bubbles: ChartLike[]; radars: ChartLike[];
  // ★ 密度子桶：pie/bar 按信息密度分流，避免低密度图霸占宽槽
  pieRich: ChartLike[]; pieSparse: ChartLike[]; barSparse: ChartLike[];
  pieRichItems: SmartLayoutItem[]; pieSparseItems: SmartLayoutItem[]; barSparseItems: SmartLayoutItem[];
  // 每个桶对应的 item 列表（与 charts 一一对应，已按权重排序）
  kpiItemsB: SmartLayoutItem[];
  fullItems: SmartLayoutItem[]; heatmapItems: SmartLayoutItem[]; heatmapWideItems: SmartLayoutItem[];
  pieItems: SmartLayoutItem[]; funnelItems: SmartLayoutItem[];
  lineItems: SmartLayoutItem[]; barItems: SmartLayoutItem[]; barDenseItems: SmartLayoutItem[];
  tableItems: SmartLayoutItem[]; otherItems: SmartLayoutItem[];
  rankChannelItems: SmartLayoutItem[]; rankStageItems: SmartLayoutItem[];
  dualAxisItems: SmartLayoutItem[]; bubbleItems: SmartLayoutItem[]; radarItems: SmartLayoutItem[];
} {
  const kpiCharts = charts.filter((c) => bucketOf(c) === 'kpi');
  const kpiItems = items.filter((_, i) => bucketOf(charts[i]) === 'kpi');
  const rest = charts.filter((c) => bucketOf(c) !== 'kpi');
  const restItems = items.filter((_, i) => bucketOf(charts[i]) !== 'kpi');

  // ★ 注入点①：每个桶内部按权重降序，使 hero 槽确定性选到最高权重图
  const mkBucket = (b: ChartBucket): { charts: ChartLike[]; items: SmartLayoutItem[] } => {
    const c: ChartLike[] = []; const it: SmartLayoutItem[] = [];
    rest.forEach((ch, i) => {
      if (bucketOf(ch) === b) {
        c.push(ch);
        it.push(restItems[i]);
      }
    });
    return sortByWeight(c, it);
  };
  const kSorted = sortByWeight(kpiCharts, kpiItems);

  // ★ 密度子桶先算出来，pies / bars 再由子桶合并而成，
  //   保证下游 allCharts（溢出兜底）不会因为图落入新桶而被漏掉。
  const bPieRich = mkBucket('pie_rich');
  const bPieSparse = mkBucket('pie_sparse');
  const bPiePlain = mkBucket('pie');
  const bBar = mkBucket('bar');
  const bBarSparse = mkBucket('bar_sparse');
  // pies：rich 在前（高信息量优先占宽槽），其次 plain，最后 sparse
  const mergedPies = [...bPieRich.charts, ...bPiePlain.charts, ...bPieSparse.charts];
  const mergedPieItems = [...bPieRich.items, ...bPiePlain.items, ...bPieSparse.items];
  const mergedBars = [...bBar.charts, ...bBarSparse.charts];
  const mergedBarItems = [...bBar.items, ...bBarSparse.items];

  return {
    kpis: kSorted.charts, kpiItems: kSorted.items, kpiItemsB: kSorted.items,
    fulls: mkBucket('full').charts,   fullItems: mkBucket('full').items,
    heatmaps: mkBucket('heatmap').charts, heatmapItems: mkBucket('heatmap').items,
    heatmapWides: mkBucket('heatmap_wide').charts, heatmapWideItems: mkBucket('heatmap_wide').items,
    pies: mergedPies,                 pieItems: mergedPieItems,
    pieRich: bPieRich.charts,         pieRichItems: bPieRich.items,
    pieSparse: bPieSparse.charts,     pieSparseItems: bPieSparse.items,
    funnels: mkBucket('funnel').charts, funnelItems: mkBucket('funnel').items,
    lines: mkBucket('line').charts,   lineItems: mkBucket('line').items,
    bars: mergedBars,                 barItems: mergedBarItems,
    barSparse: bBarSparse.charts,     barSparseItems: bBarSparse.items,
    barDenses: mkBucket('bar_dense').charts, barDenseItems: mkBucket('bar_dense').items,
    tables: mkBucket('table').charts, tableItems: mkBucket('table').items,
    others: mkBucket('other').charts, otherItems: mkBucket('other').items,
    rankChannels: mkBucket('bar_rank_channel').charts, rankChannelItems: mkBucket('bar_rank_channel').items,
    rankStages: mkBucket('bar_rank_stage').charts,    rankStageItems: mkBucket('bar_rank_stage').items,
    dualAxes: mkBucket('line_dual_axis').charts,      dualAxisItems: mkBucket('line_dual_axis').items,
    bubbles: mkBucket('bubble').charts,               bubbleItems: mkBucket('bubble').items,
    radars: mkBucket('radar').charts,                 radarItems: mkBucket('radar').items,
  };
}

// =====================================================================
// 语义化布局生成：直接生成 ComputeLayoutResult，绕开 computeLayout 蓝图
// =====================================================================

const COL_AREA = (row: number, colStart: number, width: number) =>
  `r${row}c${colStart}s${width}`;

interface RowSpec {
  row: number;          // 1-based
  template: number[];   // 每槽宽度（合计 12）
  height: string;       // 行高
  sizeClass: 'kpi' | 'wide' | 'full';
  // 每个槽的精确语义桶（与设计图位置一一对应）。
  // 声明后该槽优先从指定桶取图；未声明（undefined）则走原宽度泛型兜底。
  // 例：['heatmap','pie','funnel'] 表示 左热力-中环形-右漏斗。
  content_order?: (ChartBucket | undefined)[];
}

/**
 * 三模式蓝图（12 列）。槽位顺序即渲染优先级。
 *
 * 模式A「聚拢式」：KPI 顶栏 → 渠道价值排行(3)+环形(6)+漏斗(3) → 全宽热力图 → 阶段价值(4)+气泡(4)+各渠道新增(4) → 双轴(6)+活跃趋势(6) → 全宽明细表
 * 模式B「上下式」：KPI 顶栏 → 左大图 + 右大图 → 左趋势 + 中央大图 + 右趋势 → 底部全宽
 * 模式C「压顶式」：全宽压顶 → 左大图 + 右大图 → 左趋势 + 中央大图 + 右趋势 → KPI 落底
 */
const MODE_BLUEPRINTS: Record<'A' | 'B' | 'C', RowSpec[]> = {
  A: [
    // 顶栏 KPI（4 卡）
    { row: 1, template: [3, 3, 3, 3], height: '140px', sizeClass: 'kpi' },
    // 核心三联：左 渠道价值排行(3) + 中 pie 环形(6) + 右 funnel 漏斗(3)
    // ★ 用户明确诉求：保持 [3,6,3] 不变。
    //   pie 6 列 hero 槽位：优先接 pieRich（≥6 类高信息密度图，如 RFM 八大群体），
    //   次选 pieCompact（≤5 类低密度图，如三档用户）；funnel 槽独立存在。
    { row: 2, template: [3, 6, 3], height: '540px', sizeClass: 'wide',
      // ★ 槽位精确语义：左 ranking，中 pie_rich（≥6 类高信息量，如 RFM 八大群体占比），右 funnel
      //   pie_rich 缺失时由 takeFrom 的泛型兜底自动回退到 pie 桶，不会留空洞。
      //   低密度环形图（如三档用户占比，仅 3 类）走 pie_sparse，下沉到 row4 的 4 列窄槽。
      content_order: ['bar_rank_channel', 'pie_rich', 'funnel'] },
    // ★ 用户行为留存热力图 [12] 自占一行，紧贴环形图下面（用户最新诉求：与双轴图互换位置）
    { row: 3, template: [12], height: '420px', sizeClass: 'full',
      content_order: ['heatmap'] },
    // 用户阶段价值(4) + 气泡矩阵(4) + 各渠道新增用户(4)
    // ★ 用户最新诉求：双轴图与气泡矩阵互换，气泡落入此行中间 4 列
    // ★ 同时承接第 2 个 ranking 排行图（如「客户生命周期价值 Top5 排行」）：
    //   row2 的 [3,6,3] 只放 1 个 ranking 槽位（第 2 个 ranking 会被本行 4 列槽位吃掉）
    //   改为 content_order: ['bar_rank_channel', 'bubble', 'bar']——把两个 ranking 都聚集到 row4 左 4 列，
    //   配合 isDenseBar 让「各渠道平均 CLV」柱状图走 4 列（不再被挤进 3 列槽位）
    { row: 4, template: [4, 4, 4], height: '380px', sizeClass: 'wide',
      // ★ 承接「低密度」图：三档用户占比（3 类环形）、客户生命周期价值分层（3 柱）
      //   这两类图信息量小，4 列窄槽足够，不该占 6 列 hero 或 12 列整行。
      //   气泡矩阵占首槽保证类型分散（避免与相邻行同色柱状图三连）。
      content_order: ['bubble', 'pie_sparse', 'bar_sparse'] },
    // 双轴图(6) + 活跃趋势(6)
    // ★ 双连 [6,6]，双轴图占左 6 列（用户最新诉求：与气泡矩阵互换位置），活跃趋势占右
    //   行高由 380→440 缓解双轴图被压扁（图表含 3 个 KPI 头部 + 折柱混合本体）
    { row: 5, template: [6, 6], height: '440px', sizeClass: 'wide',
      content_order: ['line_dual_axis', 'line'] },
    // 用户行为明细表下移至最底部 [12]
    // ★ 用户最新诉求：与双轴图互换位置，让双轴图上移靠近环形图
    { row: 6, template: [12], height: '360px', sizeClass: 'full',
      content_order: ['table'] },
    // ★ 高密度柱状图（如「各客群薅羊毛组合」气泡矩阵柱，categories ≥ 7）单独占整行 [12]
    //   缺图时整行自动塌缩跳过（不破坏整体布局），仅在有此类图时动态插入
    { row: 7, template: [12], height: '440px', sizeClass: 'full',
      content_order: ['bar_dense'] },
    // ★ 宽幅热力图（如同期群分析 W0-W11 多周）占 6 列，避免被压进 4 列小卡
    //   右侧 6 列留空给其它溢出图（动态补位），缺图则整行塌缩
    { row: 8, template: [6, 6], height: '440px', sizeClass: 'wide',
      content_order: ['heatmap_wide', undefined] },
  ],
  B: [
    { row: 1, template: [3, 3, 3, 3], height: '140px', sizeClass: 'kpi' },
    { row: 2, template: [6, 6],       height: '440px', sizeClass: 'wide' },
    { row: 3, template: [3, 6, 3],    height: '360px', sizeClass: 'wide' },
    { row: 4, template: [12],         height: '360px', sizeClass: 'full' },
  ],
  C: [
    { row: 1, template: [12],         height: '360px', sizeClass: 'full' },                       // 全宽压顶
    { row: 2, template: [6, 6],       height: '420px', sizeClass: 'wide' },
    { row: 3, template: [3, 6, 3],    height: '360px', sizeClass: 'wide' },
    { row: 4, template: [3, 3, 3, 3], height: '140px', sizeClass: 'kpi' },                       // KPI 落底
  ],
};

/**
 * ★ 注入点③：列宽重归一化。
 * 把若干槽的原始宽度按比例缩放到目标总列数（默认 12），并保证：
 *   1. 缩放后各列之和严格等于 target（修正取整产生 ±1 误差）
 *   2. 误差优先补到最宽的一列，避免前端 grid 出现 11/13 列错位
 * 例：原 [3,6,3] 塌缩中间 → 有效 [3,3] → 重归一化 → [6,6]
 */
function redistributeColumns(widths: number[], target = 12): number[] {
  const sum = widths.reduce((s, w) => s + w, 0);
  if (sum <= 0) return widths.slice();
  const raw = widths.map((w) => Math.max(1, Math.round((w / sum) * target)));
  let diff = target - raw.reduce((s, w) => s + w, 0);
  // 把误差补到最宽列（diff 可能为负，则从容差最大列扣回）
  let guard = 0;
  while (diff !== 0 && guard++ < 64) {
    if (diff > 0) {
      const mi = raw.indexOf(Math.max(...raw));
      raw[mi] += 1;
      diff -= 1;
    } else {
      // 从最宽且 >1 的列扣回，避免扣成 0
      const candidates = raw.map((w, i) => ({ w, i })).filter((x) => x.w > 1);
      if (!candidates.length) break;
      const mi = candidates.reduce((a, b) => (a.w >= b.w ? a : b)).i;
      raw[mi] -= 1;
      diff += 1;
    }
  }
  return raw;
}

function buildSemanticLayout(
  charts: ChartLike[],
  items: SmartLayoutItem[],
  mode: 'A' | 'B' | 'C'
): ComputeLayoutResult {
  const m = mode.toUpperCase() as 'A' | 'B' | 'C';
  const blueprint = MODE_BLUEPRINTS[m];

  const bucket = reorderByBuckets(charts, items);
  const { kpis, kpiItems } = bucket;

  // ★ 池化选择器：每个槽按桶优先级选图，并保证每张图只被分配一次。
  //   poolItems 与 pool 一一对应（已在 reorderByBuckets 内按权重降序），
  //   因此 picked.item 总是有效，标题/权重不再回退到 chart.title 兜底。
  const usedIds = new Set<string>();
  const takeFrom = (
    pool: ChartLike[],
    poolItems: SmartLayoutItem[],
    sizeClass: 'kpi' | 'wide' | 'full'
  ): { chart: ChartLike; item?: SmartLayoutItem; sizeClass: 'kpi' | 'wide' | 'full' } | null => {
    for (let i = 0; i < pool.length; i++) {
      const ch = pool[i];
      if (usedIds.has(ch.slot)) continue;
      usedIds.add(ch.slot);
      return { chart: ch, item: poolItems[i] ?? undefined, sizeClass };
    }
    return null;
  };

  // ★ 语义桶 → { charts, items } 映射（含二级子桶与精确子桶），用于精确桶与兜底统一取图
  const POOL: Record<string, { charts: ChartLike[]; items: SmartLayoutItem[] }> = {
    kpi: { charts: bucket.kpis, items: bucket.kpiItemsB },
    full: { charts: bucket.fulls, items: bucket.fullItems },
    heatmap: { charts: bucket.heatmaps, items: bucket.heatmapItems },
    heatmap_wide: { charts: bucket.heatmapWides, items: bucket.heatmapWideItems },
    // ★ pie 桶按密度高度区分：pieRich 进 6 列 hero，pieCompact 进 4-6 列，pieSparse 3-4 列
    pie_rich: { charts: bucket.pieRich, items: bucket.pieRichItems },
    pie_sparse: { charts: bucket.pieSparse, items: bucket.pieSparseItems },
    pie: { charts: bucket.pies, items: bucket.pieItems },
    funnel: { charts: bucket.funnels, items: bucket.funnelItems },
    line: { charts: bucket.lines, items: bucket.lineItems },
    line_dual_axis: { charts: bucket.dualAxes, items: bucket.dualAxisItems },
    bubble: { charts: bucket.bubbles, items: bucket.bubbleItems },
    radar: { charts: bucket.radars, items: bucket.radarItems },
    // ★ bar 桶按密度区分：barSparse 进 3-4 列窄槽，barDense 进 12 列整行
    bar_sparse: { charts: bucket.barSparse, items: bucket.barSparseItems },
    bar_dense: { charts: bucket.barDenses, items: bucket.barDenseItems },
    bar: { charts: bucket.bars, items: bucket.barItems },
    bar_rank_channel: { charts: bucket.rankChannels, items: bucket.rankChannelItems },
    bar_rank_stage: { charts: bucket.rankStages, items: bucket.rankStageItems },
    table: { charts: bucket.tables, items: bucket.tableItems },
    other: { charts: bucket.others, items: bucket.otherItems },
  };

  const assignments: LayoutAssignment[] = [];

  // ★ 跨行去重：上一行（或上 N 行）的 chart_type 列表延续到本行 rowUsedTypes，
  //   避免 row N 末出现「bar、line」而 row N+1 开头又是「bar、line」造成视觉重复。
  let prevRowTypes: string[] = [];
  let prevPrevRowTypes: string[] = [];

  for (const rowSpec of blueprint) {
    const { row, template, sizeClass: rowSize, content_order } = rowSpec;

    // ── 阶段一：先为整行每个槽尝试取图（不立即落位）──
    // ★ 用户最新诉求：同行内 + 跨行最近 1 行内尽量避免连续相同 chart_type，降低视觉重复
    const rowUsedTypes = new Set<string>([...prevRowTypes, ...prevPrevRowTypes]);
    const picks: (ReturnType<typeof takeFrom> | null)[] = template.map((width, slotIdx) => {
      let picked: ReturnType<typeof takeFrom> | null = null;
      // ★ KPI 行允许多 KPI 重复（每张都是 metric 类型），不做去重
      const avoidDuplicate = rowSize !== 'kpi';
      // ★ 优先按 content_order 精确语义桶取图（对齐设计图）；因 POOL 已按权重降序，
      //   多图同桶时 hero 槽必然选中权重最高者（注入点①落地）
      const exactBucket = content_order?.[slotIdx];
      if (exactBucket && !usedIds.has(`__b_${exactBucket}`)) {
        const pool = POOL[exactBucket];
        // ★ 注意：不再让 heatmap_wide 回退到 heatmap——会让 row8 第 1 槽抢走
        //   本该属于 row3 [12] 整行的普通 heatmap，导致 row3 整行虚空。
        //   现在 row8 第 1 槽缺图时返回 null，由兄弟槽或第 2 槽（undefined）
        //   走终极兜底 / redistributeColumns 撑宽，整体布局更稳。
        picked = takeFrom(pool.charts, pool.items, rowSize === 'kpi' ? 'kpi' : rowSize);
        // ★ 若行内已有同 chart_type，则尝试下一个非同类型候选
        if (avoidDuplicate && picked && rowUsedTypes.has((picked.chart.chart_type || '').toLowerCase())) {
          // 找一张同桶但 chart_type 不同的图
          for (let i = 1; i < pool.charts.length; i++) {
            const alt = pool.charts[i];
            if (!usedIds.has(alt.slot) && !rowUsedTypes.has((alt.chart_type || '').toLowerCase())) {
              const altItem = pool.items[i];
              picked = { chart: alt, sizeClass: rowSize === 'kpi' ? 'kpi' : rowSize, item: altItem };
              usedIds.add(alt.slot);
              // 移除之前错误取走的：用 takeFrom 模式下如果池是数组引用，需要从原池删除该 slot
              // —— takeFrom 内部已删除，但这里我们手工构造，需清理
              const idxInPool = pool.charts.findIndex((c) => c.slot === alt.slot);
              if (idxInPool >= 0) pool.charts.splice(idxInPool, 1);
              if (altItem) {
                const idxInItems = pool.items.findIndex((it) => it.slot === alt.slot);
                if (idxInItems >= 0) pool.items.splice(idxInItems, 1);
              }
              break;
            }
          }
        }
      }
      // ★ 回退：按宽度泛型兜底——每个候选都做"跨池跨行去重"过滤
      //   之前 fallback 直接 pool[0]，没看 rowUsedTypes，所以同类图会贴邻；这里改成：
      //   优先选"chart_type 不在 rowUsedTypes"的候选，实在没有再退而求其次保留原选。
      //   ★★★ 关键修复：仅当精确桶属于"低密度稀疏桶"（用户刻意设计、不该被泛型池抢图）时，
      //   才在窄槽位（≤6）跳过 fallback 让该槽返回 null——
      //   redistributeColumns 把兄弟槽按比例撑宽（如 [4,4] → [6,6]）。
      //
      //   其它精确桶（如 'bar' / 'line' / 'heatmap' / 'bubble' 等）即使声明了，缺图时
      //   也必须走 width fallback，否则会出现"整行虚空"（row3 [12] heatmap 空 / row7
      //   [12] bar_dense 空 / row4 [4,4,4] bubble 空）这种严重的布局破坏。
      //   注意：bar_sparse / pie_sparse 是唯一受 skip 保护的"窄槽专用桶"，
      //   因为它们对应"信息量低、本来就该被其它宽图挤走"的图（如三档用户占比、客户生命周期分层）。
      const isSparseBucket = exactBucket === 'bar_sparse' || exactBucket === 'pie_sparse';
      const skipWidthFallback = isSparseBucket && width <= 6;
      if (!picked && !skipWidthFallback) {
        const pickWithDedup = (pools: { charts: ChartLike[]; items: SmartLayoutItem[] }[]): ReturnType<typeof takeFrom> | null => {
          // 先试图跨池找一张非重复 chart_type 的图（避免漏掉唯一非重复候选）
          for (const p of pools) {
            for (let i = 0; i < p.charts.length; i++) {
              const ch = p.charts[i];
              if (usedIds.has(ch.slot)) continue;
              if (!avoidDuplicate) {
                const r = takeFrom(p.charts, p.items, 'kpi');
                return r;
              }
              if (!rowUsedTypes.has((ch.chart_type || '').toLowerCase())) {
                const idx = p.charts.findIndex((c) => c.slot === ch.slot);
                if (idx >= 0) p.charts.splice(idx, 1);
                const itmIdx = p.items.findIndex((it) => it.slot === ch.slot);
                const itm = itmIdx >= 0 ? p.items.splice(itmIdx, 1)[0] : undefined;
                usedIds.add(ch.slot);
                return { chart: ch, item: itm, sizeClass: rowSize === 'kpi' ? 'kpi' : 'wide' };
              }
            }
          }
          // 实在没候选：回到首个 pool 第一张（哪怕重复），保证槽不空
          for (const p of pools) {
            const r = takeFrom(p.charts, p.items, 'kpi');
            if (r) return r;
          }
          return null;
        };

        if (rowSize === 'kpi') {
          picked = pickWithDedup([{ charts: bucket.kpis, items: bucket.kpiItemsB }]);
        } else if (width === 12) {
          picked = pickWithDedup([
            { charts: bucket.fulls, items: bucket.fullItems },
            { charts: bucket.tables, items: bucket.tableItems },
            { charts: bucket.lines, items: bucket.lineItems },
            { charts: bucket.others, items: bucket.otherItems },
          ]);
        } else if (width === 6) {
          // ★ 6 列宽槽：优先热力图（修复后 cohort_heatmap/heatmap_2d 已正确入桶），
          //   其次环形/折线/密集柱状图；明确排除 bar_sparse（≤5 柱窄图），
          //   使其只能落到 3/4 列窄槽，不再抢占 6 列 hero 位。
          picked = pickWithDedup([
            { charts: bucket.heatmaps, items: bucket.heatmapItems },
            { charts: bucket.heatmapWides, items: bucket.heatmapWideItems },
            { charts: bucket.pies, items: bucket.pieItems },
            { charts: bucket.lines, items: bucket.lineItems },
            { charts: bucket.barDenses, items: bucket.barDenseItems },
            { charts: bucket.others, items: bucket.otherItems },
          ]);
        } else { // width === 3 or 4
          // ★ 同业务模型相邻前提下，3/4 列槽位优先精确补桶（funnel/heatmap/pie 等漏斗槽等），
          //   再走通用 width=3/4 兜底——避免 funnel 在 row2 第二槽失守后被推到 overflow。
          picked = pickWithDedup([
            { charts: bucket.heatmaps, items: bucket.heatmapItems },
            { charts: bucket.funnels, items: bucket.funnelItems },
            { charts: bucket.pies, items: bucket.pieItems },
            { charts: bucket.lines, items: bucket.lineItems },
            { charts: bucket.bars, items: bucket.barItems },
            { charts: bucket.others, items: bucket.otherItems },
            { charts: bucket.tables, items: bucket.tableItems },
          ]);
        }
      }
      // ★ 终极兜底：仅当 blueprint 槽位未显式声明（content_order[i] === undefined），
      //   才从 leftovers 抽一张兜底。蓝图中显式声明的"低密度稀疏图专用槽"
      //   （如 row4 第 3 槽 = bar_sparse）在没有稀疏图可填时，**不被泛型 leftovers
      //   强行填充**——否则会让「信息量小、不该占大槽的图」把无关热力图挤进窄槽，
      //   腾不出空间给本来该吃这槽的稀疏图。让该槽返回 null，由 validParts.filter
      //   + redistributeColumns 把剩余兄弟槽位按比例撑宽（如 [4,4] → [6,6]），
      //   实现用户诉求「旁边热力图自动拉宽占满格子」。
      if (!picked && exactBucket === undefined) {
        const leftovers = [
          ...bucket.fulls, ...bucket.heatmaps, ...bucket.heatmapWides, ...bucket.pies,
          ...bucket.lines, ...bucket.bars, ...bucket.barDenses, ...bucket.tables, ...bucket.others,
        ].filter((c) => !usedIds.has(c.slot));
        if (leftovers.length) {
          // 跨行去重：选第一张 chart_type 不在 rowUsedTypes 的图
          let chosen = leftovers[0];
          if (avoidDuplicate && rowUsedTypes.size) {
            const alt = leftovers.find((c) => !rowUsedTypes.has((c.chart_type || '').toLowerCase()));
            if (alt) chosen = alt;
          }
          picked = { chart: chosen, sizeClass: rowSize, item: undefined };
          usedIds.add(chosen.slot);
        }
      }
      if (picked && avoidDuplicate) {
        rowUsedTypes.add((picked.chart.chart_type || '').toLowerCase());
      }
      return picked;
    });

    // ★ 注入点③：缺图塌缩 + 列宽重归一化。
    //   若某槽取不到图 → 该列塌缩（删除），剩余有效槽按 12 列重新分配宽度，
    //   保证大屏不出现虚线空卡、也不留空洞。整行全缺 → 跳过该行（不渲染）。
    const validParts = picks
      .map((p, i) => ({ p, width: template[i] }))
      .filter((part) => part.p && part.width > 0);

    if (validParts.length === 0) {
      // 整行缺图：跳过（不生成任何 assignment，杜绝 grid 空行）
      continue;
    }

    // 重归一化宽度：按比例把 12 列分给有效槽，修正取整差（如 [3,6,3] 缺中间 → [6,6]）
    const totalOrig = validParts.reduce((s, part) => s + part.width, 0);
    const scaled = redistributeColumns(validParts.map((part) => part.width), 12);
    let colCursor = 1;
    validParts.forEach((part, vi) => {
      const width = scaled[vi];
      const picked = part.p!;
      const area = COL_AREA(row, colCursor, width);
      assignments.push({
        slot: picked.chart.slot,
        title: picked.item?.title || picked.chart.title || '',
        chartType: picked.chart.chart_type || '',
        sizeClass: picked.sizeClass,
        area,
        rowIndex: row,
        colIndex: colCursor,
      });
      colCursor += width;
    });
    // ★ 记录本行已用 chart_type 留作下一行跨行去重
    prevPrevRowTypes = prevRowTypes;
    prevRowTypes = assignments
      .filter((a) => a.rowIndex === row)
      .map((a) => (a.chartType || '').toLowerCase())
      .filter(Boolean);
  }

  // ★ 注入点②：溢出补行。蓝图装不下的图（权重最低的）按 6+6 追加到溢出区。
  //   因 POOL 已按 attention_weight 降序，这里对"剩余图"再按权重升序，
  //   确保权重最低者优先进溢出，权重高的 hero 始终留在主蓝图内。
  const remaining: ChartLike[] = [];
  const allCharts = [
    ...bucket.fulls, ...bucket.heatmaps, ...bucket.heatmapWides, ...bucket.pies,
    ...bucket.lines, ...bucket.bars, ...bucket.barDenses, ...bucket.tables, ...bucket.others,
  ];
  for (const c of allCharts) {
    if (!usedIds.has(c.slot)) remaining.push(c);
  }
  // 表格溢出时按 analysis_type 聚类（用户最新诉求：同业务模型表格相邻，不同业务间隔），
  //   非表格按 chart_type 分散后再按权重升序——权重低者先溢出。
  const isTable = (c: ChartLike) => bucket.tables.includes(c);
  const remainingTables = remaining.filter(isTable);
  const remainingNonTable = remaining.filter((c) => !isTable(c));

  // ★ 表格聚类：按 analysis_type 分组，组内按权重降序；不同 analysis_type 之间插入 1 个空行分隔。
  //   当所有表格都属于同一 analysis_type 时不会插入空行（保持紧凑）。
  //   ★ 关键修复：改用 businessGroupOf() 而非裸 analysis_type。
  //   后端对聚类 / RFM / 关联 / 流失等表格的 analysis_type 普遍返回 'default'，
  //   直接按 analysis_type 分组会让它们全部落入同一个 '__no_pkg__' 组，
  //   导致「不同业务模型的表格紧贴在一起、无法分隔」。
  //   businessGroupOf 会先取有效 analysis_type，无效时按标题关键词归类到
  //   rfm / cluster / correlation / cohort / funnel / ranking 等真实业务组。
  const tableGroupsMap = new Map<string, ChartLike[]>();
  for (const t of remainingTables) {
    const k = businessGroupOf(t);
    const arr = tableGroupsMap.get(k) || [];
    arr.push(t);
    tableGroupsMap.set(k, arr);
  }
  // 组内按 attention_weight 降序（业务价值高的表格优先显示）
  for (const [k, arr] of tableGroupsMap.entries()) {
    arr.sort((a, b) => weightOf(b, items) - weightOf(a, items));
  }
  // 组合并保持 analysis_type 出现顺序：第一次出现的 pkg 排在前面
  const seenGroups: string[] = [];
  const groupOrder: string[] = [];
  for (const t of remainingTables) {
    const k = businessGroupOf(t);
    if (!seenGroups.includes(k)) {
      seenGroups.push(k);
      groupOrder.push(k);
    }
  }
  const orderedTables: { chart: ChartLike; isFirstInGroup: boolean }[] = [];
  for (const k of groupOrder) {
    const arr = tableGroupsMap.get(k) || [];
    arr.forEach((c, idx) => orderedTables.push({ chart: c, isFirstInGroup: idx === 0 }));
  }
  // 仅当组数 > 1 时才在表格间插入空行，否则保持密集
  const insertTableSpacer = groupOrder.length > 1;

  remainingNonTable.sort((a, b) => weightOf(a, items) - weightOf(b, items)); // 升序：低权重先溢出

  // ★ 溢出区按用户指定的循环模式追加：严格 [12]→[4,4,4]→[6,6]→ 循环
  //   约束（用户明确要求）：
  //     - [3,3,3,3] 只出现在顶栏 KPI 小卡片（blueprint row 1），溢出区不再出现
  //     - [3,6,3]   只出现在核心三联（环形图 hero 占 6 列，blueprint row 2），溢出区不再出现
  //     - 其余一律走 12,4,4,4,6,6 循环
  //   - 整 [12] 行优先放表格（table 桶），保证明细表不会被密图淹没
  //   - 其它剩余图按上面循环；不够一整行也照样出，避免出现 1 槽独占 12 列的奇怪排版
  const OVERFLOW_PATTERN: number[][] = [
    [12],
    [4, 4, 4],
    [6, 6],
  ];
  const OVERFLOW_ROW_HEIGHT: Record<number, string> = {
    12: '360px',  // 全宽（表格/明细）
    6: '380px',   // 6 列
    4: '320px',   // 4 列
    3: '300px',   // 3 列
  };
  // 表格行高度单独再高一点，便于浏览
  const TABLE_ROW_HEIGHT = '420px';
  // 表格分组之间的「隔一行」（让不同 analysis_type 表格视觉上明显隔开）
  const TABLE_SPACER_HEIGHT = '24px';

  // 行高查找：先查蓝图，再查溢出
  const overflowRowHeights: Record<number, string> = {};
  let overflowRow = (blueprint[blueprint.length - 1]?.row || 1) + 1;
  let patternIdx = 0;

  // 第一轮：table 桶的图各占一个 [12] 整行（用户最新诉求：表格必须可见 + 同 analysis_type 相邻）
  //   不同 analysis_type 之间插入 spacer 行（高 24px），让"同一业务模型相邻、不同业务隔行"。
  // ★ 注意：插 spacer 时 assignment 不加图表，只加 rowHeight——grid_template_areas 缺省自动塌缩。
  let prevGroupKey: string | null = null;
  for (const { chart: ch, isFirstInGroup } of orderedTables) {
    const groupKey = businessGroupOf(ch);
    // ★ 跨组：插入 spacer 行（前一组与本组不同业务模型）
    // 注意：不能用 !isFirstInGroup 做条件——跨组时新组的首个元素恰好 isFirstInGroup=true，
    // 会导致 spacer 永远插不进去。只需比较前后组 key 即可。
    if (insertTableSpacer && prevGroupKey !== null && prevGroupKey !== groupKey) {
      overflowRowHeights[overflowRow] = TABLE_SPACER_HEIGHT;
      overflowRow += 1;
    }
    const area = COL_AREA(overflowRow, 1, 12);
    assignments.push({
      slot: ch.slot,
      title: ch.title || '',
      chartType: ch.chart_type || '',
      sizeClass: 'full',
      area,
      rowIndex: overflowRow,
      colIndex: 1,
    });
    overflowRowHeights[overflowRow] = TABLE_ROW_HEIGHT;
    usedIds.add(ch.slot);
    prevGroupKey = groupKey;
    overflowRow += 1;
  }
  // ★ 表格与下方非表格之间再插一个 spacer（视觉层级清晰，便于阅读）
  if (orderedTables.length > 0 && remainingNonTable.length > 0) {
    overflowRowHeights[overflowRow] = TABLE_SPACER_HEIGHT;
    overflowRow += 1;
  }

  // 第二轮：剩余非表图按循环模式摆放（每轮取一个 pattern，行高按行内最大列宽决定）
  // ★ 用户最新诉求：剩余「最后 1 张」时强制占 [12] 整行（避免落单图被挤进 4/6 列槽位被压扁）；
  //   剩余 ≥2 张仍按 [12]→[4,4,4]→[6,6] 严格循环布局。
  // ★ 新增：同类 chart_type 跨行分散（避免三连柱状图 / 三连线图审美疲劳）。
  // ★ 新增：当 pattern cols 数 > 剩余图数，自动降级到能填满 12 列的子集（无空洞）。
  let pi = 0;
  const recentTypeHistory: string[] = []; // 记录最近行内 chart_type，用于跨行去重
  while (pi < remainingNonTable.length) {
    const remainingCount = remainingNonTable.length - pi;
    // ★ 最后 1 张：单独成行 [12]，避免被挤进 4/6 列后看不清
    let cols: number[];
    if (remainingCount === 1) {
      cols = [12];
    } else {
      cols = OVERFLOW_PATTERN[patternIdx % OVERFLOW_PATTERN.length];
      patternIdx += 1;
      // ★ cols 长度 > remaining 时降级：3 槽 [4,4,4] 若仅剩 2 张 → 截断为 [6,6]；仅剩 1 张 → [12]
      while (cols.length > remainingCount && cols.length > 1) {
        if (cols.length === 3) cols = [6, 6];
        else if (cols.length === 2) cols = [12];
        else break;
      }
    }
    let col = 1;
    let maxWidth = 0;
    let placed = 0;
    const rowTypes: string[] = [];
    let cursor = pi;
    for (let ci = 0; ci < cols.length && cursor < remainingNonTable.length; ci++) {
      // ★ 跨行去重：若当前 cols[ci] 有多张同类候选，优先挑 chart_type 与最近一行不同的图
      const width = cols[ci];
      let pickIdx = cursor;
      if (ci > 0 && rowTypes.length > 0) {
        const usedInRow = new Set(rowTypes);
        // 在剩余池中找一张 chart_type 不在已用集合内、且未占用、且与最近一行也不全相同的图
        for (let j = cursor; j < remainingNonTable.length; j++) {
          const cT = (remainingNonTable[j].chart_type || '').toLowerCase();
          if (!usedInRow.has(cT) && !recentTypeHistory.slice(-2).every((t) => t === cT)) {
            pickIdx = j;
            break;
          }
        }
      }
      const ch = remainingNonTable.splice(pickIdx, 1)[0];
      usedIds.add(ch.slot);
      maxWidth = Math.max(maxWidth, width);
      const area = COL_AREA(overflowRow, col, width);
      const sizeClass: 'kpi' | 'wide' | 'full' = width === 12 ? 'full' : 'wide';
      assignments.push({
        slot: ch.slot,
        title: ch.title || '',
        chartType: ch.chart_type || '',
        sizeClass,
        area,
        rowIndex: overflowRow,
        colIndex: col,
      });
      rowTypes.push((ch.chart_type || '').toLowerCase());
      col += width;
      placed += 1;
      // ★ 用 cursor 跟踪剩余位置（不被 splice 影响）
      if (pickIdx === cursor) {
        cursor += 1;
      }
      // 当 pickIdx > cursor（交换前位），cursor 维持不变；下一个槽位从 cursor 开始扫描
      // 但因 splice 移除了 pickIdx 位置之后的所有元素索引左移，所以 cursor 不需要递增
      pi = cursor;
    }
    if (placed > 0) {
      overflowRowHeights[overflowRow] = OVERFLOW_ROW_HEIGHT[maxWidth] || '360px';
      // 把本行 chart_type 记入历史（仅非空 type），最多保留 8 条
      recentTypeHistory.push(...rowTypes.filter(Boolean));
      while (recentTypeHistory.length > 8) recentTypeHistory.shift();
      overflowRow += 1;
    } else {
      break;
    }
  }

  // ★ 生成 gridTemplateAreas + rowHeights
  //   maxRow 同时考虑 assignments 与 overflowRowHeights（spacer 行高有，但可能没 assignments），
  //   确保 spacer 在 gridTemplateAreas 中也有对应行（保持行号 ↔ 行高一一对应）。
  const maxRow = Math.max(
    assignments.reduce((mx, a) => Math.max(mx, a.rowIndex), 0),
    Object.keys(overflowRowHeights).reduce((mx, k) => Math.max(mx, parseInt(k)), 0),
    1
  );

  // ★ 最后一行空缺自适应拉伸（用户最新诉求）：
  //   当最后渲染行（rowIndex === maxRow）的总列宽 < 12（存在空槽空缺）时，
  //   把缺口补到「离空槽最近的卡片」——即该行最后一张有效卡片，让它吃满剩余列宽。
  //   例如 [4,4,4] 只填了 2 张 → 有效 [4,4] 缺 4 列 → 末张变 8 → [4,8] 填满整行。
  //   单张图 → [12]；[6,6] 缺 1 → [6,6]（已满不处理）。
  //   此逻辑在最末尾统一执行，不再前置 branch 限制，覆盖主蓝图末行 / 溢出末行所有场景。
  const widthOfArea = (area: string) => {
    const mm = area.match(/s(\d+)/);
    return mm ? parseInt(mm[1]) : 0;
  };
  const lastRowAssignments = assignments.filter((a) => a.rowIndex === maxRow);
  if (lastRowAssignments.length > 0) {
    const lastA = lastRowAssignments[lastRowAssignments.length - 1];
    const oldW = widthOfArea(lastA.area);
    // 末张保持原位（colIndex 不变），宽度撑到"整行剩余可用列"：
    // newW = 12 - (起始列 - 1)，确保本行从第一列到最后一列被完全填满。
    // 例：[4,4] → 末张 colIndex=5 → newW=8 → [4,8]；单张 colIndex=1 → 12 → [12]。
    const newW = 12 - (lastA.colIndex - 1);
    if (newW > oldW) {
      lastA.area = `r${maxRow}c${lastA.colIndex}s${newW}`;
    }
  }

  const rows: string[][] = Array.from({ length: maxRow }, () => Array(12).fill('.'));
  for (const a of assignments) {
    const w = widthOfArea(a.area);
    for (let j = 0; j < w; j++) {
      rows[a.rowIndex - 1][a.colIndex + j - 1] = a.area;
    }
  }
  const gridTemplateAreas = rows.map((r) => `"${r.join(' ')}"`).join(' ');
// ★ 兜底高度使用 blueprint 最后一行同款 px，彻底避免 fr 单位被内容反撑
const lastBlueprintRow = blueprint[blueprint.length - 1];
const fallbackRowHeight = (lastBlueprintRow?.height && /\d/.test(lastBlueprintRow.height))
  ? lastBlueprintRow.height
  : '360px';
const rowHeights = Array.from({ length: maxRow }, (_, i) => {
  const idx = i + 1;
  return (
    blueprint.find((b) => b.row === idx)?.height
    || overflowRowHeights[idx]
    || fallbackRowHeight
  );
}).join(' ');

  return {
    gridTemplateAreas,
    rowHeights,
    assignments,
    rowCount: maxRow,
  };
}

/**
 * 从 saved_packages 中提取所有图表 + KPI，构建 SmartLayoutChart[] 与对应 items。
 * 完全复用真实大屏的数据，与 5 模板的图表来源一致（pkg.rendered_charts）。
 */
function extractChartsFromSavedPackages(packages: any[]): {
  charts: SmartLayoutChart[]; items: SmartLayoutItem[];
} {
  const charts: SmartLayoutChart[] = [];
  const items: SmartLayoutItem[] = [];

  packages.forEach((pkg: any, pkgIdx: number) => {
    // 图表（含可能的 metric 类图表）——slot 必须全局唯一，KPI 识别交给 isMetricChart
    const pkgCharts = pkg.rendered_charts || pkg.charts || [];
    pkgCharts.forEach((c: any, i: number) => {
      if (!c) return;
      const chartType = (c.chart_type || '').toLowerCase();
      const slotId = `c_${pkgIdx}_${i}`;
      const chart: SmartLayoutChart = {
        slot: slotId,
        title: c.title || '',
        chart_type: chartType || 'unknown',
        option: c.option || null,
        table_data: c.table_data || null,
        raw_data: c.raw_data || c.data || null,
        x: c.x || '',
        y: c.y || '',
        analysis_type: pkg.analysis_type || '',
      };
      charts.push(chart);
      items.push({
        slot: slotId,
        slot_id: slotId,
        chart_type: chartType || 'unknown',
        title: c.title || '',
        // ★ 优先用后端传来的 attention_weight / business_value（来自 importance_engine 评分），
        //   没传才按 metric=0.9 / 其他=0.6 兜底——保证业务价值高的图优先 hero 槽
        attention_weight:
          (typeof c.attention_weight === 'number' ? c.attention_weight : null)
          ?? (typeof c.business_value === 'number' ? c.business_value : null)
          ?? (isMetricChart(chart) ? 0.9 : 0.6),
      });
    });

    // ★ 表格（来自 pkg.tables）——也必须有 slot，才能进入 layout
    const pkgTables = pkg.tables || [];
    pkgTables.forEach((t: any, i: number) => {
      if (!t) return;
      const slotId = `t_${pkgIdx}_${i}`;
      // 兼容多种表格数据结构：columns/rows(header/data)、table_data、raw_data
      const td = t.table_data || {};
      const columns = td.columns || t.columns || [];
      const rows = td.rows || t.rows || t.data || [];
      const header = td.header || t.header || columns;
      const data = td.data || t.data || rows;
      const tableData = {
        columns: Array.isArray(columns) && columns.length ? columns : header,
        rows: Array.isArray(rows) && rows.length ? rows : data,
        table_type: t.table_type || td.table_type || 'data',
      };
      const chart: SmartLayoutChart = {
        slot: slotId,
        title: t.title || '数据表格',
        chart_type: 'table',
        option: t.option || null,
        table_data: tableData,
        raw_data: rows.length ? rows : data,
        x: '',
        y: '',
        analysis_type: pkg.analysis_type || '',
        attention_weight: typeof t.attention_weight === 'number' ? t.attention_weight : 0.55,
      };
      charts.push(chart);
      items.push({
        slot: slotId,
        slot_id: slotId,
        chart_type: 'table',
        title: t.title || '数据表格',
        attention_weight: typeof t.attention_weight === 'number' ? t.attention_weight : 0.55,
      });
    });

    // KPI（来自 rendered_kpis 或 kpis）→ 转成 metric 图表，slot 同样全局唯一
    const pkgKpis = pkg.rendered_kpis || pkg.kpis || [];
    pkgKpis.forEach((k: any, i: number) => {
      if (!k) return;
      const label = k.label || '';
      const value = k.formatted ?? k.value ?? '';
      const change = k.change || '';
      // ★ 业务价值透传：来自后端 render_kpis 的 business_value 评分
      //   让高价值 KPI（GMV/利润/客单价等）优先占据 4 个 [3,3,3,3] 槽位
      const bv = typeof k.business_value === 'number' ? k.business_value : 0.9;
      const option: any = {
        kind: 'metric',
        label,
        value: String(value),
        change,
        kpi_type: k.kpi_type || 'sum',
        business_value: bv,
      };
      const slotId = `k_${pkgIdx}_${i}`;
      const chart: SmartLayoutChart = {
        slot: slotId,
        title: label,
        chart_type: 'metric',
        option,
        table_data: null,
        raw_data: null,
        x: '',
        y: '',
        analysis_type: pkg.analysis_type || '',
        business_value: bv,
        // ★ 关键：用 business_value 取代硬编码 0.9，
        //   让 sortByWeight 真正按业务价值降序选 hero KPI
        attention_weight: bv,
      };
      charts.push(chart);
      items.push({
        slot: slotId,
        slot_id: slotId,
        chart_type: 'metric',
        title: label,
        attention_weight: bv,
      });
    });
  });

  return { charts, items };
}

export default function SmartDashboard({ sessionId, mock, mode }: SmartDashboardProps) {
  const [data, setData] = useState<{ charts: SmartLayoutChart[]; items: SmartLayoutItem[] } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [localMode, setLocalMode] = useState<'A' | 'B' | 'C'>(() => {
    if (mode === 'A' || mode === 'B' || mode === 'C') return mode;
    const m = new URLSearchParams(window.location.search).get('mode')?.toUpperCase();
    return m === 'B' || m === 'C' ? m : 'A';
  });

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      let packages: any[] = [];
      if (mock) {
        // ★ 模拟大屏：仅用第一包渲染（单包 ~10 张刚好匹配三模式蓝图槽位，
        //   避免 78 张图溢出到 overflowRow 撑爆布局）。三模式切换在工具条里即可预览。
        packages = (MOCK_PACKAGES as unknown as any[]).slice(0, 1);
      } else {
        if (!sessionId) {
          setError('缺少会话 ID，请先在「数据上传」页面上传数据');
          return;
        }
        // ★ 真实大屏：严格只读取用户已保存的分析包（saved_packages）
        const res: any = await api.getSavedPackages(sessionId);
        packages = (res && res.packages) || [];
      }
      if (packages.length === 0) {
        setError(
          mock
            ? '示例数据加载失败'
            : '暂无可视化内容，请先在「数据分析」页生成并收藏分析图表'
        );
        return;
      }
      const { charts, items } = extractChartsFromSavedPackages(packages);
      console.log('[SmartDashboard] 从 saved_packages 加载:', {
        packagesLen: packages.length,
        chartsLen: charts.length,
        itemsLen: items.length,
        chartTypeHistogram: charts.reduce<Record<string, number>>((acc, c) => {
          const k = (c.chart_type || '<空>').toString();
          acc[k] = (acc[k] || 0) + 1; return acc;
        }, {}),
        tableLikeCandidates: charts
          .filter((c) => /表|表格|明细|列表|清单|table|tabular|grid|cohort|retention|留存|同期群|同环比|行为/.test((c.title || '') + ' ' + (c.chart_type || '')))
          .map((c) => ({ slot: c.slot, type: c.chart_type, title: c.title, hasTableData: !!c.table_data, hasOption: !!c.option })),
      });
      setData({ charts, items });
    } catch (err) {
      const msg = err instanceof Error ? err.message : '加载已保存分析包失败';
      console.error('[SmartDashboard] 加载失败:', msg);
      setError(`加载失败：${msg}`);
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    load();
  }, [load]);

  // 按模式重新分配 slot + 直接生成 layout（语义化分配，绕开 computeLayout 蓝图）
  const remappedData = useMemo(() => {
    if (!data) return null;
    // ★ 直接把原始 data 交给 buildSemanticLayout；它内部会按 chart_type/title
    //   语义选择槽位（如 heatmap→6列、line→3列、kpi→顶栏等），
    //   并保证每个 chart 只被分配一次、slot 永不重复。
    const layoutResult = buildSemanticLayout(
      (data.charts || []) as ChartLike[],
      (data.items || []) as SmartLayoutItem[],
      localMode
    );
    return {
      charts: data.charts as SmartLayoutChart[],
      items: data.items as SmartLayoutItem[],
      layout: layoutResult,
    };
  }, [data, localMode]);

  const chartMap = useMemo(() => {
    const m: Record<string, SmartLayoutChart> = {};
    if (!remappedData) return m;
    (remappedData.charts || []).forEach((c) => {
      if (c && c.slot) m[c.slot] = c;
    });
    return m;
  }, [remappedData]);

  const layout = remappedData?.layout || null;

  // 诊断
  useEffect(() => {
    if (!layout || !remappedData) return;
    const slots = (remappedData.charts || []).map((c: any) => c.slot);
    const itemSlots = (remappedData.items || []).map((it: any) => it.slot);
    const missing = layout.assignments.filter((a: any) => !chartMap[a.slot]).map((a: any) => a.slot);
    const seen = new Set<string>();
    const dup: string[] = [];
    for (const s of [...itemSlots, ...slots]) {
      if (seen.has(s)) dup.push(s);
      seen.add(s);
    }
    console.log('[SmartDashboard:diagnostics]', {
      mode: localMode,
      chartsLen: (remappedData.charts || []).length,
      itemsLen: (remappedData.items || []).length,
      assignments: layout.assignments.length,
      missingAssignments: missing,
      duplicateSlots: Array.from(new Set(dup)),
      rowHeights: layout.rowHeights,
    });
  }, [layout, remappedData, chartMap, localMode]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex flex-col items-center gap-3 text-slate-300">
          <div className="w-9 h-9 rounded-full border-2 border-[#8B5CF6] border-t-transparent animate-spin" />
          <span className="text-sm">加载真实已保存图表…</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="max-w-md text-center space-y-3 p-8 rounded-2xl bg-white/40 border border-white/50">
          <FiAlertTriangle className="w-8 h-8 mx-auto text-amber-500" />
          <p className="text-sm text-slate-600">{error}</p>
          <button onClick={() => load()}
            className="px-4 py-2 text-xs rounded-lg bg-white/60 border border-white/60 hover:bg-white/80 transition-colors">
            重试
          </button>
        </div>
      </div>
    );
  }

  if (!remappedData || !layout || layout.assignments.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-slate-400 text-sm">
        暂无图表可排版。
      </div>
    );
  }

  return (
    <div className="relative w-full" style={{ minHeight: '100%' }}>
      {/* 工具条：来源提示 + 三模式切换 */}
      <div className="sticky top-0 z-10 flex justify-between items-center px-4 py-3"
        style={{
          background: 'rgba(255,255,255,0.45)',
          backdropFilter: 'blur(10px)',
          WebkitBackdropFilter: 'blur(10px)',
          borderBottom: '1px solid rgba(255,255,255,0.5)',
        }}
      >
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-[12px] text-slate-600">
            <FiCpu className="w-3.5 h-3.5 text-violet-500" />
            {mock
              ? `模拟大屏 · 示例数据预览 · ${remappedData.charts.length} 张`
              : `真实大屏 · 已保存图表 · ${remappedData.charts.length} 张`}
          </div>
          <div className="flex items-center gap-1 rounded-lg bg-white/50 border border-white/60 p-0.5 backdrop-blur-md">
            {(['A', 'B', 'C'] as const).map((mm) => (
              <button
                key={mm}
                onClick={() => setLocalMode(mm)}
                className={`px-2.5 py-1 text-[11px] rounded-md transition-colors ${
                  localMode === mm
                    ? 'bg-violet-500 text-white shadow-sm'
                    : 'text-slate-600 hover:bg-white/80'
                }`}
                title={`模式${mm}：${mm === 'A' ? '核心聚拢式（图1）' : mm === 'B' ? '上图下表式（图2）' : '宽幅压顶式（图3）'}`}
              >
                {mm === 'A' ? '模式A 聚拢' : mm === 'B' ? '模式B 上下' : '模式C 压顶'}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 主网格 */}
      <div
        className="grid gap-3 p-4 w-full mx-auto"
        style={{
          gridTemplateAreas: layout.gridTemplateAreas,
          gridTemplateRows: layout.rowHeights,
          gridTemplateColumns: 'repeat(12, minmax(0, 1fr))',
          gridAutoRows: '360px', // ★ 兜底：即便 maxRow 算少也不会出现 auto 行
          overflow: 'visible',
          maxWidth: '1920px',
        }}
      >
        {(() => {
          // ★ 防御：computeLayout 可能因上游 slot 重复产出相同 slot 的 assignment，
          //   这里按 slot 去重，保证 React key 绝对唯一（避免 duplicate key 报错）。
          const seenSlots = new Set<string>();
          return layout.assignments.map((a) => {
            if (seenSlots.has(a.slot)) return null;
            seenSlots.add(a.slot);
            const chart = chartMap[a.slot];
            // ★ 占位格子：蓝图每槽必占，缺图时画一个 no-data 占位框，不留空白
            if (!chart || (a as any).placeholder) {
              return (
                <div
                  key={a.slot}
                  style={{
                    gridArea: a.area,
                    minHeight: 0,
                    minWidth: 0,
                    height: '100%',
                    maxHeight: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    overflow: 'hidden',
                  }}
                  className="rounded-xl bg-white/35 border border-dashed border-white/50"
                >
                  <span className="text-[11px] text-slate-400">— 暂无图表 —</span>
                </div>
              );
            }
            return (
              <div
                key={a.slot}
                style={{
                  gridArea: a.area,
                  minHeight: 0,
                  minWidth: 0,
                  // ★ 关键：固定 height/maxHeight，避免父级 fr / 内容反撑
                  height: '100%',
                  maxHeight: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  overflow: 'hidden',
                }}
                className="rounded-xl overflow-hidden bg-white/55 border border-white/60 backdrop-blur-md shadow-sm"
              >
                <ChartErrorBoundary slot={a.slot} chartType={a.chartType}>
                  <div className="w-full flex-1 min-h-0 min-w-0">
                    {renderSmartChart(chart)}
                  </div>
                </ChartErrorBoundary>
              </div>
            );
          });
        })()}
      </div>
    </div>
  );
}
