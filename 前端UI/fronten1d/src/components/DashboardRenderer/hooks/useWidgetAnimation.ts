/**
 * useWidgetAnimation —— Widget 动画 hook
 *
 * Dashboard 首次进入：Fade In
 * Card：Scale In
 * Chart：Progressive Animation
 * Filter：Smooth Transition
 *
 * 动画不要夸张。保持专业。
 */

import { useEffect, useState, useRef } from 'react';

export interface AnimationConfig {
  type: 'fade-in' | 'slide-up' | 'scale-in' | 'progressive';
  delay?: number;     // ms
  duration?: number;  // ms
}

/** Widget 首次可见时触发动画 */
export function useWidgetAnimation(config: AnimationConfig) {
  const [visible, setVisible] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    // IntersectionObserver 检测首次进入可视区域
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.disconnect();  // 只触发一次
        }
      },
      { threshold: 0.1 },
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const animationClass = visible ? `animate-db-${config.type}` : 'opacity-0';
  const animationStyle = visible ? { animationDelay: `${config.delay || 0}ms` } : {};

  return { ref, visible, animationClass, animationStyle };
}
