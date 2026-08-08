/**
 * 仙气水彩环形图（React 版）
 *
 * ★ 严格移植自「可视化模板库/同期群分析/环形图组件.js」
 *   除「接入 React（echarts 实例来源 + 资源路径解析）」外，组件逻辑、配色、纹理生成
 *   全部照原版保留，未做篡改。
 *
 * 原版签名：renderEtherealPieChart(domId, chartData, cardBgUrl, sliceTextureUrl, title)
 *  - cardBgUrl     : 卡片外层高级水墨背景图（默认 背景.png）
 *  - sliceTextureUrl: 扇区内部黑白水墨纹理底图（默认 bg5.png）
 */
import React, { useEffect, useRef } from 'react';
import * as echarts from 'echarts/core';

// 水墨纹理资源（Vite 会按 import.meta.url 解析为真实地址）
const CARD_BG_URL = new URL('../../assets/ethereal/背景.png', import.meta.url).href;
const SLICE_TEXTURE_URL = new URL('../../assets/ethereal/bg5.png', import.meta.url).href;

// 仙气默认粉彩配色
const defaultPalette = ['#C7E7FB', '#E0C5F0', '#FBC2E8', '#C4EAD1', '#FED3C2', '#F3C0C7', '#F7F1BA', '#B6BBF5'];

// ============ 以下工具函数照原版移植，未改动逻辑 ============

/** RGB 混合（原版 colorMixRGBA） */
function colorMixRGBA(rgb1: string, rgb2: string, weight: number): string {
  const c1 = rgb1.replace('#', '');
  const c2 = rgb2.replace('#', '');
  const r1 = parseInt(c1.substring(0, 2), 16);
  const g1 = parseInt(c1.substring(2, 4), 16);
  const b1 = parseInt(c1.substring(4, 6), 16);
  const r2 = parseInt(c2.substring(0, 2), 16);
  const g2 = parseInt(c2.substring(2, 4), 16);
  const b2 = parseInt(c2.substring(4, 6), 16);
  const r = Math.round(r1 * (1 - weight) + r2 * weight);
  const g = Math.round(g1 * (1 - weight) + g2 * weight);
  const b = Math.round(b1 * (1 - weight) + b2 * weight);
  return `rgb(${r}, ${g}, ${b})`;
}

/**
 * 生成纯正水彩纹理 Canvas（★ 严格按原版「可视化模板库/同期群分析/环形图组件.js」移植）
 *
 * 原版逻辑：
 *   1. 创建画布 850x650
 *   2. 把黑白纹理图以「扇区索引 * 137 度」旋转后绘制在画布中心
 *   3. 用 getImageData 遍历每个像素，按亮度计算不透明度：
 *        - 白色像素（bright）→ opacity≈0.35（颜色淡化当背景）
 *        - 黑色像素（dark）   → opacity=1.0（完全显示颜色当墨迹）
 *      用公式 (1-opacity)*255 + opacity*color 混合成 RGBA
 *   4. putImageData 写回 → 返回 canvas
 *
 * 重要：这不是 multiply 复合，是逐像素手动染色，不会让黑色像素"乘没"颜色。
 */
function createPureWatercolorPattern(
  img: HTMLImageElement,
  hexColor: string,
  sliceIndex: number,
): HTMLCanvasElement {
  const width = 850;
  const height = 650;
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d')!;

  const cx = width / 2;
  const cy = height / 2;

  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate((sliceIndex * 137) * Math.PI / 180);
  const drawSize = 850;
  ctx.drawImage(img, -drawSize / 2, -drawSize / 2, drawSize, drawSize);
  ctx.restore();

  const imageData = ctx.getImageData(0, 0, width, height);
  const data = imageData.data;

  const hex = hexColor.replace('#', '');
  const r = parseInt(hex.substring(0, 2), 16);
  const g = parseInt(hex.substring(2, 4), 16);
  const b = parseInt(hex.substring(4, 6), 16);

  for (let i = 0; i < data.length; i += 4) {
    const brightness = data[i]; // 取 R 作为亮度（原版直接用 R）
    const darkness = (255 - brightness) / 255;

    let opacity = 0.35 + darkness * 2.2;
    if (opacity > 1.0) opacity = 1.0;

    data[i] = Math.round(255 * (1 - opacity) + r * opacity);
    data[i + 1] = Math.round(255 * (1 - opacity) + g * opacity);
    data[i + 2] = Math.round(255 * (1 - opacity) + b * opacity);
    data[i + 3] = 255;
  }

  ctx.putImageData(imageData, 0, 0);
  return canvas;
}

interface Props {
  /** 现有 ECharts 饼图 option（兼容 series[0].data）或 原版 chartData 结构 */
  option?: Record<string, unknown> | null;
  /** 直接传扁平数据（优先于 option） */
  data?: Array<{ name: string; value: number }>;
  title?: string;
  height?: number | string;
  /** 卡片外层水墨背景图地址（默认 背景.png） */
  cardBgUrl?: string;
  /** 扇区内部水墨纹理底图地址（默认 bg5.png） */
  sliceTextureUrl?: string;
}

export const EtherealPieChart: React.FC<Props> = ({
  option,
  data,
  title,
  height = 360,
  cardBgUrl = CARD_BG_URL,
  sliceTextureUrl = SLICE_TEXTURE_URL,
}) => {
  const domRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!domRef.current) return;
    const chartDom = domRef.current;
    const myChart = echarts.init(chartDom);

    // —— 数据解析（照原版 chartData 结构：兼容传入 option / data 扁平结构）——
    let chartData: Array<{ name: string; value: number }> = [];
    if (data && data.length) {
      chartData = data;
    } else if (option) {
      const series = (option.series as Array<Record<string, unknown>>) || [];
      const pieSeries = series.find((s) => s.type === 'pie') || series[0];
      if (pieSeries) {
        chartData = ((pieSeries.data as Array<unknown>) || []).map((d) => {
          if (Array.isArray(d)) return { name: String(d[0]), value: Number(d[1]) };
          if (typeof d === 'object' && d !== null) {
            const o = d as Record<string, unknown>;
            return { name: String(o.name ?? ''), value: Number(o.value ?? 0) };
          }
          return { name: '', value: Number(d ?? 0) };
        });
      }
    }
    const titleText = title ?? String(((option?.title as Record<string, unknown>)?.text) || '');

    myChart.showLoading({ text: '渲染水彩纹理中...', color: '#F472B6', maskColor: 'rgba(255,255,255,0.4)' });

    const img = new Image();
    img.crossOrigin = 'anonymous';

    img.onload = () => {
      // —— 逐扇区生成水墨染色纹理（★ 严格照原版调用方式）——
      const processedData = chartData.map((item, index) => {
        const color = defaultPalette[index % defaultPalette.length];
        const pattern = createPureWatercolorPattern(img, color, index);
        return {
          name: item.name,
          value: item.value,
          itemStyle: { color: { image: pattern, repeat: 'repeat' } as unknown as string },
        };
      });

      myChart.hideLoading();
      myChart.setOption({
        backgroundColor: 'transparent',
        title: titleText
          ? {
              text: titleText,
              left: 'center',
              top: 10,
              textStyle: { color: '#1E293B', fontSize: 16, fontWeight: 'bold' },
            }
          : undefined,
        tooltip: {
          trigger: 'item',
          backgroundColor: 'rgba(255,255,255,0.9)',
          borderColor: '#E2E8F0',
          padding: [12, 16],
          textStyle: { color: '#475569', fontWeight: 600 },
          extraCssText: 'box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); border-radius: 12px;',
        },
        legend: {
          bottom: 0,
          icon: 'circle',
          itemWidth: 10,
          itemHeight: 10,
          textStyle: { color: '#64748B', fontSize: 11, fontWeight: 600 },
        },
        series: [
          {
            type: 'pie',
            radius: ['30%', '55%'],
            center: ['50%', '50%'],
            avoidLabelOverlap: true,
            label: {
              show: true,
              color: '#475569',
              fontWeight: 600,
              fontSize: 10,
              formatter: '{b}\n{d}%',
            },
            labelLine: {
              lineStyle: { color: '#CBD5E1' },
              smooth: 0.2,
              length: 6,
              length2: 10,
            },
            data: processedData,
          },
        ],
      });
    };

    img.onerror = () => {
      myChart.hideLoading();
      // 纹理加载失败则降级为纯色（保留粉彩配色）
      const processedData = chartData.map((item, index) => ({
        name: item.name,
        value: item.value,
        itemStyle: { color: defaultPalette[index % defaultPalette.length] },
      }));
      myChart.setOption({
        backgroundColor: 'transparent',
        series: [{ type: 'pie', radius: ['30%', '55%'], center: ['50%', '50%'], data: processedData }],
      });
    };
    img.src = sliceTextureUrl;

    const onResize = () => myChart.resize();
    window.addEventListener('resize', onResize);
    const ro = new ResizeObserver(onResize);
    ro.observe(chartDom);

    return () => {
      window.removeEventListener('resize', onResize);
      ro.disconnect();
      myChart.dispose();
    };
  }, [option, data, title, sliceTextureUrl]);

  return (
    <div
      ref={domRef}
      style={{
        width: '100%',
        height,
        borderRadius: 24,
        padding: 20,
        boxSizing: 'border-box',
        backgroundImage: `url(${cardBgUrl})`,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        backdropFilter: 'blur(4px)',
        WebkitBackdropFilter: 'blur(4px)',
        boxShadow:
          '0 20px 40px -10px rgba(99,102,241,0.05), inset 0 0 0 1px rgba(255,255,255,0.8)',
      }}
    />
  );
};

export default EtherealPieChart;
