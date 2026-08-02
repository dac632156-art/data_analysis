/**
 * ChartStyle.ts —— 逐类型图表规范（Galaxy AI Analytics）
 *
 * 取代原 ChartPalette.ts，结构性演进：
 *  - 所有颜色统一从 Palette / withAlpha 派生，禁止写死。
 *  - 逐类型规范（Line / Bar / Area / Pie / Scatter / Radar / Heatmap / Map）。
 *  - 多系列 / 多类别用 10 色有序分类色板（蓝→靛→青→金→粉→橙→青柠→淡紫→天空蓝→湖绿，暖色前置）；AI 紫禁入图表，禁彩虹 / 禁蓝白交替。
 *  - 移除旧 ChartPalette 中不存在于新契约的字段（tooltip.text / line.axis 上移为顶层 axis）。
 */
import { Palette, withAlpha } from './Palette';

export const ChartStyle = {
  // ===== 折线 / 面积图 =====
  line: {
    line: Palette.primary,
    width: 3,
    point: 4,
    hoverPoint: 8,
    area: withAlpha(Palette.primary, 0.18),
  },

  // ===== 柱状图（普通蓝 / Top 青 / 非重点蓝，禁每柱异色） =====
  bar: {
    normal: Palette.primary,
    top: Palette.interaction,
    muted: withAlpha(Palette.primary, 0.35),
    emphasis: Palette.primaryHover,
  },

  // ===== 面积图（独立，便于 area series 复用） =====
  area: {
    line: Palette.primary,
    area: withAlpha(Palette.primary, 0.20),
  },

  // ===== 饼图 / 环形图：10 色有序分类色板（禁彩虹 / 禁随机；AI 紫不进图表） =====
  pie: [
    Palette.primary, Palette.catIndigo, Palette.interaction, Palette.catGold,
    Palette.catRose, Palette.catCoral, Palette.catLime, Palette.catLightPurple,
    Palette.catSkyBlue, Palette.catLake,
  ],

  // ===== 散点 / 气泡 =====
  scatter: {
    color: Palette.primary,
    opacity: 0.7,
  },

  // ===== 雷达图（含网格轴线 / 分隔线，必须可读） =====
  radar: {
    line: Palette.primary,
    area: withAlpha(Palette.primary, 0.15),
    axis: withAlpha(Palette.textMuted, 0.15),
    split: withAlpha(Palette.textMuted, 0.08),
  },

  // ===== 热力图：蓝色渐变（禁红绿） =====
  heatmap: [
    Palette.heatStart, Palette.skyDeep, Palette.skyMid, Palette.sky,
    Palette.primary, Palette.primaryBright, Palette.interaction,
  ],

  // ===== 地图：普通 / Hover / 高亮统一蓝青 =====
  map: {
    normal: Palette.mapNormal,
    hover: Palette.interaction,
    highlight: Palette.primary,
  },

  // ===== 网格分割线 =====
  grid: Palette.border,

  // ===== 坐标轴文本色（原 line.axis 上移至顶层） =====
  axis: withAlpha(Palette.textPrimary, 0.55),

  // ===== Legend =====
  legend: Palette.textMuted,

  // ===== Tooltip =====
  tooltip: {
    background: Palette.card,
    border: Palette.border,
    title: Palette.textPrimary,
    content: Palette.tooltipContent,
  },

  // ===== 多系列 / 多类别 10 色有序分类色板（蓝→靛→青→金→粉→橙→青柠→淡紫→天空蓝→湖绿，暖色前置）=====
  // 与后端 echart_generator.py 的 BLUE_PALETTE 顺序、取值完全一致。
  // 约束：银河紫 ai(#8B5CF6) 专属 AI / Glow / 按钮，禁入此板；禁彩虹、禁每图随机配色。
  series: [
    Palette.primary, Palette.catIndigo, Palette.interaction, Palette.catGold,
    Palette.catRose, Palette.catCoral, Palette.catLime, Palette.catLightPurple,
    Palette.catSkyBlue, Palette.catLake,
  ],

  // ===== 强调 / 联动高亮的辉光色（银河紫，替代原写死紫色 #8b5cf6） =====
  emphasisGlow: withAlpha(Palette.ai, 0.55),
} as const;

export type ChartStyleToken = typeof ChartStyle;
