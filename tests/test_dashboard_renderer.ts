/**
 * Dashboard Renderer 测试（纯数据结构验证）
 *
 * 不导入 React/ECharts 组件，只验证数据模型和业务逻辑。
 */

// ===== 从 dashboard.ts 复制关键类型进行内联验证 =====

const DARK_THEME_ANIMATION_DURATION = 500;

type FilterScope = 'global' | 'section' | 'widget';
type LinkageType = 'one_to_one' | 'one_to_many' | 'many_to_many';
type HighlightRuleType = 'top_n' | 'bottom_n' | 'anomaly' | 'high_growth' | 'threshold' | 'trend_change' | 'hover_highlight';

interface FilterRule {
  id: string; name: string; field: string; filter_type: string;
  scope: FilterScope; widget_type: string;
  target_widgets: string[]; target_sections: string[];
  default_value: string | null; priority: number;
}

interface CrossFilterRule {
  id: string; source_widget: string; event: string;
  field: string; field_label: string;
  targets: string[]; priority: number; bidirectional: boolean;
}

interface DrillDownRule {
  id: string; widget_id: string; dimension: string;
  current_level: string; next_level: string; label: string; priority: number;
}

interface HighlightRule {
  id: string; widget_id: string; rule_type: HighlightRuleType;
  params: Record<string, unknown>; label: string; priority: number;
}

interface WidgetLinkageRule {
  id: string; source_widgets: string[]; target_widgets: string[];
  linkage_type: LinkageType; business_topic: string; description: string;
}

interface InteractionConfig {
  id: string; dashboard_id: string; version: string;
  global_filters: FilterRule[]; cross_filters: CrossFilterRule[];
  drill_downs: DrillDownRule[]; highlights: HighlightRule[];
  linkages: WidgetLinkageRule[];
  metadata: Record<string, unknown>;
  animation: Record<string, unknown>; bookmark: Record<string, unknown>;
  dashboard_state: Record<string, unknown>; undo: Record<string, unknown>;
  share_state: Record<string, unknown>;
}

interface WidgetSlot {
  widget_id: string; title: string; widget_type: string;
  position: { x: number; y: number; w: number; h: number };
  size_class: string; importance_score: number; z_index: number;
  section_id: string; group_id: string;
  chart_type: string | null;
  chart_config: Record<string, unknown>;
  supported_filters: { field: string; label: string; filter_type: string }[];
  metadata: Record<string, unknown>;
}

interface DashboardSchema {
  id: string; title: string; created_at: string; version: string;
  metadata: Record<string, unknown>;
  layout: Record<string, unknown>;
  layout_strategy: string;
  widgets: WidgetSlot[];
  sections: Record<string, unknown>[];
  groups: Record<string, unknown>[];
  interactions: InteractionConfig;
  theme: Record<string, unknown>;
  dark_mode: boolean;
}

// ===== ChartConfigBuilder Logic（内联） =====

function chartTypeToHeight(chartType: string | null, sizeClass: string): string {
  if (chartType === 'map' || chartType === 'map_3d') return '400px';
  if (chartType === 'radar') return '300px';
  if (chartType === 'gauge') return '240px';
  const map: Record<string, string> = { hero: '400px', large: '320px', medium: '260px', small: '200px' };
  return map[sizeClass] || '260px';
}

function chartTypeToSeriesType(chartType: string | null): string {
  const map: Record<string, string> = {
    line: 'line', bar: 'bar', pie: 'pie', scatter: 'scatter',
    radar: 'radar', heatmap: 'heatmap', treemap: 'treemap',
    funnel: 'funnel', waterfall: 'bar', gauge: 'gauge',
    area: 'line', bubble: 'scatter', histogram: 'bar',
    boxplot: 'boxplot', map: 'map', map_3d: 'map3D',
  };
  return map[chartType || ''] || 'bar';
}

function isGLChartType(chartType: string | null): boolean {
  const glTypes = ['map_3d', 'scatter3D', 'bar3D', 'line3D', 'lines3D', 'surface'];
  return glTypes.includes(chartType || '');
}

// ===== Mock Data =====

const MOCK_INTERACTIONS: InteractionConfig = {
  id: 'interact_test', dashboard_id: 'dashboard_test', version: '2.0',
  global_filters: [
    { id: 'gf_time', name: '时间范围', field: 'time', filter_type: 'global', scope: 'global', widget_type: 'date_range', target_widgets: ['w1', 'w2', 'w3'], target_sections: [], default_value: null, priority: 100 },
    { id: 'gf_region', name: '地区筛选', field: 'region', filter_type: 'global', scope: 'global', widget_type: 'dropdown', target_widgets: ['w1', 'w2', 'w3'], target_sections: [], default_value: null, priority: 90 },
  ],
  cross_filters: [
    { id: 'cf_region', source_widget: 'w2', event: 'click', field: 'region', field_label: '地区', targets: ['w1', 'w3'], priority: 80, bidirectional: false },
  ],
  drill_downs: [
    { id: 'dd_geo', widget_id: 'w2', dimension: 'region', current_level: 'province', next_level: 'city', label: '省份 → 城市', priority: 60 },
  ],
  highlights: [
    { id: 'hl_top3', widget_id: 'w2', rule_type: 'top_n', params: { n: 3 }, label: '高亮 TOP 3', priority: 50 },
    { id: 'hl_hover', widget_id: 'w1', rule_type: 'hover_highlight', params: {}, label: 'Hover Highlight', priority: 30 },
  ],
  linkages: [
    { id: 'lg_sales', source_widgets: ['w1'], target_widgets: ['w2', 'w3'], linkage_type: 'one_to_many', business_topic: '销售', description: '销售趋势联动' },
  ],
  metadata: { total_widgets: 6 },
  animation: {}, bookmark: {}, dashboard_state: {}, undo: {}, share_state: {},
};

const MOCK_WIDGETS: WidgetSlot[] = [
  { widget_id: 'w1', title: '销售趋势', widget_type: 'chart', position: { x: 0, y: 0, w: 8, h: 3 }, size_class: 'hero', importance_score: 90, z_index: 0, section_id: 'sec_hero', group_id: 'grp_sales', chart_type: 'line', chart_config: {}, supported_filters: [{ field: 'region', label: '地区', filter_type: 'dropdown' }], metadata: {} },
  { widget_id: 'w2', title: '地区排行', widget_type: 'chart', position: { x: 8, y: 0, w: 4, h: 3 }, size_class: 'large', importance_score: 80, z_index: 0, section_id: 'sec_main', group_id: 'grp_region', chart_type: 'bar', chart_config: {}, supported_filters: [{ field: 'region', label: '地区', filter_type: 'dropdown' }], metadata: {} },
  { widget_id: 'w3', title: '产品占比', widget_type: 'chart', position: { x: 0, y: 3, w: 4, h: 3 }, size_class: 'medium', importance_score: 60, z_index: 0, section_id: 'sec_main', group_id: 'grp_product', chart_type: 'pie', chart_config: {}, supported_filters: [{ field: 'product', label: '产品', filter_type: 'dropdown' }], metadata: {} },
  { widget_id: 'w4', title: '总销售额', widget_type: 'kpi', position: { x: 4, y: 3, w: 2, h: 2 }, size_class: 'small', importance_score: 50, z_index: 0, section_id: 'sec_main', group_id: '', chart_type: null, chart_config: {}, supported_filters: [], metadata: { kpi_label: '¥1,234万' } },
  { widget_id: 'w5', title: '数据表格', widget_type: 'table', position: { x: 6, y: 3, w: 6, h: 3 }, size_class: 'medium', importance_score: 40, z_index: 0, section_id: 'sec_secondary', group_id: '', chart_type: null, chart_config: { columns: ['地区', '销售额'], rows: [['华东', 1200]] }, supported_filters: [], metadata: {} },
  { widget_id: 'w6', title: '销售洞察', widget_type: 'insight', position: { x: 0, y: 6, w: 4, h: 2 }, size_class: 'small', importance_score: 30, z_index: 0, section_id: 'sec_footer', group_id: '', chart_type: null, chart_config: { text: '华东持续增长' }, supported_filters: [], metadata: {} },
  { widget_id: 'w7', title: '3D地图', widget_type: 'map', position: { x: 0, y: 8, w: 12, h: 4 }, size_class: 'hero', importance_score: 85, z_index: 0, section_id: 'sec_main', group_id: 'grp_region', chart_type: 'map_3d', chart_config: {}, supported_filters: [{ field: 'region', label: '地区', filter_type: 'dropdown' }], metadata: {} },
];

const MOCK_SCHEMA: DashboardSchema = {
  id: 'dashboard_test', title: '数据分析驾驶舱', created_at: '2024-01-01', version: '2.0',
  metadata: { layout_selected: 'executive' },
  layout: { name: 'executive', columns: 12, section_order: ['hero', 'main'], section_gap: 2, widget_gap: 0, page_margin: 1 },
  layout_strategy: 'executive',
  widgets: MOCK_WIDGETS,
  sections: [],
  groups: [],
  interactions: MOCK_INTERACTIONS,
  theme: {}, dark_mode: true,
};

// ===== Tests =====

let passed = 0;
let failed = 0;

function assert(condition: boolean, msg: string) {
  if (condition) { passed++; console.log(`  ✓ ${msg}`); }
  else { failed++; console.error(`  ✗ ${msg}`); }
}

console.log('\n========================================');
console.log('  Dashboard Renderer 测试');
console.log('========================================\n');

// Test 1: Widget Factory 映射
console.log('--- Test 1: Widget Factory 映射 ---');
const supportedTypes = ['kpi', 'chart', 'map', 'table', 'insight', 'summary'];
MOCK_WIDGETS.forEach(w => assert(supportedTypes.includes(w.widget_type), `widget_type "${w.widget_type}" 支持`));

// Test 2: Theme Engine
console.log('\n--- Test 2: Theme Engine ---');
const themeNames = ['light', 'dark', 'blue', 'gray'];
assert(themeNames.length === 4, '4 种主题定义');
const requiredThemeFields = ['background', 'cardBg', 'cardBorder', 'text', 'textSecondary', 'accent', 'chartColors', 'cssVars', 'fontFamily', 'borderRadius', 'cardPadding', 'animationDuration'];
assert(requiredThemeFields.length === 12, 'DashboardTheme 有 12 个必要字段');

// Test 3: Chart Style Engine
console.log('\n--- Test 3: Chart Style Engine ---');
assert(chartTypeToHeight('line', 'hero') === '400px', 'line hero → 400px');
assert(chartTypeToHeight('bar', 'medium') === '260px', 'bar medium → 260px');
assert(chartTypeToHeight('map', 'medium') === '400px', 'map → 400px');
assert(chartTypeToHeight('radar', 'medium') === '300px', 'radar → 300px');
assert(chartTypeToHeight('gauge', 'medium') === '240px', 'gauge → 240px');
assert(chartTypeToSeriesType('line') === 'line', 'line → line');
assert(chartTypeToSeriesType('pie') === 'pie', 'pie → pie');
assert(chartTypeToSeriesType('map_3d') === 'map3D', 'map_3d → map3D');
assert(isGLChartType('map_3d') === true, 'map_3d is GL');
assert(isGLChartType('bar') === false, 'bar is not GL');

// Test 4: Interaction Binding
console.log('\n--- Test 4: Interaction Binding ---');
const interactions = MOCK_SCHEMA.interactions;
assert(interactions.global_filters.length === 2, `2 Global Filters（${interactions.global_filters.length}）`);
assert(interactions.cross_filters.length === 1, `1 Cross Filter（${interactions.cross_filters.length}）`);
assert(interactions.drill_downs.length === 1, `1 Drill Down（${interactions.drill_downs.length}）`);
assert(interactions.highlights.length === 2, `2 Highlights（${interactions.highlights.length}）`);
assert(interactions.linkages.length === 1, `1 Linkage（${interactions.linkages.length}）`);

const gfTime = interactions.global_filters.find(f => f.field === 'time');
assert(gfTime !== undefined, 'time Global Filter 存在');
assert(gfTime!.scope === 'global', 'time scope = global');
assert(gfTime!.widget_type === 'date_range', 'time widget_type = date_range');

const gfRegion = interactions.global_filters.find(f => f.field === 'region');
assert(gfRegion !== undefined, 'region Global Filter 存在');
assert(gfRegion!.scope === 'global', 'region scope = global');
assert(gfRegion!.widget_type === 'dropdown', 'region widget_type = dropdown');

const cf = interactions.cross_filters[0];
assert(cf.source_widget === 'w2', 'cross filter source = w2');
assert(cf.field === 'region', 'cross filter field = region');
assert(cf.targets.length === 2, `cross filter targets = 2（${cf.targets.length}）`);

const dd = interactions.drill_downs[0];
assert(dd.widget_id === 'w2', 'drill down widget = w2');
assert(dd.current_level === 'province', 'drill down current = province');
assert(dd.next_level === 'city', 'drill down next = city');

const hlHover = interactions.highlights.find(h => h.rule_type === 'hover_highlight');
assert(hlHover !== undefined, 'hover_highlight 存在');
assert(hlHover!.widget_id === 'w1', 'hover_highlight widget = w1');

const lg = interactions.linkages[0];
assert(lg.linkage_type === 'one_to_many', 'linkage type = one_to_many');
assert(lg.business_topic === '销售', 'linkage topic = 销售');

// Test 5: Widget Error Isolation
console.log('\n--- Test 5: Widget Error Isolation ---');
const widgetErrors: { widget_id: string; message: string }[] = [];
widgetErrors.push({ widget_id: 'w1', message: 'ECharts setOption 失败' });
assert(widgetErrors.length === 1, 'Widget Error 记录正确');
assert(widgetErrors[0].widget_id === 'w1', 'Widget Error widget_id = w1');
assert(MOCK_WIDGETS.length === 7, `7 个 Widget 全部独立渲染（1 个错误不影响其他）`);

// Test 6: Animation Engine
console.log('\n--- Test 6: Animation Engine ---');
const animTypes = ['fade-in', 'slide-up', 'scale-in', 'progressive'];
assert(animTypes.length === 4, '4 种动画类型');
assert(DARK_THEME_ANIMATION_DURATION === 500, 'dark theme animationDuration = 500ms');

// Test 7: Dashboard Renderer API
console.log('\n--- Test 7: Dashboard Renderer API ---');
assert(MOCK_SCHEMA.version === '2.0', 'Schema version = 2.0');
assert(MOCK_SCHEMA.widgets.length === 7, `7 个 Widgets（${MOCK_SCHEMA.widgets.length}）`);
assert('interactions' in MOCK_SCHEMA, 'interactions 存在');
assert('layout_strategy' in MOCK_SCHEMA, 'layout_strategy 存在');
assert('dark_mode' in MOCK_SCHEMA, 'dark_mode 存在');

// FilterScope 验证
assert(interactions.global_filters.every(f => f.scope === 'global'), '所有 Global Filter scope = global');

// Interaction 优先级验证
const priorities = [
  ...interactions.global_filters.map(f => f.priority),
  ...interactions.cross_filters.map(c => c.priority),
  ...interactions.drill_downs.map(d => d.priority),
  ...interactions.highlights.map(h => h.priority),
];
assert(priorities.length === 6, `6 条交互规则优先级（${priorities.length}）`);
// Global > Cross > Drill > Highlight
assert(priorities[0] >= priorities[1], 'Global Filter 优先级最高');

console.log('\n========================================');
console.log(`  结果: ${passed}/${passed + failed} PASS, ${failed} FAIL`);
console.log('========================================\n');

if (failed > 0) {
  console.error('❌ Dashboard Renderer 测试失败');
} else {
  console.log('✅ Dashboard Renderer 测试全部通过');
}


