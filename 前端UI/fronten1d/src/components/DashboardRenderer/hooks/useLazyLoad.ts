/**
 * useLazyLoad —— Widget 懒加载 hook
 *
 * 只在 Widget 进入可视区域后才渲染真实内容。
 * 减少首屏渲染压力。
 */

import { useEffect, useState, useRef } from 'react';

export function useLazyLoad<T extends HTMLElement>(threshold = 0.05) {
  const [shouldRender, setShouldRender] = useState(false);
  const ref = useRef<T>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) {
      // 如果没有 ref，直接渲染
      setShouldRender(true);
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setShouldRender(true);
          observer.disconnect();
        }
      },
      { threshold },
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, [threshold]);

  return { ref, shouldRender };
}
