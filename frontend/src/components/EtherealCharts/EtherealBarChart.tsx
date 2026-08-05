import React, { useEffect, useRef } from 'react';
import * as echarts from 'echarts/core';
import { BarChart } from 'echarts/charts';
import { GridComponent, TooltipComponent, ToolboxComponent, GraphicComponent, TitleComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import type { EChartsCoreOption } from 'echarts/core';
import 背景 from '../../assets/ethereal/背景.png';

echarts.use([BarChart, GridComponent, TooltipComponent, ToolboxComponent, GraphicComponent, TitleComponent, CanvasRenderer]);

// 8 色粉彩调色板（严格对齐原版 echarts_柱状图.js 第 22 行）
const customPalette = ['#FCCDDF', '#C8E1F5', '#E2C9F3', '#D7EFE5', '#FCDDC8', '#E8C9CE', '#F9F1C6', '#BAC2F0'];

function withAlpha(hex: string, alpha: string): string {
  return `${hex}${alpha}`;
}

function normalizeTitle(node: Record<string, unknown>, propTitle?: string): string {
  if (propTitle) return propTitle;
  const t = node.title;
  if (typeof t === 'string') return t;
  if (t && typeof t === 'object') {
    const text = (t as Record<string, unknown>).text;
    if (typeof text === 'string') return text;
  }
  return '';
}

function getXData(opt: Record<string, unknown>): string[] {
  const xAxis = opt.xAxis as Record<string, unknown> | Array<Record<string, unknown>> | undefined;
  if (!xAxis) return [];
  const first = Array.isArray(xAxis) ? xAxis[0] : xAxis;
  const data = first?.data;
  return Array.isArray(data) ? data.map((v) => String(v ?? '')) : [];
}

// 从 option 的 xAxis/yAxis 读取轴名（后端已按模型正确写入），无则 undefined（不显示轴名）
function getAxisName(opt: Record<string, unknown>, key: 'xAxis' | 'yAxis'): string | undefined {
  const axis = opt[key] as Record<string, unknown> | Array<Record<string, unknown>> | undefined;
  if (!axis) return undefined;
  const first = Array.isArray(axis) ? axis[0] : axis;
  const name = first?.name;
  return typeof name === 'string' && name.length > 0 ? name : undefined;
}

function extractSeriesValues(raw: unknown): number[] {
  if (!Array.isArray(raw)) return [];
  return raw.map((v) => {
    if (typeof v === 'number') return v;
    if (typeof v === 'object' && v !== null) return Number((v as Record<string, unknown>).value ?? 0);
    return Number(v ?? 0);
  });
}

interface Props {
  chartNode: Record<string, unknown>;
  title?: string;
  height?: number | string;
}

// 通用格式化器：万/亿按 unitHint 转成 "1404.3万" 这种。
// unitHint 是后端通过 _unitHint 传的纯字符串（"万"/"亿"），没有 JS 代码，
// 由前端在此写出真函数后塞进 ECharts option。
function makeUnitFormatter(unitHint?: string): (v: any) => string {
  const fmt = (raw: any): string => {
    // 兼容 ECharts 不同系列/位置的 formatter 传值：
    // - bar label.formatter: p = { value }（部分版本直接是数字）
    // - tooltip.formatter: p = { data: { value } }
    let n: number;
    if (typeof raw === 'number') {
      n = raw;
    } else if (raw && typeof raw === 'object') {
      n = Number(raw.value ?? raw.data?.value ?? 0);
    } else {
      n = Number(raw ?? 0);
    }
    if (!Number.isFinite(n)) return '';
    if (unitHint === '亿') return (n / 100000000).toFixed(2) + '亿';
    if (unitHint === '万') return (n / 10000).toFixed(1) + '万';
    return String(n);
  };
  return fmt;
}

export const EtherealBarChart: React.FC<Props> = ({ chartNode, title, height = 360 }) => {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    const chartDom = ref.current;
    chartDom.style.backgroundImage = `url(${背景})`;
    chartDom.style.backgroundSize = 'cover';
    chartDom.style.backgroundPosition = 'center';
    chartDom.style.borderRadius = '24px';
    chartDom.style.backgroundColor = 'rgba(255, 255, 255, 0.32)';

    const chart = echarts.init(chartDom);
    const node = chartNode || {};

    const titleText = normalizeTitle(node, title);
    const seriesInput = ((node.series as Array<Record<string, unknown>>) || []);
    const xAxisData = getXData(node);
    const rawData = (node.data as Array<Record<string, unknown>>) || undefined;
    // 轴名来自后端 JSON（模型已正确写入），不再前端写死
    const xAxisName = getAxisName(node, 'xAxis');
    const yAxisName = getAxisName(node, 'yAxis');

    // y 轴名自适应间距：短名（"人数"/"金额"）贴轴不飞出去，长名（"客户生命周期价值"）拉远不挡刻度
    const yAxisNameLen = yAxisName ? yAxisName.length : 0;
    // 通用规则：≤4字贴近、>4字拉远
    let yAxisNameGap = yAxisNameLen <= 4 ? 50 : 83;
    // 特定图兜底：客户生命周期价值-分布直方图（按 x 轴名识别）仍压刻度，再右挪 5
    if (xAxisName && xAxisName.includes('客户生命周期价值') && yAxisName === '客户数（人）') {
      yAxisNameGap = 40;
    }

    // 后端注入的 _unitHint（纯数据 "万"/"亿"，不是 JS 代码）→ 前端据此生成真正的 formatter 函数
    const unitHint = (node._unitHint as string) || undefined;

    let categories: string[] = xAxisData.length ? xAxisData : [];
    let series: any[] = [];

    // 阈值线：从 chart_config.threshold 取（分析包路径）；若缺失则由 series 中后端注入的
    // markLine 兜底（经典网格/预览页只传 option 的路径，_inject_threshold_markline 已注入完整 markLine）。
    const chartConfig = (node.chart_config as Record<string, unknown> | undefined) || {};
    const thresholdRaw = chartConfig.threshold;
    const threshold = typeof thresholdRaw === 'number' ? thresholdRaw : Number(thresholdRaw);
    const thresholdLabel = (chartConfig.threshold_label as string) || '阈值';
    // 红线画在命中桶的"左边界"（即阈值的数值分界点），而不是柱子正中间，
    // 否则视觉上像穿过柱子、看不出阈值数值。category 轴 markLine 传入数字时
    // 被当作类目浮点坐标，bestIdx-0.5 即第 bestIdx 根柱子的左边界；首桶 clamp 到 0。
    let thresholdX: number | undefined;
    if (Number.isFinite(threshold) && categories.length > 0) {
      // 从桶名提取「区间起点」用于定位阈值分界：
      // "≥157天"/">=157" → 157（尾桶）；"0~10天"/"0-10" → 区间起点 0；"53"/"106" 纯数字 → 本身
      const bucketStart = (cat: string): number | undefined => {
        const s = String(cat);
        let m = s.match(/[≥>=]+\s*(\d+(?:\.\d+)?)/);
        if (m) return parseFloat(m[1]);
        m = s.match(/(\d+(?:\.\d+)?)\s*[~\-]\s*\d+(?:\.\d+)?/);
        if (m) return parseFloat(m[1]);
        m = s.match(/^\s*(\d+(?:\.\d+)?)\s*$/);
        if (m) return parseFloat(m[1]);
        return undefined;
      };
      let bestIdx = -1;
      for (let i = 0; i < categories.length; i++) {
        const v = bucketStart(categories[i]);
        if (v !== undefined && v >= threshold) {
          bestIdx = i;
          break;
        }
      }
      if (bestIdx >= 0) {
        // 命中桶：红线落左边界（首桶 clamp 到 0 避免画出轴外左侧）
        thresholdX = Math.max(bestIdx - 0.5, 0);
      } else if (categories.length > 0) {
        // 阈值超过所有桶起点：落最右桶右边界外侧，表明全量已超阈值（不静默不画）
        thresholdX = categories.length - 1 + 0.5;
      }
    }

    // 优先标准 option：按 series 生成柱状图（每柱独立配色，对齐原版）
    if (seriesInput.length > 0 && categories.length > 0) {
      const items: { category: string; seriesIndex: number; valueIndex: number; value: number; color: string }[] = [];
      seriesInput.forEach((s, sIdx) => {
        const vals = extractSeriesValues(s.data);
        vals.forEach((v, vIdx) => {
          items.push({
            category: categories[vIdx] ?? '',
            seriesIndex: sIdx,
            valueIndex: vIdx,
            value: v,
            color: customPalette[(sIdx * vals.length + vIdx) % customPalette.length],
          });
        });
      });

      series = seriesInput.map((s, sIdx) => ({
        name: s.name || `Series ${sIdx + 1}`,
        type: 'bar' as const,
        barWidth: 38,
        // 保留后端 option 中已注入的阈值 markLine（经典网格/预览页只传 option 的路径，
        // _inject_threshold_markline 已写入正确类目文本的 xAxis，透传即可渲染红线）。
        ...(s.markLine ? { markLine: s.markLine } : {}),
        data: items
          .filter((it) => it.seriesIndex === sIdx)
          .map((it) => ({
            value: it.value,
            name: it.category,
            itemStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: withAlpha(it.color, 'F0') },
                { offset: 0.1, color: withAlpha(it.color, 'E8') },
                { offset: 1, color: withAlpha(it.color, '70') },
              ]),
              borderRadius: 19,
              borderColor: 'rgba(255, 255, 255, 0.4)',
              borderWidth: 1,
              shadowColor: withAlpha(it.color, '30'),
              shadowBlur: 8,
              shadowOffsetY: 0,
            },
          })),
        label: {
          show: true,
          position: 'top' as const,
          color: '#475569',
          fontWeight: 600,
          fontSize: 13,
          distance: 8,
          // ★ 跟 y 轴一样，根据后端 _unitHint 出真函数（"1404.3万"）
          ...(unitHint ? { formatter: makeUnitFormatter(unitHint) } : {}),
        },
      }));
    } else if (Array.isArray(rawData) && rawData.length > 0) {
      // 老私有格式兜底
      const xs = (node.x as string) || 'x';
      categories = rawData.map((r) => String(r[xs] ?? ''));
      const yKeys = Object.keys(rawData[0] || {}).filter((k) => k !== xs);

      const items: { category: string; yKey: string; value: number; color: string }[] = [];
      rawData.forEach((r, i) => {
        yKeys.forEach((yk, yi) => {
          items.push({
            category: String(r[xs] ?? ''),
            yKey: yk,
            value: Number(r[yk] ?? 0),
            color: customPalette[(i * yKeys.length + yi) % customPalette.length],
          });
        });
      });

      series = yKeys.map((yKey) => ({
        name: yKey,
        type: 'bar' as const,
        barWidth: 38,
        data: items
          .filter((it) => it.yKey === yKey)
          .map((it) => ({
            value: it.value,
            name: it.category,
            itemStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: withAlpha(it.color, 'F0') },
                { offset: 0.1, color: withAlpha(it.color, 'E8') },
                { offset: 1, color: withAlpha(it.color, '70') },
              ]),
              borderRadius: 19,
              borderColor: 'rgba(255, 255, 255, 0.4)',
              borderWidth: 1,
              shadowColor: withAlpha(it.color, '30'),
              shadowBlur: 8,
              shadowOffsetY: 0,
            },
          })),
        label: {
          show: true,
          position: 'top' as const,
          color: '#475569',
          fontWeight: 600,
          fontSize: 13,
          distance: 8,
          // ★ 跟 y 轴一样，根据后端 _unitHint 出真函数（"1404.3万"）
          ...(unitHint ? { formatter: makeUnitFormatter(unitHint) } : {}),
        },
      }));
    }

    // DEBUG(threshold): 临时打印 categories / threshold / thresholdX（定位红线是否真的在左边界）
    if (thresholdX !== undefined && typeof window !== 'undefined' && (window as any).__dbg_threshold__) {
      console.log('[THR_DBG]', { threshold, categories, thresholdX });
    }

    // 给每个 bar series 叠加阈值竖线（如流失预警 R_churn 红线）
    if (thresholdX !== undefined) {
      const thresholdFormatter = Number.isInteger(threshold)
        ? `${thresholdLabel} ${threshold}天`
        : `${thresholdLabel} ${threshold}天`;
      const markLine = {
        symbol: 'none' as const,
        silent: true,
        // 关键：用第二个（隐藏 value）轴定位，才能精确落在浮点坐标（桶左边界），
        // category 轴只认整数索引，传浮点会被忽略导致红线掉回柱子正中。
        xAxisIndex: 1,
        lineStyle: { color: '#DC2626', width: 3 },
        label: {
          show: true,
          formatter: thresholdFormatter,
          color: '#FFFFFF',
          fontWeight: 700 as const,
          fontSize: 12,
          // end：标签落在竖直线段「顶端外侧」，横排（不再沿线段旋转成竖排）
          position: 'end' as const,
          // 负向 Y 偏移把标签向上推远，避免压到柱顶数字
          offset: [0, -12] as [number, number],
          backgroundColor: '#DC2626',
          padding: [4, 8],
          borderRadius: 4,
        },
        data: [{ xAxis: thresholdX }],
      };
      series = series.map((s) => ({ ...s, markLine }));
    }

    const option: EChartsCoreOption = {
      title: titleText
        ? {
            text: titleText,
            left: 'center',
            top: 8,
            textStyle: { color: '#1E293B', fontSize: 16, fontWeight: 600 },
          }
        : undefined,
      tooltip: {
        trigger: 'item',
        backgroundColor: 'rgba(255, 255, 255, 0.85)',
        borderColor: '#E2E8F0',
        borderWidth: 1,
        padding: [10, 16],
        textStyle: { color: '#475569', fontWeight: 'bold' },
        extraCssText: 'box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); backdrop-filter: blur(8px); border-radius: 12px;',
        formatter: (p: { data: { value: number; name: string }; dataIndex: number; seriesIndex: number }) => {
          const color = customPalette[(p.seriesIndex * categories.length + p.dataIndex) % customPalette.length];
          const valueText = makeUnitFormatter(unitHint)(Number(p.data.value));
          return `<div style="display:flex; align-items:center; gap:8px;">
                      <span style="display:inline-block; width:10px; height:10px; border-radius:50%; background-color:${color};"></span>
                      <span>${p.data.name} : ${valueText}</span>
                  </div>`;
        },
      },
      grid: { left: 64, right: 24, top: titleText ? 56 : 36, bottom: xAxisName ? 56 : 36, containLabel: true },
      // 双 X 轴：第 1 个 category 给柱子，第 2 个隐藏 value 轴（min=0, max=桶数-1）给阈值 markLine 定位浮点坐标
      xAxis: [
        {
          type: 'category',
          name: xAxisName,
          nameLocation: 'middle' as const,
          nameGap: 30,
          nameTextStyle: { color: '#475569', fontWeight: 600, fontSize: 13 },
          data: categories,
          axisLabel: {
            color: '#64748B',
            fontWeight: 600,
            fontSize: 13,
            interval: 'auto',
            rotate: 0,
            hideOverlap: true,
          },
          axisLine: { lineStyle: { color: 'rgba(148,163,184,0.45)' } },
          axisTick: { show: false },
        },
        {
          type: 'value',
          show: false,
          min: 0,
          max: Math.max(categories.length - 1, 1),
          splitNumber: Math.max(categories.length - 1, 1),
        },
      ],
      yAxis: {
        type: 'value',
        name: yAxisName,
        nameLocation: 'middle' as const,
        nameGap: yAxisNameGap,
        nameTextStyle: { color: '#475569', fontWeight: 600, fontSize: 13 },
        axisLabel: {
          color: '#64748B',
          fontWeight: 500,
          fontSize: 13,
          // ★ 后端只传 _unitHint（"万"/"亿" 纯字符串），前端据此写出真 JS 函数
          ...(unitHint ? { formatter: makeUnitFormatter(unitHint) } : {}),
        },
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { show: true, lineStyle: { type: 'dashed', color: 'rgba(255, 255, 255, 0.45)', width: 1 } },
      },
      toolbox: {
        show: true,
        left: 'right',
        right: 20,
        top: 6,
        orient: 'horizontal',
        itemSize: 16,
        itemGap: 12,
        z: 9999,
        iconStyle: { borderColor: '#8B7FB0' },
        feature: { saveAsImage: { title: '下载图片', name: titleText || 'chart' } },
      },
      series,
    };

    chart.setOption(option);
    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(chartDom);
    return () => {
      ro.disconnect();
      chart.dispose();
    };
  }, [chartNode, title]);

  return <div ref={ref} style={{ width: '100%', height, borderRadius: 24 }} />;
};

export default EtherealBarChart;
