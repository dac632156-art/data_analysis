import React, { memo, useRef, useEffect, useState } from 'react';
import * as echarts from 'echarts';
import 'echarts-gl';
import type { WidgetSlot } from '../../../types/dashboard';
import { useDashboardTheme } from '../ThemeProvider';
import { useLazyLoad } from '../hooks';

// 中国地图 GeoJSON
const CHINA_GEO_URL = 'https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json';
let chinaMapRegistered = false;

interface MapWidgetProps {
  widget: WidgetSlot;
  onFilter?: (field: string, value: string) => void;
  onClick?: (widgetId: string, data: Record<string, unknown>) => void;
  highlightLabel?: string | null;
  isCrossFilterSource?: boolean;
  hasDrillDown?: boolean;
  onDrillDown?: (widgetId: string, dimension: string, nextLevel: string) => void;
}

export const MapWidget: React.FC<MapWidgetProps> = memo(({ widget, onFilter, isCrossFilterSource }) => {
  const theme = useDashboardTheme();
  const { ref: lazyRef, shouldRender } = useLazyLoad<HTMLDivElement>();
  const chartRef = useRef<HTMLDivElement>(null);
  const instanceRef = useRef<echarts.ECharts | null>(null);

  // 注册地图 + 初始化
  useEffect(() => {
    if (!shouldRender || !chartRef.current) return;

    const el = chartRef.current;
    const existing = widget.chart_config?.option as Record<string, unknown>;

    const initMap = async () => {
      // 确保中国地图已注册
      if (!chinaMapRegistered) {
        try {
          const geo = await (await fetch(CHINA_GEO_URL)).json();
          echarts.registerMap('china', geo as any);
          chinaMapRegistered = true;
        } catch {
          console.warn('[MapWidget] 地图 GeoJSON 加载失败');
          return;
        }
      }

      // 如果已有实例，先销毁
      if (instanceRef.current) {
        instanceRef.current.dispose();
      }

      const chart = echarts.init(el, undefined, { renderer: 'canvas' });
      instanceRef.current = chart;

      if (existing) {
        chart.setOption(existing);
      } else {
        chart.setOption({
          title: { text: widget.title, textStyle: { color: '#94a3b8', fontSize: 14 }, left: 'center', top: 'center' },
        });
      }

      // Cross Filter 绑定
      if (isCrossFilterSource) {
        chart.on('click', (params: Record<string, unknown>) => {
          const label = String(params.name || '');
          if (label) {
            window.dispatchEvent(new CustomEvent('dashboard:cross-filter', {
              detail: { widgetId: widget.widget_id, label },
            }));
          }
        });
      }

      const ro = new ResizeObserver(() => chart.resize());
      ro.observe(el);
      // 存储 cleanup 函数供后续 use
      (chart as any)._cleanup = () => { chart.dispose(); ro.disconnect(); };
    };

    initMap();
  }, [shouldRender, widget, theme, isCrossFilterSource]);

  // 销毁
  useEffect(() => {
    return () => {
      const chart = instanceRef.current;
      if (chart) {
        (chart as any)._cleanup?.();
        chart.dispose();
        instanceRef.current = null;
      }
    };
  }, []);

  if (!shouldRender) {
    return (
      <div ref={lazyRef}
        className={`${theme.cardBg} ${theme.cardBorder} border rounded-xl`}
        style={{ height: '400px', padding: theme.cardPadding }}
      />
    );
  }

  return (
    <div ref={lazyRef}
      className={`${theme.cardBg} ${theme.cardBorder} border rounded-xl db-transition animate-db-scale-in ${theme.shadow}`}
      style={{ padding: theme.cardPadding, borderRadius: theme.borderRadius }}
    >
      <div ref={chartRef} className="w-full h-[400px]" />
    </div>
  );
});

MapWidget.displayName = 'MapWidget';
