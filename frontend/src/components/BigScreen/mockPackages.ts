/**
 * 模拟大屏（/dashboard?mock=1）专用示例分析包。
 *
 * ★ 完全独立于真实大屏的数据源（saved_packages），不依赖后端、不依赖用户上传。
 *   仅在 mock 模式下注入，用于预览三种排版模式（A 聚拢 / B 上下 / C 压顶）的效果。
 *
 * 数据结构与 SmartDashboard.extractChartsFromSavedPackages 期望的 AnalysisPackage 一致：
 *   - rendered_charts: [{ title, chart_type, option, raw_data, table_data }]
 *   - rendered_kpis:   [{ label, value, formatted, change, kpi_type }]
 *
 * ★ 只使用有「仙气组件」对应的图表类型（heatmap / pie / line / bar / ranking /
 *   funnel / table / dual_axis / hbar / bubble），避免出现 ECharts 默认丑陋兜底图。
 * ★ 单包图表控制在 14 张内（与三模式大屏蓝图槽位容量匹配），避免溢出到布局之外。
 */

type ChartType = 'heatmap' | 'pie' | 'line' | 'bar' | 'ranking' | 'funnel' | 'table' | 'dual_axis' | 'hbar' | 'bubble';

interface MockChart {
  title: string;
  chart_type: ChartType;
  option?: Record<string, unknown> | null;
  raw_data?: Record<string, unknown>[] | null;
  table_data?: Record<string, unknown> | null;
}

interface MockKpi {
  label: string;
  value: number | string;
  formatted?: string;
  change?: string;
  kpi_type?: string;
}

interface MockPackage {
  analysis_type: string;
  rendered_charts: MockChart[];
  rendered_kpis: MockKpi[];
}

// ---------- 可复用的 option 模板 ----------

const MONTHS = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'];
const REGIONS = ['华东', '华南', '华北', '西南', '华中', '东北', '西北'];
const COLORS = ['服饰', '数码', '美妆', '家居', '食品', '母婴', '运动', '图书'];
const FUNNEL_STEPS = ['访问', '加购', '下单', '支付', '复购'];

function lineOption(name: string, values: number[]) {
  return {
    xAxis: { type: 'category', data: MONTHS },
    yAxis: { type: 'value' },
    series: [{ name, type: 'line', smooth: true, areaStyle: {}, data: values }],
  };
}

function multiLineOption(series: { name: string; values: number[] }[]) {
  return {
    xAxis: { type: 'category', data: MONTHS },
    yAxis: { type: 'value' },
    series: series.map((s) => ({ name: s.name, type: 'line', smooth: true, data: s.values })),
  };
}

function barOption(cats: string[], values: number[], name = '数值') {
  return {
    xAxis: { type: 'category', data: cats },
    yAxis: { type: 'value' },
    series: [{ name, type: 'bar', data: values }],
  };
}

function hbarOption(rows: { name: string; value: number }[]) {
  return { categories: rows.map((r) => r.name), series: [{ type: 'bar', data: rows.map((r) => r.value) }] };
}

function pieOption(data: { name: string; value: number }[]) {
  return { series: [{ type: 'pie', radius: ['40%', '70%'], data }] };
}

function funnelOption(data: { name: string; value: number }[]) {
  return { series: [{ type: 'funnel', data }] };
}

function rankingOption(rows: { name: string; value: number }[]) {
  return { series: [{ type: 'bar', data: rows.map((r) => r.value) }], categories: rows.map((r) => r.name) };
}

function heatmapData(months: string[], steps: string[], base: number) {
  const raw: Record<string, unknown>[] = [];
  months.forEach((m, mi) =>
    steps.forEach((s, si) => {
      const v = Math.max(0.05, base * (1 - si * 0.18) * (0.8 + ((mi * 7 + si * 3) % 9) / 20));
      raw.push({ 月份: m, 阶段: s, value: Number(v.toFixed(2)) });
    })
  );
  return raw;
}

function dualAxisOption(cats: string[], left: number[], right: number[]) {
  return {
    xAxis: { type: 'category', data: cats },
    yAxis: [{ type: 'value' }, { type: 'value' }],
    series: [
      { name: '新增', type: 'bar', data: left, yAxisIndex: 0 },
      { name: '转化率', type: 'line', data: right, yAxisIndex: 1, smooth: true },
    ],
  };
}

function bubbleData(rows: { name: string; x: number; y: number; size: number }[]) {
  return rows.map((r) => ({ 维度: r.name, x: r.x, y: r.y, size: r.size }));
}

function tableOption(cols: string[], rows: string[][]) {
  return { columns: cols, rows };
}

function rand(n: number, min: number, max: number) {
  return Array.from({ length: n }, () => Math.round(min + Math.random() * (max - min)));
}

// ---------- 构造每个分析包（14 张图内）----------

function userBehaviorPkg(): MockPackage {
  return {
    analysis_type: '用户行为分析',
    rendered_kpis: [
      { label: '总用户数', value: 128640, formatted: '128,640', change: '+12.4%' },
      { label: '活跃用户', value: 45230, formatted: '45,230', change: '+8.1%' },
      { label: '平均客单价', value: 286.5, formatted: '286.5', change: '+3.2%' },
      { label: '30日留存率', value: 0.412, formatted: '41.2%', change: '-1.5%' },
    ],
    rendered_charts: [
      { title: '用户行为留存热力图', chart_type: 'heatmap', raw_data: heatmapData(MONTHS.slice(0, 6), FUNNEL_STEPS, 0.9) },
      { title: '渠道转化漏斗', chart_type: 'funnel', option: funnelOption(FUNNEL_STEPS.map((n, i) => ({ name: n, value: 100 - i * 18 }))) },
      { title: '用户价值分布环形图', chart_type: 'pie', option: pieOption([{ name: '高价值', value: 18600 }, { name: '中价值', value: 52300 }, { name: '潜力', value: 34100 }, { name: '沉睡', value: 23640 }]) },
      { title: '近12个月活跃趋势', chart_type: 'line', option: lineOption('活跃用户', rand(12, 28000, 50000)) },
      { title: '各渠道新增用户', chart_type: 'bar', option: barOption(['自然流量', '社交媒体', '付费广告', '合作引流', '邮件召回'], [42300, 38500, 27400, 12800, 7600]) },
      { title: '渠道价值排行', chart_type: 'ranking', raw_data: REGIONS.slice(0, 6).map((r, i) => ({ name: r, value: 280000 - i * 12000 })) },
      { title: '新增 vs 转化率双轴', chart_type: 'dual_axis', option: dualAxisOption(MONTHS.slice(0, 6), rand(6, 8000, 20000), rand(6, 10, 40)) },
      { title: '用户阶段价值排行', chart_type: 'ranking', raw_data: FUNNEL_STEPS.map((n, i) => ({ name: n, value: 80 - i * 12 })) },
      { title: '用户价值气泡图', chart_type: 'bubble', raw_data: bubbleData(COLORS.slice(0, 6).map((n, i) => ({ name: n, x: rand(1, 20, 80)[0], y: rand(1, 30, 90)[0], size: rand(1, 30, 80)[0] }))) },
      { title: '用户行为明细表', chart_type: 'table', table_data: tableOption(['渠道', '新增用户', '转化率', '客单价'], REGIONS.map((r) => [r, `${rand(1, 5000, 30000)[0]}`, `${rand(1, 8, 35)[0]}%`, `¥${rand(1, 100, 500)[0]}`])) },
    ],
  };
}

function salesPkg(): MockPackage {
  return {
    analysis_type: '销售业绩分析',
    rendered_kpis: [
      { label: 'GMV', value: 14286000, formatted: '1428.6万', change: '+18.4%' },
      { label: '订单数', value: 28640, formatted: '28,640', change: '+12.1%' },
      { label: '退货率', value: 0.062, formatted: '6.2%', change: '-0.8%' },
      { label: '复购率', value: 0.345, formatted: '34.5%', change: '+2.3%' },
    ],
    rendered_charts: [
      { title: '品类销售占比', chart_type: 'pie', option: pieOption(COLORS.map((c, i) => ({ name: c, value: 500000 - i * 50000 }))) },
      { title: '销售转化漏斗', chart_type: 'funnel', option: funnelOption([{ name: '访问', value: 100 }, { name: '加购', value: 58 }, { name: '下单', value: 32 }, { name: '支付', value: 27 }, { name: '复购', value: 14 }]) },
      { title: '月度GMV趋势', chart_type: 'line', option: lineOption('GMV(万)', rand(12, 800, 1700)) },
      { title: '品类销售额对比', chart_type: 'bar', option: barOption(COLORS, rand(COLORS.length, 50000, 500000), '销售额') },
      { title: '多业务线趋势', chart_type: 'line', option: multiLineOption(['直营', '分销', '代销'].map((n) => ({ name: n, values: rand(12, 50000, 200000) }))) },
      { title: '门店销售排行', chart_type: 'ranking', raw_data: ['北京朝阳店', '上海浦东店', '广州天河店', '深圳南山店', '成都锦江店', '杭州西湖店'].map((n, i) => ({ name: n, value: 280000 - i * 15000 })) },
      { title: '月度销售 vs 客单价', chart_type: 'dual_axis', option: dualAxisOption(MONTHS.slice(0, 6), rand(6, 800, 1700), rand(6, 200, 500)) },
      { title: '品类毛利排行', chart_type: 'ranking', raw_data: COLORS.slice(0, 6).map((c, i) => ({ name: c, value: 60 - i * 7 })) },
      { title: '客单价 vs 销量气泡', chart_type: 'bubble', raw_data: bubbleData(COLORS.slice(0, 6).map((n, i) => ({ name: n, x: rand(1, 100, 500)[0], y: rand(1, 50000, 300000)[0], size: rand(1, 20, 80)[0] }))) },
      { title: '区域销售汇总', chart_type: 'table', table_data: tableOption(['区域', '销售额(万)', '订单数', '同比'], REGIONS.map((r) => [r, `${rand(1, 80, 200)[0]}`, `${rand(1, 5000, 30000)[0]}`, `+${rand(1, 5, 20)[0]}.${rand(1, 0, 9)[0]}%`])) },
    ],
  };
}

function channelPkg(): MockPackage {
  return {
    analysis_type: '渠道转化分析',
    rendered_kpis: [
      { label: '总访问', value: 1820000, formatted: '182.0万', change: '+15.2%' },
      { label: '转化率', value: 0.273, formatted: '27.3%', change: '+1.1%' },
      { label: '获客成本', value: 38.6, formatted: '¥38.6', change: '-5.4%' },
      { label: 'ROI', value: 4.2, formatted: '4.2x', change: '+0.6x' },
    ],
    rendered_charts: [
      { title: '渠道分布环形图', chart_type: 'pie', option: pieOption([['自然流量', 423000], ['社交媒体', 385000], ['付费广告', 274000], ['合作引流', 128000], ['邮件召回', 76000]].map(([n, v]) => ({ name: n as string, value: v as number }))) },
      { title: '渠道转化漏斗', chart_type: 'funnel', option: funnelOption([{ name: '曝光', value: 100 }, { name: '点击', value: 64 }, { name: '访问', value: 42 }, { name: '加购', value: 23 }, { name: '下单', value: 14 }]) },
      { title: '渠道访问趋势', chart_type: 'line', option: multiLineOption(['自然', '社交', '付费'].map((n) => ({ name: n, values: rand(12, 30000, 100000) }))) },
      { title: '渠道获客成本', chart_type: 'bar', option: barOption(['自然流量', '社交媒体', '付费广告', '合作引流', '邮件召回'], [12, 28, 65, 22, 8], '成本') },
      { title: '渠道转化热力图', chart_type: 'heatmap', raw_data: heatmapData(MONTHS.slice(0, 6), FUNNEL_STEPS, 0.85) },
      { title: 'Top渠道排行', chart_type: 'ranking', raw_data: ['小红书种草', '抖音直播', '微信朋友圈', '百度SEM', 'KOL合作', '私域社群'].map((n, i) => ({ name: n, value: 50000 - i * 6000 })) },
      { title: '访问 vs 转化双轴', chart_type: 'dual_axis', option: dualAxisOption(MONTHS.slice(0, 6), rand(6, 100000, 250000), rand(6, 15, 35)) },
      { title: '渠道效率排行', chart_type: 'ranking', raw_data: ['自然流量', '社交媒体', '付费广告', '合作引流'].map((n, i) => ({ name: n, value: 85 - i * 15 })) },
      { title: '渠道产出气泡', chart_type: 'bubble', raw_data: bubbleData([['自然流量', 80, 42, 60], ['社交媒体', 65, 38, 55], ['付费广告', 45, 65, 70], ['合作引流', 50, 32, 40]].map(([n, x, y, s]) => ({ name: n as string, x: x as number, y: y as number, size: s as number }))) },
      { title: '渠道明细', chart_type: 'table', table_data: tableOption(['渠道', '曝光', '转化', '成本'], [['自然流量', '128万', '4.2%', '¥12'], ['社交媒体', '86万', '3.8%', '¥28'], ['付费广告', '64万', '6.5%', '¥65']]) },
    ],
  };
}

const MOCK_PACKAGES: MockPackage[] = [userBehaviorPkg(), salesPkg(), channelPkg()];

export default MOCK_PACKAGES;