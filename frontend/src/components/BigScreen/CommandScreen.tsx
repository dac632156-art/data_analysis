/* CommandScreen - 工业级指挥中心大屏 */
import React, { useEffect, useRef, useState, useMemo } from 'react';
import * as echarts from 'echarts/core';
import { EffectScatterChart, LinesChart } from 'echarts/charts';
import { GeoComponent, TooltipComponent, VisualMapComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import { ScrollRankingBoard } from '@jiaminghi/data-view-react';
import AnimatedNumber from '../AnimatedNumber';
import TbHbTable, { type TbHbRow } from '../TbHbTable';
import type { EChartItem, AnalysisPackage } from '../../types/api';

// ★ 注册所有必要组件（2D 地图渲染）
echarts.use([
  EffectScatterChart, LinesChart,
  GeoComponent, TooltipComponent, VisualMapComponent,
  CanvasRenderer,
]);

interface Props {
  kpis: Array<{ title: string; value: string | number; icon?: string; color?: string }>;
  dataPreview?: Record<string, unknown>[];
  categoryCol?: string;
  valueCol?: string;
  echarts?: EChartItem[];
  /** V2：从分析引擎保存的分析包 */
  packages?: AnalysisPackage[];
}

const CHINA_GEO_URL = 'https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json';

/** 省份名 → 经纬度映射 */
const PROVINCE_CENTERS: Record<string, [number, number]> = {
  '北京市': [116.46, 39.92], '天津市': [117.20, 39.13], '上海市': [121.48, 31.22],
  '重庆市': [106.54, 29.59], '河北省': [114.48, 38.03], '山西省': [112.53, 37.87],
  '辽宁省': [123.38, 41.80], '吉林省': [125.35, 43.88], '黑龙江省': [126.63, 45.75],
  '江苏省': [118.78, 32.04], '浙江省': [120.19, 30.26], '安徽省': [117.27, 31.86],
  '福建省': [119.30, 26.08], '江西省': [115.89, 28.68], '山东省': [117.00, 36.65],
  '河南省': [113.65, 34.76], '湖北省': [114.31, 30.52], '湖南省': [112.98, 28.19],
  '广东省': [113.23, 23.16], '广西壮族自治区': [108.33, 22.84], '海南省': [110.35, 20.02],
  '四川省': [104.06, 30.67], '贵州省': [106.71, 26.57], '云南省': [102.73, 25.04],
  '西藏自治区': [91.11, 29.97], '陕西省': [108.95, 34.27], '甘肃省': [103.73, 36.03],
  '青海省': [101.74, 36.56], '宁夏回族自治区': [106.27, 38.47],
  '新疆维吾尔自治区': [87.68, 43.77], '台湾省': [121.50, 25.05],
  '香港特别行政区': [114.17, 22.28], '澳门特别行政区': [113.55, 22.19],
  '内蒙古自治区': [111.65, 40.82],
};

/** 从短名匹配完整 GeoJSON 省份名（如 "上海" → "上海市"） */
function matchProvince(shortName: string): string | null {
  const clean = shortName.replace(/省|市|自治区|特别行政区|壮族|回族|维吾尔/g, '').trim();
  for (const fullName of Object.keys(PROVINCE_CENTERS)) {
    const fullClean = fullName.replace(/省|市|自治区|特别行政区|壮族|回族|维吾尔/g, '').trim();
    if (fullClean === clean || fullName === shortName || fullClean.includes(clean) || clean.includes(fullClean)) {
      return fullName;
    }
  }
  return null;
}

function buildChinaMapOption(echartsCharts?: EChartItem[]): Record<string, unknown> {
  // ★ 从分析页图表中提取真实数据
  type MapItem = { geoName: string; displayName: string; value: number; lng: number; lat: number };
  let mapData: MapItem[] = [];

  if (echartsCharts && echartsCharts.length > 0) {
    for (const chart of echartsCharts) {
      const opt = chart.option || {};
      const geo = (opt as Record<string, unknown>).geo as Record<string, unknown> | undefined;
      const series = ((opt as Record<string, unknown>).series as Array<Record<string, unknown>>) || [];

      // Step 1: 从 geo.regions 提取省份 → 构建基础 mapData
      if (geo?.regions && Array.isArray(geo.regions)) {
        for (const r of geo.regions) {
          const geoName = String((r as Record<string, unknown>).name || '');
          const center = PROVINCE_CENTERS[geoName];
          if (center) {
            mapData.push({ geoName, displayName: geoName, value: 0, lng: center[0], lat: center[1] });
          } else {
            // 尝试模糊匹配
            const matched = matchProvince(geoName);
            if (matched && PROVINCE_CENTERS[matched]) {
              const c = PROVINCE_CENTERS[matched];
              mapData.push({ geoName: matched, displayName: geoName, value: 0, lng: c[0], lat: c[1] });
            }
          }
        }
      }

      // Step 2: 从 scatter/effectScatter 提取数值（按名称匹配而不是坐标）
      for (const s of series) {
        const sType = String(s.type || '');
        if (sType !== 'effectScatter' && sType !== 'scatter') continue;
        if (s.coordinateSystem !== 'geo') continue;

        const scatterData = (s.data as Array<Record<string, unknown>>) || [];
        for (const d of scatterData) {
          const dName = String(d.name || '');
          const dVal = (d.value as number[]) || [];
          if (dVal.length < 3) continue;

          // ★ 如果 mapData 还没构建（geo.regions 可能为空），从散点数据直接构建
          if (mapData.length === 0) {
            const matched = matchProvince(dName);
            const geoName = matched || dName;
            const center = matched ? PROVINCE_CENTERS[matched] : null;
            if (center) {
              mapData.push({ geoName, displayName: dName, value: Number(dVal[2]), lng: center[0], lat: center[1] });
            }
          } else {
            // ★ 按名称模糊匹配到已有 mapData
            const matchedItem = mapData.find((m) => {
              const a = m.geoName.replace(/省|市|自治区|特别行政区|壮族|回族|维吾尔/g, '').trim();
              const b = dName.replace(/省|市|自治区|特别行政区|壮族|回族|维吾尔/g, '').trim();
              return a === b || a.includes(b) || b.includes(a) || m.geoName === dName;
            });

            if (matchedItem) {
              matchedItem.value = Number(dVal[2]);
              if (dName && dName.length < matchedItem.displayName.length) {
                matchedItem.displayName = dName;
              }
            }
          }
        }
        break; // 只取第一个 effectScatter 系列
      }

      // 只取第一张有 geo 或 effectScatter 的地图图表
      if (mapData.length > 0) break;
    }
  }

  // ★ 有真实数据？
  const hasRealData = mapData.length > 0 && mapData.some((d) => d.value > 0);
  const maxVal = hasRealData ? Math.max(...mapData.map((d) => d.value)) : 1;

  // ★ 改为 2D 地图（geo + effectScatter + lines）—— 确保省份名和数据值可靠显示
  const effectScatterData = hasRealData
    ? mapData
        .filter((d) => d.value > 0)
        .map((d) => ({
          name: d.displayName,
          value: [d.lng, d.lat, d.value],
        }))
    : [
        { name: '北京', value: [116.46, 39.92, 1200] },
        { name: '上海', value: [121.48, 31.22, 1100] },
        { name: '广州', value: [113.23, 23.16, 900] },
        { name: '深圳', value: [114.07, 22.62, 850] },
        { name: '成都', value: [104.06, 30.67, 700] },
        { name: '武汉', value: [114.31, 30.52, 650] },
        { name: '杭州', value: [120.19, 30.26, 750] },
      ];

  // 飞线数据
  const linesData = hasRealData
    ? (() => {
        const sorted = [...mapData].filter((d) => d.value > 0).sort((a, b) => b.value - a.value).slice(0, 6);
        if (sorted.length < 2) return [{ coords: [[116.46, 39.92], [121.48, 31.22]] }];
        return sorted.slice(1).map((d) => ({ coords: [[sorted[0].lng, sorted[0].lat], [d.lng, d.lat]] }));
      })()
    : [
        { coords: [[116.46, 39.92], [121.48, 31.22]] },
        { coords: [[116.46, 39.92], [113.23, 23.16]] },
        { coords: [[121.48, 31.22], [114.07, 22.62]] },
        { coords: [[104.06, 30.67], [116.46, 39.92]] },
      ];

  // 省份着色（星空渐变）
  const regions = hasRealData
    ? mapData.map((d) => {
        const ratio = maxVal > 0 ? d.value / maxVal : 0;
        const colors = [
          'rgba(15,12,41,0.6)', 'rgba(45,27,105,0.55)', 'rgba(74,45,138,0.5)',
          'rgba(99,102,241,0.45)', 'rgba(59,130,246,0.4)', 'rgba(6,182,212,0.38)',
          'rgba(34,211,238,0.35)', 'rgba(103,232,249,0.3)',
        ];
        const idx = Math.min(Math.floor(ratio * (colors.length - 1)), colors.length - 1);
        return {
          name: d.geoName,
          itemStyle: { areaColor: colors[idx] },
          label: { show: true, color: '#c4b5fd', fontSize: 10 },
        };
      })
    : [];

  return {
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(15,12,41,0.95)',
      borderColor: '#6366f1',
      borderWidth: 1,
      textStyle: { color: '#e0e7ff', fontSize: 12 },
    },
    geo: {
      map: 'china',
      roam: true,
      zoom: 1.15,
      center: [104.5, 36],
      aspectScale: 0.85,
      regions,
      itemStyle: {
        areaColor: '#0f0c29',
        borderColor: '#312e81',
        borderWidth: 1,
        shadowBlur: 6,
        shadowColor: 'rgba(99,102,241,0.25)',
      },
      emphasis: {
        itemStyle: {
          areaColor: '#4f46e5',
          shadowBlur: 25,
          shadowColor: 'rgba(99,102,241,0.7)',
        },
        label: { show: true, color: '#f0e6ff', fontSize: 14, fontWeight: 'bold' },
      },
    },
    series: [
      {
        type: 'effectScatter',
        coordinateSystem: 'geo',
        data: effectScatterData,
        symbol: 'circle',
        symbolSize: (val: number[]) => Math.max(6, Math.min(18, val[2] / maxVal * 16)),
        showEffectOn: 'render',
        rippleEffect: {
          brushType: 'stroke',
          scale: 4,
          period: 4,
          color: '#818cf8',
        },
        itemStyle: { color: '#e0e7ff', shadowBlur: 10, shadowColor: 'rgba(129,140,248,0.8)' },
        label: {
          show: true,
          position: 'top',
          distance: 10,
          color: '#67e8f9',
          fontSize: 11,
          fontWeight: 'bold',
          formatter: '{c}',
          textShadowBlur: 6,
          textShadowColor: 'rgba(6,182,212,0.6)',
        },
        emphasis: {
          scale: 2,
          itemStyle: { color: '#f0e6ff', shadowBlur: 20 },
          label: { fontSize: 15, color: '#f0e6ff' },
        },
        zlevel: 1,
      },
      {
        type: 'lines',
        coordinateSystem: 'geo',
        data: linesData,
        lineStyle: { color: '#818cf8', width: 1, opacity: 0.4, curveness: 0.2 },
        effect: {
          show: true,
          period: 5,
          trailLength: 0.3,
          trailWidth: 1.5,
          symbolSize: 4,
          color: '#818cf8',
        },
        zlevel: 1,
      },
    ],
  };
}

export default function CommandScreen({ kpis, dataPreview, categoryCol, valueCol, echarts: echartsData, packages }: Props) {
  const chinaRef = useRef<HTMLDivElement>(null);
  const [mapLoaded, setMapLoaded] = useState(false);
  const chinaInst = useRef<echarts.ECharts | null>(null);

  // ★ 用真实数据生成地图配置
  const mapOption = useMemo(() => buildChinaMapOption(echartsData), [echartsData]);

  // ★ 从已保存图表中提取同环比表格数据
  const tbHbCharts = useMemo(() => {
    return (echartsData || [])
      .filter((c) => c.chart_type === 'table' && c.table_data)
      .map((c) => {
        const td = c.table_data!;
        return {
          title: String(c.title || '同环比分析'),
          rows: (td.rows || []) as TbHbRow[],
          value_column: String(td.value_column || ''),
          current_year: String(td.current_year || ''),
          previous_year: td.previous_year ? String(td.previous_year) : null,
          has_yoy: Boolean(td.has_yoy),
        };
      });
  }, [echartsData]);

  useEffect(() => {
    let c = false;
    fetch(CHINA_GEO_URL).then((r) => r.json()).then((geo) => { if (!c) { echarts.registerMap('china', geo); setMapLoaded(true); } }).catch(() => {});
    return () => { c = true; };
  }, []);

  // ★ 2D 中国地图 — 依赖 mapOption 变化时重绘
  useEffect(() => {
    const el = chinaRef.current;
    if (!el || !mapLoaded) return;

    // 如果实例已存在就销毁重建（数据变化时需要重新初始化）
    if (chinaInst.current) {
      chinaInst.current.dispose();
      chinaInst.current = null;
    }

    const chart = echarts.init(el, undefined, { renderer: 'canvas' });
    chinaInst.current = chart;
    chart.setOption(mapOption);
    const r = () => chart?.resize();
    window.addEventListener('resize', r);
    return () => { window.removeEventListener('resize', r); chart.dispose(); };
  }, [mapLoaded, mapOption]);

  // 排名
  const catCol = categoryCol || (dataPreview?.length ? Object.keys(dataPreview[0])[0] : '');
  const valCol = valueCol || (dataPreview?.length ? Object.keys(dataPreview[0]).find((k) => typeof dataPreview[0][k] === 'number') || Object.keys(dataPreview[0])[1] || '' : '');
  const rankingData = (dataPreview || []).slice(0, 5).map((row, i) => ({
    name: String(row[catCol] || `项${i + 1}`),
    value: Number(row[valCol]) || 0,
  }));

  // ★ V2：从分析包中提取 AI 摘要 & 异常预警
  const aiSummary = useMemo(() => {
    if (!packages || packages.length === 0) return [] as string[];
    return packages.filter(p => p.can_run).flatMap(p => p.insights || []).slice(0, 5);
  }, [packages]);
  const anomalyAlerts = useMemo(() => {
    if (!packages || packages.length === 0) return [] as string[];
    return packages
      .filter(p => p.analysis_type === 'anomaly_analysis' && p.can_run)
      .flatMap(p => p.insights || [])
      .slice(0, 3);
  }, [packages]);

  const KPIRow = ({ kpi }: { kpi: Props['kpis'][0] }) => {
    const color = kpi.color || '#22d3ee';
    const numVal = typeof kpi.value === 'number' ? kpi.value : parseFloat(String(kpi.value));
    return (
      <div className="flex items-center justify-between py-2" style={{ borderBottom: '1px solid rgba(34,211,238,0.06)' }}>
        <span className="text-[11px] text-slate-400 truncate">{kpi.title}</span>
        <span className="text-sm font-bold font-mono" style={{ color, textShadow: `0 0 12px ${color}40` }}>
          <AnimatedNumber value={isNaN(numVal) ? 0 : numVal} duration={1.5} decimals={numVal % 1 !== 0 ? 2 : 0} />
        </span>
      </div>
    );
  };

  return (
    <div className="w-full h-full flex flex-col"
      style={{
        background: `radial-gradient(ellipse at center, #0a1628 0%, #050d1a 50%, #020810 100%)`,
        fontFamily: "'PingFang SC', 'Microsoft YaHei', system-ui, sans-serif",
        overflow: 'auto',
      }}
    >
      {/* 顶部标题栏 */}
      <div className="flex items-center justify-between px-6 py-3" style={{ borderBottom: '1px solid rgba(34,211,238,0.12)' }}>
        <div className="flex items-center gap-4">
          <div className="w-1.5 h-6 bg-gradient-to-b from-[#22d3ee] to-[#8b5cf6] rounded-full" />
          <h1 className="text-xl font-bold text-white tracking-widest" style={{ textShadow: '0 0 30px rgba(34,211,238,0.6)' }}>数据智能指挥中心</h1>
        </div>
        <div className="flex items-center gap-8 text-xs">
          <span className="flex items-center gap-2 text-[#22d3ee]">
            <span className="w-2 h-2 rounded-full bg-[#22d3ee] animate-pulse shadow-[0_0_8px_#22d3ee]" />系统运行中
          </span>
          <span className="text-slate-400 font-mono">{new Date().toLocaleString('zh-CN')}</span>
        </div>
      </div>

      {/* 主内容区 */}
      <div className="flex-1 flex gap-3 p-3" style={{ minHeight: 0 }}>

        {/* 左侧面板 */}
        <div className="flex flex-col gap-3" style={{ width: '22%', minWidth: 240 }}>
          <div className="flex-1 flex flex-col gap-2" style={{
            background: 'rgba(34,211,238,0.03)',
            border: '1px solid rgba(34,211,238,0.08)',
            borderRadius: '8px',
            padding: '10px 14px',
          }}>
            <div className="text-xs text-[#22d3ee] font-semibold mb-2 tracking-wider">📊 数据总览</div>
            <div className="flex flex-col gap-0.5">
              {kpis.slice(0, 4).map((kpi, i) => <KPIRow key={i} kpi={kpi} />)}
            </div>
            <div className="flex-1" />
            <div className="text-xs text-[#a78bfa] font-semibold mb-2 tracking-wider">📋 数据预览</div>
            <div className="overflow-auto" style={{ height: '160px' }}>
              {/* ... 数据预览表格 ... */}
              {dataPreview && dataPreview.length > 0 ? (
                <table className="w-full text-[10px]">
                  <thead>
                    <tr style={{ background: 'rgba(139,92,246,0.1)' }}>
                      <th className="px-2 py-1.5 text-left text-slate-500">#</th>
                      {Object.keys(dataPreview[0]).slice(0, 3).map((k) => <th key={k} className="px-2 py-1.5 text-left text-slate-500">{k}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {dataPreview.slice(0, 6).map((row, i) => (
                      <tr key={i} className="border-t border-white/[0.03] hover:bg-[#22d3ee]/[0.05]">
                        <td className="px-2 py-1 text-slate-600">{i + 1}</td>
                        {Object.keys(dataPreview[0]).slice(0, 3).map((k) => <td key={k} className="px-2 py-1 text-slate-300">{String(row[k] ?? '-')}</td>)}
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="flex items-center justify-center h-full text-slate-500 text-xs">暂无数据</div>
              )}
            </div>
            {/* V2: AI 摘要 */}
            {aiSummary.length > 0 && (
              <div className="mt-3 pt-2 border-t border-white/[0.06]">
                <div className="text-xs text-[#f59e0b] font-semibold mb-2 tracking-wider">🤖 AI 摘要</div>
                <div className="overflow-auto" style={{ maxHeight: '120px' }}>
                  {aiSummary.map((ins, i) => (
                    <p key={i} className="text-[10px] text-slate-400 mb-1 leading-relaxed">{ins}</p>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* 中间主屏 - 中国数据态势 */}
        <div className="flex-1 relative" style={{
          background: 'rgba(34,211,238,0.02)',
          border: '1px solid rgba(34,211,238,0.08)',
          borderRadius: '8px',
          overflow: 'hidden',
        }}>
          <div className="absolute top-3 left-4 z-10 text-xs text-[#22d3ee] tracking-wider">🇨🇳 国内数据态势</div>
          {!mapLoaded ? (
            <div className="flex items-center justify-center h-full text-slate-500 text-xs">
              <div className="w-6 h-6 rounded-full border-2 border-[#22d3ee] border-t-transparent animate-spin mr-3" />
              加载地图数据...
            </div>
          ) : (
            <div ref={chinaRef} style={{ width: '100%', height: '100%' }} />
          )}
        </div>

        {/* 右侧面板 */}
        <div className="flex flex-col gap-3" style={{ width: '22%', minWidth: 240 }}>
          <div className="flex-1 flex flex-col gap-2" style={{
            background: 'rgba(34,211,238,0.03)',
            border: '1px solid rgba(34,211,238,0.08)',
            borderRadius: '8px',
            padding: '10px 14px',
          }}>
            <div className="text-xs text-[#22d3ee] font-semibold mb-2 tracking-wider">⚡ 关键指标</div>
            <div className="flex flex-col gap-0.5">
              {kpis.slice(4, 8).map((kpi, i) => <KPIRow key={i} kpi={kpi} />)}
            </div>
            <div className="flex-1" />
            <div className="text-xs text-[#a78bfa] font-semibold mb-2 tracking-wider">🏆 数据排行 TOP5</div>
            <div style={{ height: '150px', minHeight: 150 }}>
              {rankingData.length > 0 ? (
                <ScrollRankingBoard
                  config={{
                    data: rankingData,
                    rowNum: 5,
                    sort: true,
                    waitTime: 3000,
                    carousel: 'single',
                    color: ['#22d3ee', '#8b5cf6'],
                  }}
                  style={{ width: '100%', height: '100%' }}
                />
              ) : (
                <div className="flex items-center justify-center h-full text-slate-500 text-xs">无排行数据</div>
              )}
            </div>
            {/* V2: 异常预警 */}
            {anomalyAlerts.length > 0 && (
              <div className="mt-3 pt-2 border-t border-white/[0.06]">
                <div className="text-xs text-[#f87171] font-semibold mb-2 tracking-wider">⚠️ 异常预警</div>
                <div className="overflow-auto" style={{ maxHeight: '100px' }}>
                  {anomalyAlerts.map((alert, i) => (
                    <p key={i} className="text-[10px] text-red-400/70 mb-1 leading-relaxed">{alert}</p>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ★ 同环比表格（从已保存图表中提取） */}
      {tbHbCharts.length > 0 && (
        <div className="px-3 pb-3">
          {tbHbCharts.map((tb, idx) => (
            <div key={idx} className="p-4 rounded-lg" style={{ background: 'rgba(10,14,30,0.95)', border: '1px solid rgba(34,211,238,0.12)' }}>
              <TbHbTable
                data={tb.rows}
                valueColumn={tb.value_column}
                currentYear={tb.current_year}
                previousYear={tb.previous_year}
                hasYoY={tb.has_yoy}
                maxHeight="380px"
              />
            </div>
          ))}
        </div>
      )}

      {/* 底部信息条 */}
      <div className="px-6 py-2 flex items-center gap-6 text-xs"
        style={{ background: 'rgba(34,211,238,0.04)', borderTop: '1px solid rgba(34,211,238,0.08)' }}>
        <span className="text-[#22d3ee] font-semibold">数据源</span>
        <span className="text-slate-600">|</span>
        <span className="text-slate-400">{dataPreview ? `共 ${dataPreview.length} 条记录` : '实时监控中'}</span>
        <span className="text-slate-600">•</span>
        <span className="text-slate-400">更新于 {new Date().toLocaleTimeString('zh-CN')}</span>
        <div className="flex-1" />
        <span className="text-slate-600">ECharts + DataV</span>
      </div>
    </div>
  );
}
