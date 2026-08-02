/* StarBackground - 三层星空粒子系统 + 银河带 + 呼吸光晕 */
import React from 'react';

export default function StarBackground() {
  return (
    <>
      {/* 远景恒星层：200+ 小星点，缓慢闪烁 */}
      <div className="cosmic-stars-far" />

      {/* 银河带：从左下到右上斜跨 */}
      <div className="cosmic-galaxy-band" />

      {/* 星云漂浮层 */}
      <div className="cosmic-nebula-drift" />

      {/* 中景星云层：50-80 发光粒子 */}
      <div className="cosmic-nebula-mid" />

      {/* 前景流星层 */}
      <div className="cosmic-meteors" />

      {/* 背景光晕呼吸 */}
      <div className="cosmic-aura" />
    </>
  );
}
