/* GLMapView - ECharts GL 3D 地图渲染组件（中国地图 + 散点 + 飞线） */
import React, { useEffect, useRef, useState } from 'react';
import * as echarts from 'echarts/core';
import type { EChartsOption } from './EChartView';

interface Props {
  option: EChartsOption | null;
  height?: number;
  title?: string;
}

// 中国地图 GeoJSON 数据（阿里云 DataV 免费 API）
const CHINA_GEO_URL = 'https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json';

export default function GLMapView({ option, height = 500, title }: Props) {
  const domRef = useRef<HTMLDivElement>(null);
  const instanceRef = useRef<echarts.ECharts | null>(null);
  const [mapLoaded, setMapLoaded] = useState(false);
  const [error, setError] = useState(false);

  // 加载中国地图 GeoJSON
  useEffect(() => {
    let cancelled = false;
    fetch(CHINA_GEO_URL)
      .then((r) => r.json())
      .then((geo) => {
        if (cancelled) return;
        echarts.registerMap('china', geo);
        setMapLoaded(true);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      });
    return () => { cancelled = true; };
  }, []);

  // 渲染地图
  useEffect(() => {
    const el = domRef.current;
    if (!el || !option || !mapLoaded) return;

    let chart = instanceRef.current;
    if (!chart) {
      chart = echarts.init(el, undefined, { renderer: 'webgl' });
      instanceRef.current = chart;
    }

    chart.setOption({ ...option, backgroundColor: 'transparent' }, { notMerge: true });

    const onResize = () => chart?.resize();
    window.addEventListener('resize', onResize);
    return () => { window.removeEventListener('resize', onResize); };
  }, [option, mapLoaded]);

  useEffect(() => {
    return () => {
      if (instanceRef.current) {
        instanceRef.current.dispose();
        instanceRef.current = null;
      }
    };
  }, []);

  if (error) {
    return (
      <div className="glass-card p-4">
        {title && <h3 className="text-sm font-medium text-slate-300 mb-3">{title}</h3>}
        <div style={{ height }} className="flex items-center justify-center text-slate-400 text-sm">
          地图加载失败（需要网络连接）
        </div>
      </div>
    );
  }

  if (!mapLoaded) {
    return (
      <div className="glass-card p-4">
        {title && <h3 className="text-sm font-medium text-slate-300 mb-3">{title}</h3>}
        <div style={{ height }} className="flex flex-col items-center justify-center gap-3">
          <div className="w-8 h-8 rounded-full border-2 border-[#7DD3FC] border-t-transparent animate-spin" />
          <span className="text-slate-500 text-xs">加载中国地图数据...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="glass-card p-4" data-echart-wrapper>
      {title && <h3 className="text-sm font-medium text-slate-300 mb-3">{title}</h3>}
      <div ref={domRef} style={{ height: `${height}px`, width: '100%' }} />
    </div>
  );
}
