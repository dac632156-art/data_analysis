import React, { useEffect, useRef } from 'react';
import * as echarts from 'echarts';

/**
 * 同期群（下三角）热力矩阵 — 完全复刻「可视化模板库/同期群分析/下三角热力图组件.js」的白底仙气粉蓝风。
 *
 * 数据源：后端产出的扁平清单 [{ 首单月, Index_j, value }]
 *  - 优先用 props.rawData，其次 chartNode.data
 *  - value === -1 为后端哨兵值（未观测），归入浅灰「无数据」格
 *  - 下三角靠 yAxis.inverse: true 实现
 */

interface RetentionMatrixProps {
  chartNode?: any;
  rawData?: any;
  title?: string;
  height?: number | string;
  cardBgUrl?: string;
  /** 'percent'（默认，留存率类，乘100加%）；'number'（客单价/净毛利类，原始数值不加%） */
  valueFormat?: 'percent' | 'number';
  onReady?: (chart: any) => void;
}

/** 数值格式化：percent 模式乘100加%，number 模式千分位+2位小数 */
function fmtValue(v: number, mode: 'percent' | 'number'): string {
  if (mode === 'percent') {
    return (v * 100).toFixed(1) + '%';
  }
  return Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

const PINK_BLUE_RAMP = ['#D6E5FA', '#E2DAF4', '#EDCEEC', '#F6C3E2', '#FCB8D7', '#FFAECC'];
const W0_COLOR = '#FF9EA6';
const EMPTY_COLOR = 'rgba(248, 250, 252, 0.7)';
const MAX_COLUMNS = 12;
const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function fmtMonthLabel(value: string): string {
  const date = new Date(value + '-01');
  return MONTH_NAMES[date.getMonth()] + " '" + value.substring(2, 4);
}

const EtherealRetentionMatrix: React.FC<RetentionMatrixProps> = ({
  chartNode,
  rawData,
  title,
  height = 520,
  cardBgUrl,
  valueFormat = 'percent',
  onReady,
}) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const instRef = useRef<echarts.ECharts | null>(null);

  const rows = (rawData && rawData.length ? rawData : (chartNode?.data || [])) as Array<{
    首单月: string;
    Index_j: number;
    value: number;
  }>;


  useEffect(() => {
    if (!chartRef.current) return;
    if (instRef.current) instRef.current.dispose();
    const myChart = echarts.init(chartRef.current);
    instRef.current = myChart;

    // ===== 1. 解析扁平清单 → 三组坐标 =====
    const allMonths = [...new Set(rows.map((item) => item['首单月']))].sort();
    const yAxisData = allMonths.slice(-12);
    const xAxisData = Array.from({ length: MAX_COLUMNS }, (_, i) => 'W' + i);

    const dataValid: number[][] = [];
    const dataW0: number[][] = [];
    const dataEmpty: number[][] = [];
    let minVal = Infinity;
    let maxVal = -Infinity;

    yAxisData.forEach((yMonth, yIndex) => {
      for (let xIndex = 0; xIndex < MAX_COLUMNS; xIndex++) {
        const target = rows.find((item) => item['首单月'] === yMonth && item['Index_j'] === xIndex);
        if (target && target.value !== -1 && target.value !== null && target.value !== undefined) {
          const val = target.value;
          if (xIndex === 0) {
            dataW0.push([xIndex, yIndex, val]);
          } else {
            dataValid.push([xIndex, yIndex, val]);
            if (val < minVal) minVal = val;
            if (val > maxVal) maxVal = val;
          }
        } else {
          dataEmpty.push([xIndex, yIndex, 0]);
        }
      }
    });

    if (minVal === Infinity) minVal = 0;
    if (maxVal === -Infinity) maxVal = 0.1;

    const titleText = title || 'COHORT ANALYSIS: USER RETENTION MATRIX';

    const option: echarts.EChartsOption = {
      backgroundColor: 'transparent',
      toolbox: {
        right: 40,
        top: 10,
        feature: {
          saveAsImage: { title: '下载图片', show: true },
          myExport: {
            show: true,
            title: '导出数据',
            icon: 'path://M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z',
            onclick: function () {
              const exportData = [...dataValid, ...dataW0];
              const blob = new Blob([JSON.stringify(exportData)], { type: 'application/json' });
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url;
              a.download = 'retention_data.json';
              a.click();
            },
          },
        },
      },
      title: {
        text: titleText,
        left: 'center',
        top: '11%',
        textStyle: { color: '#1E293B', fontSize: 22, fontWeight: 'bold', fontFamily: "'Microsoft YaHei', sans-serif" },
      },
      tooltip: {
        position: 'top',
        backgroundColor: 'rgba(255, 255, 255, 0.95)',
        borderColor: '#E2E8F0',
        borderWidth: 1,
        extraCssText: 'box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); border-radius: 8px;',
        textStyle: { color: '#475569', fontWeight: 'bold' },
        formatter: function (p: any) {
          if (p.seriesName === '无数据') return '';
          const yMonth = yAxisData[p.value[1]];
          const wLabel = p.value[0] === 0 ? 'W0（初始）' : `W${p.value[0]}`;
          if (valueFormat === 'number') {
            const label = p.value[0] === 0 ? '初始值' : '数值';
            return `${yMonth} <br/> ${wLabel} ${label}: <span style="color:#FCB8D7">${fmtValue(p.value[2], valueFormat)}</span>`;
          }
          return `${yMonth} <br/> W${p.value[0]} 留存率: <span style="color:#FCB8D7">${(p.value[2] * 100).toFixed(2)}%</span>`;
        },
      },
      grid: { top: '20%', bottom: '5%', left: '13%', right: '7%', containLabel: false },
      xAxis: {
        type: 'category',
        position: 'bottom',
        data: xAxisData,
        splitArea: { show: false },
        axisLabel: { color: '#64748B', fontWeight: 'bold', fontSize: 14, margin: 12 },
        axisLine: { show: false },
        axisTick: { show: false },
      },
      yAxis: {
        type: 'category',
        data: yAxisData,
        inverse: true,
        splitArea: { show: false },
        axisLabel: {
          color: '#475569',
          fontWeight: 'bold',
          fontSize: 14,
          margin: 16,
          formatter: function (value: string) {
            return fmtMonthLabel(value);
          },
        },
        axisLine: { show: false },
        axisTick: { show: false },
      },
      visualMap: {
        type: 'continuous',
        seriesIndex: [0, 1, 2],
        min: minVal,
        max: maxVal,
        show: false,
        inRange: { color: PINK_BLUE_RAMP },
      },
      series: [
        {
          name: '有效留存',
          type: 'heatmap',
          data: dataValid,
          itemStyle: { borderColor: '#FFFFFF', borderWidth: 4, borderRadius: 6 },
          label: {
            show: true,
            color: '#475569',
            fontWeight: 'bold',
            fontSize: 11,
            formatter: (p: any) =>
              valueFormat === 'number'
                ? fmtValue(p.value[2], 'number')
                : p.value[2] === 0
                  ? '0.0%'
                  : (p.value[2] * 100).toFixed(1) + '%',
          },
        },
        {
          name: 'W0初始留存',
          type: 'heatmap',
          data: dataW0,
          itemStyle: { color: W0_COLOR, borderColor: '#FFFFFF', borderWidth: 4, borderRadius: 6 },
          label: {
            show: true,
            color: '#881337',
            fontWeight: 'bold',
            fontSize: 11,
            formatter: (p: any) =>
              valueFormat === 'number'
                ? fmtValue(p.value[2], 'number')
                : (p.value[2] * 100).toFixed(1) + '%',
          },
        },
        {
          name: '无数据',
          type: 'heatmap',
          data: dataEmpty,
          itemStyle: { color: EMPTY_COLOR, borderColor: '#FFFFFF', borderWidth: 4, borderRadius: 6 },
          label: { show: false },
          tooltip: { show: false },
        },
      ],
    };

    myChart.setOption(option);
    if (onReady) onReady(myChart);
    const handleResize = () => myChart.resize();
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      myChart.dispose();
      instRef.current = null;
    };
  }, [rows, title]);

  const hasData = rows.length > 0;

  return (
    <div
      style={{
        position: 'relative',
        height: height,
        borderRadius: 24,
        overflow: 'hidden',
        background: cardBgUrl
          ? `url(${cardBgUrl}) center/cover no-repeat`
          : 'linear-gradient(135deg, #FDF2F8, #EEF2FF, #ECFEFF)',
        boxShadow: '0 18px 50px -12px rgba(168, 162, 196, 0.45)',
        padding: 16,
      }}
    >
      {hasData && (
        <>
          {/* 右侧独立渐变竖条图例 */}
          <div
            style={{
              position: 'absolute',
              right: 22,
              top: '24%',
              bottom: '14%',
              width: 14,
              borderRadius: 8,
              background: `linear-gradient(to bottom, ${PINK_BLUE_RAMP.join(', ')})`,
              boxShadow: '0 4px 12px rgba(168,162,196,0.3)',
            }}
          />
          <div
            style={{
              position: 'absolute',
              right: 2,
              top: 'calc(24% - 18px)',
              fontSize: 11,
              fontWeight: 700,
              color: '#64748B',
            }}
          >
            {(() => {
              const vals = rows.map((r) => r.value).filter((v) => v !== -1 && v != null);
              const max = vals.length ? Math.max(...vals) : 0;
              return valueFormat === 'number' ? fmtValue(max, 'number') : (max * 100).toFixed(1) + '%';
            })()}
          </div>
          <div
            style={{
              position: 'absolute',
              right: 2,
              bottom: 'calc(14% - 4px)',
              fontSize: 11,
              fontWeight: 700,
              color: '#64748B',
            }}
          >
            {(() => {
              const vals = rows.map((r) => r.value).filter((v) => v !== -1 && v != null);
              const min = vals.length ? Math.min(...vals) : 0;
              return valueFormat === 'number' ? fmtValue(min, 'number') : (min * 100).toFixed(1) + '%';
            })()}
          </div>
        </>
      )}

      {hasData ? (
        <div ref={chartRef} style={{ width: '100%', height: '100%' }} />
      ) : (
        <div
          style={{
            width: '100%',
            height: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#64748B',
            fontSize: 14,
            fontWeight: 700,
          }}
        >
          暂无同期群数据
        </div>
      )}
    </div>
  );
};

export { EtherealRetentionMatrix };
