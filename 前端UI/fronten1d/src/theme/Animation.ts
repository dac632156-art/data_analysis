/**
 * Animation.ts —— 动画规范（保持专业，不过度夸张）
 */

export const Animation = {
  duration: {
    fast: 200,
    base: 400,
    slow: 500,
    slowest: 600,
  },
  easing: {
    /** 标准缓动（用于进入动画） */
    standard: 'cubic-bezier(0.16,1,0.3,1)',
    /** ECharts 标准 out */
    out: 'cubicOut',
    inOut: 'cubicInOut',
  },
  /** 可注入全局 <style> 的 keyframes */
  keyframes: {
    fadeIn: '@keyframes dbFadeIn { from { opacity:0; transform:translateY(8px);} to {opacity:1; transform:translateY(0);} }',
    slideUp: '@keyframes dbSlideUp { from { opacity:0; transform:translateY(16px);} to {opacity:1; transform:translateY(0);} }',
    scaleIn: '@keyframes dbScaleIn { from { opacity:0; transform:scale(0.95);} to {opacity:1; transform:scale(1);} }',
  },
} as const;

export type AnimationToken = typeof Animation;
