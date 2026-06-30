/* AnimatedNumber - 数字滚动动效组件（基于 CountUp.js） */
import React, { useEffect, useRef } from 'react';
import { CountUp } from 'countup.js';

interface Props {
  value: number;
  /** 动画时长（秒） */
  duration?: number;
  /** 小数位数 */
  decimals?: number;
  /** 数字前缀 */
  prefix?: string;
  /** 数字后缀 */
  suffix?: string;
  /** 千分位分隔符 */
  separator?: string;
  /** 小数分隔符 */
  decimal?: string;
  /** 自定义样式 */
  className?: string;
  /** 内联样式 */
  style?: React.CSSProperties;
}

export default function AnimatedNumber({
  value,
  duration = 1.5,
  decimals = 0,
  prefix = '',
  suffix = '',
  separator = ',',
  decimal = '.',
  className = '',
  style,
}: Props) {
  const ref = useRef<HTMLSpanElement>(null);
  const instanceRef = useRef<CountUp | null>(null);

  useEffect(() => {
    if (!ref.current) return;

    // 销毁旧实例
    if (instanceRef.current) {
      instanceRef.current = null;
    }

    const countUp = new CountUp(ref.current, value, {
      startVal: 0,
      duration,
      decimalPlaces: decimals,
      prefix,
      suffix,
      separator,
      decimal,
      enableScrollSpy: false,
      useEasing: true,
      useGrouping: true,
    });

    if (countUp.error) {
      // 回退：直接显示值
      ref.current.textContent = prefix + value.toLocaleString() + suffix;
      return;
    }

    countUp.start();
    instanceRef.current = countUp;

    return () => {
      countUp.reset();
    };
  }, [value, duration, decimals, prefix, suffix, separator, decimal]);

  return <span ref={ref} className={className} style={style} />;
}
