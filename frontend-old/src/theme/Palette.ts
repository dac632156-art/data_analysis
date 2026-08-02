/**
 * Palette.ts —— Galaxy AI Analytics 基础色板
 *
 * ★ 整个项目唯一的「原始颜色」来源（Single Source of Truth）。
 * 任何 HEX / 基础色只可在此定义；SemanticColor / ChartStyle / 后端 GALAXY
 * 全部从这里派生，禁止在其它文件写死颜色（杜绝真源被拆成多份）。
 *
 * 品牌：Professional · Technology · AI · Business · Executive · Dark · Premium
 * 不是 PowerPoint，不是 Excel，不是彩虹色 Dashboard。
 */

/** 将 HEX 转为带透明度的 rgba（用于面积 / 辉光 / 边框等派生色，杜绝散落字面量） */
export function withAlpha(hex: string, alpha: number): string {
  const h = hex.replace('#', '');
  const r = parseInt(h.substring(0, 2), 16);
  const g = parseInt(h.substring(2, 4), 16);
  const b = parseInt(h.substring(4, 6), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

export const Palette = {
  // ===== 背景 =====
  /** 主背景（深空 #020617） */
  pageBg: '#020617',

  // ===== 卡片表面（深空蓝 Surface） =====
  /** 卡片背景 */
  card: '#0F172A',
  /** 卡片 Hover 表面 */
  cardHover: '#16223F',
  /** 表头 / 区块头背景 */
  header: '#182642',

  // ===== 边框 =====
  border: 'rgba(255,255,255,0.08)',
  borderStrong: 'rgba(255,255,255,0.12)',

  // ===== 文本 =====
  /** 月光白（标题 / 正文 / 数字） */
  textPrimary: '#F8FAFC',
  /** 次级文本（dimmed white，用于副标题 / 描述） */
  textSecondary: 'rgba(248,250,252,0.65)',
  /** 中性灰（图例 / Label / 坐标轴） */
  textMuted: '#94A3B8',
  textDisabled: '#64748B',

  // ===== 数据主色（星光蓝，Dashboard ~90%） =====
  primary: '#38BDF8',
  primaryHover: '#7DD3FC',
  primaryActive: '#0EA5E9',
  /** 高亮蓝（饼图第 3 段 / 多系列第 4 段） */
  primaryBright: '#67E8F9',
  /** 蓝色梯度（冷色 ramp，禁紫） */
  sky: '#0ea5e9',
  skyMid: '#0369a1',
  skyDeep: '#0c4a6e',

  // ===== AI 语义色（银河紫，仅用于 Insight / Recommendation / Agent，禁普通图表） =====
  ai: '#8B5CF6',

  // ===== 交互色（极光青，Hover / Active / Selected / Filter / Button / Focus） =====
  interaction: '#22D3EE',

  // ===== 数据分类色板（Categorical Palette · 10 色有序） =====
  // 普通图表多系列 / 多类别按顺序取色；蓝→靛→青 三冷色打头保品牌调，第 4 位起暖色前置（金→粉→橙→青柠）拉节奏。
  // 银河紫 ai(#8B5CF6) 仍专属 AI / Glow / 按钮，禁入此板；图表第二数据位由靛蓝 catIndigo 替补。
  // 金色 catGold 与 warning 同值，但语义独立（数据色 vs 预警），勿混用。
  catIndigo: '#818CF8',       // 靛蓝（第二数据位，替补 AI 紫；比浅靛蓝更饱和、更抓眼）
  catLightPurple: '#C084FC',  // 淡紫
  catSkyBlue: '#60A5FA',      // 天空蓝
  catLake: '#2DD4BF',         // 湖水绿
  catGold: '#FBBF24',         // 金色（数据色）
  catRose: '#F472B6',         // 玫瑰粉
  catCoral: '#FB923C',         // 珊瑚橙
  catLime: '#84CC16',         // 青柠绿

  // ===== 地图 / 热力图派生 =====
  /** 地图普通区域 */
  mapNormal: '#23304E',
  /** 热力图起点（提亮，避免融进卡片不可见） */
  heatStart: '#13243F',
  /** Tooltip 正文色 */
  tooltipContent: '#CBD5E1',

  // ===== 状态色（仅用于 KPI 涨跌 / 异常 / 预警，禁普通图表） =====
  success: '#34D399',
  warning: '#FBBF24',
  danger: '#FB7185',
  /** 信息态（等同于数据主色） */
  info: '#38BDF8',
} as const;

export type PaletteToken = typeof Palette;
