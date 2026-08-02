/**
 * SemanticColor.ts —— 语义色映射层（Galaxy AI Analytics）
 *
 * 全部从 Palette 派生，自身不出现任何新 HEX。
 * 含义：Data=星光蓝 / AI=银河紫 / Interaction=极光青 / Content=月光白 / Surface=深空蓝。
 * 状态色 success / warning / danger 仅用于 KPI 涨跌 / 异常。
 */
import { Palette } from './Palette';

export const SemanticColor = {
  /** 数据 = 星光蓝（占 Dashboard ~90%） */
  data: Palette.primary,
  /** AI = 银河紫（禁普通图表） */
  ai: Palette.ai,
  /** 交互 = 极光青 */
  interaction: Palette.interaction,
  /** 内容 = 月光白 */
  content: Palette.textPrimary,
  /** 表面 = 深空蓝 */
  surface: Palette.card,
  status: {
    success: Palette.success,
    warning: Palette.warning,
    danger: Palette.danger,
  },
} as const;

export type SemanticColorToken = typeof SemanticColor;
