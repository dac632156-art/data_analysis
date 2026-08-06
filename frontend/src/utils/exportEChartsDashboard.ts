/* 生成自包含 ECharts 交互式 HTML 大屏文件，保留所有 ECharts 交互和深色主题 */
import type { EChartItem, ReportDegradation } from '../types/api';
import type { CardItem, CardMeta } from '../components/cardTypes';
import { Palette, ChartStyle, withAlpha } from '../theme';

// ★ 导出 HTML 统一配色（Single Source of Truth = frontend/src/theme，禁止写死）
// 大屏/报告里所有品牌色必须从这里派生；保留 ${color}40 这类 8 位 alpha 写法有效。
const REPORT_THEME = {
  primary: Palette.primary,
  primaryHover: Palette.primaryHover,
  interaction: Palette.interaction,
  success: Palette.success,
  danger: Palette.danger,
  warning: Palette.warning,
  textMuted: Palette.textMuted,
  textSecondary: Palette.textSecondary,
  content: Palette.tooltipContent,
  glow: (a: number) => withAlpha(Palette.primary, a),
};

interface KPI {
  title: string;
  value: string | number;
  icon?: string;
  color?: string;
  unit?: string;
}

type Template = 'immersive' | 'medical' | 'command';

interface RingChartData { name: string; value: number; }
interface RingChartConfig { title: string; data: RingChartData[]; }

const COMMON_CSS = `
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', system-ui, -apple-system, sans-serif;
  background: #050816;
  color: #e2e8f0;
  min-height: 100vh;
  overflow-x: hidden;
}
.highlight-bar {
  display: none;
}
.highlight-bar.active {
  display: flex;
}
`;

function makeHeader(title: string, center = false) {
  return `
<div style="display:flex;align-items:center;justify-content:${center ? 'center' : 'space-between'};padding:16px 32px;border-bottom:2px solid rgba(56,189,248,0.15);position:relative;">
  <div style="display:flex;align-items:center;gap:16px;">
    <div style="width:8px;height:32px;background:linear-gradient(180deg,#38BDF8,#7DD3FC);border-radius:4px;"></div>
    <h1 style="font-size:28px;font-weight:700;letter-spacing:0.05em;text-shadow:0 0 25px rgba(56,189,248,0.5);">${title}</h1>
  </div>
  <div style="display:flex;align-items:center;gap:24px;font-size:13px;color:#94a3b8;${center ? 'position:absolute;right:32px;top:50%;transform:translateY(-50%);' : ''}">
    <span style="display:flex;align-items:center;gap:8px;">
      <span style="width:8px;height:8px;border-radius:50%;background:#34D399;animation:pulse 2s infinite;"></span>
      实时数据
    </span>
    <span style="font-family:monospace;">${new Date().toLocaleString('zh-CN')}</span>
  </div>
</div>
<style>@keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.4; } }</style>`;
}

function makeKPICard(kpi: KPI) {
  const color = kpi.color || REPORT_THEME.primary;
  const trendHtml = (kpi as any).trend && (kpi as any).trend !== 'flat' && (kpi as any).change != null && (kpi as any).change !== 0
    ? `<p style="font-size:10px;font-weight:600;margin-top:2px;color:${(kpi as any).trend === 'up' ? '#34D399' : '#FB7185'}">${(kpi as any).trend === 'up' ? '↑' : '↓'} ${Math.abs((kpi as any).change) >= 100 ? Math.abs((kpi as any).change).toFixed(0) : Math.abs((kpi as any).change).toFixed(1)}%</p>`
    : '';
  return `
<div style="flex:1;min-width:0;padding:16px;border-radius:12px;background:rgba(56,189,248,0.08);border:1px solid rgba(56,189,248,0.15);">
  <div style="font-size:24px;margin-bottom:4px;">${kpi.icon || '📊'}</div>
  <p style="font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:4px;">${kpi.title}</p>
  <p style="font-size:22px;font-weight:700;color:${color};text-shadow:0 0 10px ${color}40;">${kpi.value}</p>
  ${trendHtml}
</div>`;
}

interface TableDataRaw {
  rows?: unknown[][];
  columns?: string[];
}

function convertTableData(tableData: TableDataRaw): Record<string, unknown>[] {
  if (!tableData || !tableData.rows || !tableData.columns) return [];
  return tableData.rows.map(row => {
    const obj: Record<string, unknown> = {};
    tableData.columns!.forEach((col, idx) => {
      obj[col] = row[idx];
    });
    return obj;
  });
}

function makeChartDiv(id: string, title: string, height: number, hideTitle: boolean, chartType?: string, tableData?: TableDataRaw, span = false) {
  const spanStyle = span ? 'grid-column:span 3;' : '';
  const titleHtml = hideTitle ? '' : `
<div style="padding:10px 16px;border-bottom:1px solid rgba(56,189,248,0.1);display:flex;align-items:center;gap:10px;">
  <span style="width:8px;height:8px;border-radius:50%;background:#38BDF8;"></span>
  <span style="font-size:13px;font-weight:600;color:#cbd5e1;">${title}</span>
</div>`;

  if (chartType === 'table' && tableData) {
    const convertedData = convertTableData(tableData);
    const tableHtml = makeTableHTML(convertedData);
    return `
<div data-chart-wrapper style="${spanStyle}border-radius:16px;overflow:hidden;background:rgba(15,23,42,0.7);border:1px solid rgba(56,189,248,0.15);">
  ${titleHtml}
  <div style="width:100%;padding:12px;overflow:auto;max-height:${hideTitle ? height : height - 40}px;">
    ${tableHtml}
  </div>
</div>`;
  }

  if (chartType === 'analysis_table' && tableData) {
    const columns = tableData.columns || [];
    const rows = tableData.rows || [];
    let theadHtml = `<thead><tr style="background:rgba(125,211,252,0.1);"><th style="padding:8px 12px;text-align:left;font-size:11px;font-weight:600;color:#94a3b8;border-bottom:1px solid rgba(125,211,252,0.15);">${columns.join('</th><th style="padding:8px 12px;text-align:left;font-size:11px;font-weight:600;color:#94a3b8;border-bottom:1px solid rgba(125,211,252,0.15);">')}</th></tr></thead>`;
    let tbodyHtml = '<tbody>';
    rows.forEach((row: unknown[], ri: number) => {
      tbodyHtml += `<tr style="border-bottom:1px solid rgba(125,211,252,0.04);background:${ri % 2 === 0 ? 'rgba(15,23,42,0.5)' : 'transparent'};">`;
      row.forEach((cell: unknown) => {
        const val = cell !== null && cell !== undefined ? String(cell) : '-';
        tbodyHtml += `<td style="padding:8px 12px;font-size:11px;color:#e2e8f0;">${val}</td>`;
      });
      tbodyHtml += '</tr>';
    });
    tbodyHtml += '</tbody>';
    return `
<div data-chart-wrapper style="${spanStyle}border-radius:16px;overflow:hidden;background:rgba(15,23,42,0.7);border:1px solid rgba(56,189,248,0.15);">
  ${titleHtml}
  <div style="width:100%;padding:12px;overflow:auto;max-height:${hideTitle ? height : height - 40}px;">
    <table style="width:100%;border-collapse:collapse;">${theadHtml}${tbodyHtml}</table>
  </div>
</div>`;
  }

  return `
<div data-chart-wrapper style="${spanStyle}border-radius:16px;overflow:hidden;background:rgba(15,23,42,0.7);border:1px solid rgba(56,189,248,0.15);">
  ${titleHtml}
  <div id="${id}" style="width:100%;height:${hideTitle ? height : height - 40}px;"></div>
</div>`;
}

/** 环形图专用：去掉 overflow:hidden，避免 ECharts 渲染时边缘被裁 */
function makeRingChartDiv(id: string, title: string, height: number, hideTitle: boolean) {
  const titleHtml = hideTitle ? '' : `
<div style="padding:10px 16px;border-bottom:1px solid rgba(56,189,248,0.1);display:flex;align-items:center;gap:10px;">
  <span style="width:8px;height:8px;border-radius:50%;background:#38BDF8;"></span>
  <span style="font-size:13px;font-weight:600;color:#cbd5e1;">${title}</span>
</div>`;
  return `
<div data-chart-wrapper style="border-radius:16px;background:rgba(15,23,42,0.7);border:1px solid rgba(56,189,248,0.15);">
  ${titleHtml}
  <div id="${id}" style="width:100%;height:${hideTitle ? height : height - 40}px;"></div>
</div>`;
}

function makeEChartsScript(charts: (EChartItem | { id?: string; title: string; option: any })[], hideTitle: boolean) {
  // 过滤掉表格类型的图表，它们不需要 ECharts 初始化
  const validCharts = charts.filter((c) => (c as EChartItem).chart_type !== 'table' && (c as EChartItem).chart_type !== 'analysis_table');
  // 序列化每个图表的 option，安全处理 NaN / Infinity / undefined
  const chartConfigs = validCharts.map((c, i) => {
    const optionStr = JSON.stringify(c.option, (key, val) => {
      // 跳过无法序列化的值
      if (typeof val === 'function') return undefined;
      if (val === undefined) return undefined;
      // NaN 和 Infinity 转为 null（ECharts 能正确处理 null 作为缺省值）
      if (typeof val === 'number' && !Number.isFinite(val)) return null;
      return val;
    });
    const chartId = ((c as any).id) || `chart_${i}`;
    return `{ id: ${JSON.stringify(chartId)}, title: ${JSON.stringify(c.title)}, option: ${optionStr} }`;
  }).join(',\n        ');

  return `
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<script>
  (function() {
    var charts = [
        ${chartConfigs}
    ];

    var highlightLabel = null;
    var lastClickTime = 0;
    var DIM_OPACITY = 0.15;
    var globalFilterValues = {};

    function resetAllCharts() {
      highlightLabel = null;
      var bar = document.getElementById('highlight-bar');
      if (bar) bar.classList.remove('active');
      charts.forEach(function(c) {
        var el = document.getElementById(c.id);
        if (!el) return;
        var chart = echarts.getInstanceByDom(el);
        if (!chart) return;
        // 恢复原始 option
        chart.setOption(c.option, { notMerge: true });
      });
      // 清除高亮后仍需保留已激活的全局筛选
      applyGlobalFiltersToAll();
    }

    function createHighlightBar() {
      var bar = document.createElement('div');
      bar.id = 'highlight-bar';
      bar.className = 'highlight-bar';
      bar.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:99999;display:none;align-items:center;justify-content:center;gap:12px;padding:8px 16px;background:rgba(56,189,248,0.15);border-bottom:1px solid rgba(56,189,248,0.2);';
      bar.innerHTML = '<span style="font-size:13px;color:#7DD3FC;">🔗 联动高亮：<strong id="highlight-label-text" style="color:#fff;"></strong></span>' +
        '<button id="clear-highlight-btn" style="padding:4px 12px;font-size:12px;border-radius:6px;background:rgba(56,189,248,0.3);border:1px solid rgba(56,189,248,0.3);color:#7DD3FC;cursor:pointer;font-family:inherit;">✕ 清除高亮</button>' +
        '<span style="font-size:10px;color:#64748b;">点击图表数据项可联动，点击空白区域或此按钮清除</span>';
      document.body.appendChild(bar);
      document.getElementById('clear-highlight-btn').addEventListener('click', resetAllCharts);
    }

    function updateHighlightBar(label) {
      var bar = document.getElementById('highlight-bar');
      var labelText = document.getElementById('highlight-label-text');
      if (!bar || !labelText) return;
      if (label) {
        labelText.textContent = label;
        bar.classList.add('active');
        bar.style.display = 'flex';
      } else {
        bar.classList.remove('active');
        bar.style.display = 'none';
      }
    }

    // ★ 判断 series 是否匹配 label
    function seriesMatchesLabel(option, series, label) {
      var sName = String(series.name || '');
      var sType = String(series.type || 'bar');
      if (sName === label) return true;
      if (sType === 'pie' || sType === 'treemap' || sType === 'wordCloud') {
        var data = series.data || [];
        return data.some(function(d) { return typeof d === 'object' && d !== null && !Array.isArray(d) && String(d.name || '') === label; });
      }
      var xAxis = option.xAxis;
      var xData = (Array.isArray(xAxis) ? xAxis[0] : xAxis)?.data;
      if (xData && ['bar','line','area','histogram','boxplot','scatter','bubble'].includes(sType)) {
        return xData.some(function(c) { return String(c) === label; });
      }
      return false;
    }

    // ★ 安全包装数据项
    function wrapDataItem(d, extraStyle) {
      if (d === null || d === undefined) return { value: d, itemStyle: Object.assign({}, extraStyle) };
      if (Array.isArray(d)) return { value: d.slice(), itemStyle: Object.assign({}, extraStyle) };
      if (typeof d === 'object') {
        var existing = d.itemStyle || {};
        var merged = Object.assign({}, typeof d, d, { itemStyle: Object.assign({}, existing, extraStyle) });
        return merged;
      }
      return { value: d, itemStyle: Object.assign({}, extraStyle) };
    }

    // ★ 找到匹配的数据点索引
    function findMatchingIndices(option, series, label) {
      var data = series.data || [];
      var sName = String(series.name || '');
      var sType = String(series.type || '');
      if (sName === label) return data.map(function(_, i) { return i; });
      var matching = [];
      if (sType === 'pie' || sType === 'treemap' || sType === 'wordCloud' || sType === 'radar') {
        data.forEach(function(d, i) {
          if (typeof d === 'object' && d !== null && !Array.isArray(d) && String(d.name || '') === label) matching.push(i);
        });
        return matching;
      }
      var xAxis = option.xAxis;
      var xData = (Array.isArray(xAxis) ? xAxis[0] : xAxis)?.data;
      if (xData && ['bar','line','area','histogram','boxplot','scatter','bubble'].includes(sType)) {
        xData.forEach(function(cat, i) { if (String(cat) === label && i < data.length) matching.push(i); });
        return matching;
      }
      return matching;
    }

    // ★ 应用高亮/淡化到 option
    function applyHighlightBlur(option, label) {
      var result = JSON.parse(JSON.stringify(option));
      result.backgroundColor = 'transparent';
      var series = result.series || [];
      result.series = series.map(function(s) {
        var sType = String(s.type || 'bar');
        var matchingIndices = findMatchingIndices(option, s, label);
        if (matchingIndices.length > 0) {
          // 有匹配 → 匹配点正常，非匹配点淡化
          if (sType === 'radar') {
            s.lineStyle = Object.assign({}, s.lineStyle, { width: 3, opacity: 1 });
            s.areaStyle = Object.assign({}, s.areaStyle, { opacity: 0.35 });
            s.itemStyle = Object.assign({}, s.itemStyle, { opacity: 1 });
            s.symbolSize = 8;
          } else {
            var data = s.data || [];
            s.data = data.map(function(d, i) {
              var isMatch = matchingIndices.includes(i);
              return wrapDataItem(d, { opacity: isMatch ? 1 : DIM_OPACITY });
            });
            if (sType === 'line' || sType === 'area') {
              s.lineStyle = Object.assign({}, s.lineStyle, { opacity: 0.6, width: 3 });
              if (sType === 'area') s.areaStyle = Object.assign({}, s.areaStyle, { opacity: 0.3 });
            }
          }
        } else {
          // 无匹配 → 整个 series 淡化
          if (sType === 'radar') {
            s.lineStyle = Object.assign({}, s.lineStyle, { opacity: DIM_OPACITY });
            s.areaStyle = Object.assign({}, s.areaStyle, { opacity: 0.03 });
            s.itemStyle = Object.assign({}, s.itemStyle, { opacity: DIM_OPACITY });
            s.symbolSize = 3;
          } else if (sType === 'line' || sType === 'area') {
            s.lineStyle = Object.assign({}, s.lineStyle, { opacity: DIM_OPACITY });
            s.areaStyle = Object.assign({}, s.areaStyle, { opacity: 0.03 });
            s.itemStyle = Object.assign({}, s.itemStyle, { opacity: DIM_OPACITY });
          } else {
            var data2 = s.data || [];
            if (data2.length > 0) {
              s.data = data2.map(function(d) { return wrapDataItem(d, { opacity: DIM_OPACITY }); });
            } else {
              s.itemStyle = Object.assign({}, s.itemStyle, { opacity: DIM_OPACITY });
            }
          }
        }
        return s;
      });
      return result;
    }

    // ★ 应用高亮
    function applyHighlight(label) {
      highlightLabel = label;
      updateHighlightBar(label);
      charts.forEach(function(c) {
        var el = document.getElementById(c.id);
        if (!el) return;
        var chart = echarts.getInstanceByDom(el);
        if (!chart) return;
        if (label) {
          var newOption = applyHighlightBlur(c.option, label);
          chart.setOption(newOption, { notMerge: true });
        } else {
          chart.setOption(c.option, { notMerge: true });
        }
      });
    }

    // ★ 应用全局筛选（多个筛选值取并集，仅淡化无关类别，不影响无关图表）
    function applyGlobalFilters(option, labels) {
      if (!labels || labels.length === 0) return option;
      var result = JSON.parse(JSON.stringify(option));
      result.backgroundColor = 'transparent';
      var anyMatch = false;
      function inSet(name) {
        for (var i = 0; i < labels.length; i++) {
          if (String(labels[i]) === String(name)) return true;
        }
        return false;
      }
      var series = result.series || [];
      result.series = series.map(function(s) {
        var sType = String(s.type || 'bar');
        var data = s.data || [];
        var matched = [];
        if (['pie', 'treemap', 'wordCloud', 'radar'].indexOf(sType) !== -1) {
          data.forEach(function(d, i) {
            if (d && typeof d === 'object' && !Array.isArray(d) && inSet(d.name)) matched.push(i);
          });
        } else {
          var xAxis = option.xAxis;
          var xAxisObj = Array.isArray(xAxis) ? xAxis[0] : xAxis;
          var xData = xAxisObj && xAxisObj.data;
          if (xData && Array.isArray(xData)) {
            xData.forEach(function(cat, i) { if (i < data.length && inSet(cat)) matched.push(i); });
          } else if (inSet(s.name)) {
            matched = data.map(function(_, i) { return i; });
          }
        }
        // 本 series 无匹配 → 保持不变（不淡化整张无关图表）
        if (matched.length === 0) return s;
        anyMatch = true;
        s.data = data.map(function(d, i) {
          return wrapDataItem(d, { opacity: matched.indexOf(i) !== -1 ? 1 : DIM_OPACITY });
        });
        if (sType === 'line' || sType === 'area') {
          s.lineStyle = Object.assign({}, s.lineStyle, { opacity: 0.6, width: 3 });
          if (sType === 'area') s.areaStyle = Object.assign({}, s.areaStyle, { opacity: 0.3 });
        }
        return s;
      });
      // 整张图都无匹配 → 原样保留
      return anyMatch ? result : option;
    }

    function applyGlobalFiltersToAll() {
      var labels = [];
      for (var k in globalFilterValues) {
        if (globalFilterValues[k]) labels.push(globalFilterValues[k]);
      }
      charts.forEach(function(c) {
        var el = document.getElementById(c.id);
        if (!el) return;
        var chart = echarts.getInstanceByDom(el);
        if (!chart) return;
        chart.setOption(applyGlobalFilters(c.option, labels), { notMerge: true });
      });
    }

    // 供导出 HTML 中筛选下拉的 onchange 调用
    window.onGlobalFilterChange = function(field, value) {
      globalFilterValues[field] = value || '';
      applyGlobalFiltersToAll();
    };

    // ★ 处理点击事件
    function processClick(idx, params) {
      var now = Date.now();
      if (now - lastClickTime < 250) return;
      lastClickTime = now;

      var seriesType = String(params.seriesType || '');
      var label = seriesType === 'radar'
        ? String(params.seriesName || params.name || '')
        : String(params.name || params.seriesName || '');

      if (!label || label === 'undefined') return;

      if (label === highlightLabel) {
        applyHighlight(null);
      } else {
        applyHighlight(label);
      }
    }

    // ★ 存储因父容器 display:none 而延迟初始化的图表（索引 → option）
    var deferredCharts = {};

    function initOneChart(c, idx) {
      var el = document.getElementById(c.id);
      if (!el) return;
      // 容器仍不可见 → 继续延迟
      if (el.offsetWidth === 0 || el.offsetHeight === 0) {
        deferredCharts[c.id] = { config: c, index: idx };
        return;
      }
      delete deferredCharts[c.id];
      var chart = echarts.init(el);
      var option = JSON.parse(JSON.stringify(c.option));
      option.backgroundColor = 'transparent';
      // ★ 深空背景下轴标保险：补充浅色轴标（已有则不覆盖），兼容旧 saved_packages
      function ensureAxisLabelColor(axis) {
        if (!axis) return;
        if (Array.isArray(axis)) { axis.forEach(ensureAxisLabelColor); return; }
        axis.axisLabel = axis.axisLabel || {};
        if (!axis.axisLabel.color) axis.axisLabel.color = '#94A3B8';
      }
      if (option.xAxis) ensureAxisLabelColor(option.xAxis);
      if (option.yAxis) ensureAxisLabelColor(option.yAxis);
      chart.setOption(option);

      chart.on('click', function(params) {
        processClick(idx, params);
      });

      chart.getZr().on('click', function(e) {
        if (!e.target) {
          applyHighlight(null);
        }
      });
    }

    function renderAllCharts() {
      charts.forEach(function(c, idx) {
        initOneChart(c, idx);
      });

      createHighlightBar();

      window.addEventListener('resize', function() {
        charts.forEach(function(c) {
          var el = document.getElementById(c.id);
          if (!el) return;
          var chart = echarts.getInstanceByDom(el);
          if (chart) chart.resize();
        });
      });
    }

    // ★ 初始化某个面板内的所有延迟图表（供 switchTab 调用）
    function initDeferredChartsInPanel(panelId) {
      var deferredEntries = Object.keys(deferredCharts);
      if (deferredEntries.length === 0) return;
      var panel = document.getElementById(panelId);
      if (!panel) return;
      deferredEntries.forEach(function(chartId) {
        var el = document.getElementById(chartId);
        // 如果该元素在当前面板或其子元素中（至少在其可见区域内）
        if (el && panel.contains(el)) {
          var item = deferredCharts[chartId];
          if (item) initOneChart(item.config, item.index);
        }
      });
    }

    function ready(fn) {
      if (document.readyState === 'complete') {
        setTimeout(fn, 300);
      } else {
        window.addEventListener('load', function() { setTimeout(fn, 300); });
      }
    }

    if (typeof echarts !== 'undefined') {
      ready(renderAllCharts);
    } else {
      var check = setInterval(function() {
        if (typeof echarts !== 'undefined') {
          clearInterval(check);
          ready(renderAllCharts);
        }
      }, 50);
    }
  })();
</script>`;
}

// ========== 各布局 HTML 生成 ==========

// 检测 option 是否为 3D GL 类型（与 EGridLayout.isGLOption 一致）
function isGLOptionExport(option: any): boolean {
  if (!option) return false;
  if (option.geo3D) return true;
  const series = option.series || [];
  const glTypes = ['scatter3D', 'bar3D', 'line3D', 'lines3D', 'surface', 'map3D'];
  return series.some((s: any) => glTypes.includes(String(s.type || '')));
}

function buildImmersiveLayout(kpis: KPI[], charts: EChartItem[], title: string, hideTitle: boolean): string {
  const kpiHtml = kpis.slice(0, 4).map(k => {
    const color = k.color || '#7DD3FC';
    return `<div style="text-align:center;">
    <p style="font-size:10px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:6px;">${k.title}</p>
    <p style="font-size:24px;font-family:monospace;font-weight:700;color:${color};text-shadow:0 0 20px ${color}50;">${k.value}</p>
  </div>`;
  }).join('\n  ');

  const isGrid = charts.length >= 4;
  const gridStyle = isGrid
    ? 'grid-template-columns:2fr 1fr 1fr;grid-template-rows:1fr 1fr;'
    : 'grid-template-columns:1fr 1fr;grid-template-rows:1fr;';

  const chartHtml = charts.length > 0 ? `
<div style="display:grid;gap:12px;padding:0 16px 24px;${gridStyle}">
  ${charts.map((c, i) => {
    const isMain = i === 0 && isGrid;
    const chartH = isMain ? 560 : 300;
    const titleColor = isMain ? '#7DD3FC' : '#38BDF8';
    const titleHtml = hideTitle ? '' : '<div style="padding:10px 16px;border-bottom:1px solid #1e1e3a80;display:flex;align-items:center;gap:10px;">' +
      '<span style="width:10px;height:10px;border-radius:50%;background:' + titleColor + ';"></span>' +
      '<span style="font-size:13px;font-weight:600;color:#cbd5e1;">' + c.title + '</span>' +
      '</div>';
    if (c.chart_type === 'table' && c.table_data) {
      return '<div data-chart-wrapper style="border-radius:16px;overflow:hidden;background:rgba(10,10,30,0.8);border:1px solid rgba(56,189,248,0.15);position:relative;' + (isMain ? 'grid-row:span 2;' : '') + '">' +
        titleHtml +
        '<div style="width:100%;padding:12px;overflow:auto;max-height:' + chartH + 'px;">' +
        makeTableHTML(convertTableData(c.table_data)) +
        '</div></div>';
    }
    return '<div data-chart-wrapper style="border-radius:16px;overflow:hidden;background:rgba(10,10,30,0.8);border:1px solid rgba(56,189,248,0.15);position:relative;' + (isMain ? 'grid-row:span 2;' : '') + '">' +
      titleHtml +
      '<div id="chart_' + i + '" style="width:100%;height:' + chartH + 'px;"></div></div>';
  }).join('\n  ')}
</div>` : '<div style="padding:60px;text-align:center;color:#64748b;font-size:18px;">暂无图表</div>';

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${title} - 数据大屏</title>
<style>${COMMON_CSS}</style>
</head>
<body style="min-height:100vh;background:radial-gradient(ellipse at 50% 0%,#1a1040 0%,#050510 70%);">
<div style="display:flex;align-items:center;justify-content:space-between;padding:24px 32px;">
  <div><h1 style="font-size:30px;font-weight:700;color:#fff;letter-spacing:0.2em;text-shadow:0 0 50px rgba(56,189,248,0.6);">⚡ ${title}</h1></div>
  <div style="display:flex;align-items:center;gap:32px;">
    ${kpiHtml}
    <span style="font-size:13px;color:#64748b;font-family:monospace;">${new Date().toLocaleTimeString('zh-CN')}</span>
  </div>
</div>
${chartHtml}
${makeEChartsScript(charts, hideTitle)}
</body>
</html>`;
}

// ========== 数据看板 (medical) 布局 HTML 生成 ==========

function buildRingChartEChartsOption(data: RingChartData[], title: string, chartHeight?: number) {
  const mainItem = data[0] || { name: '', value: 0 };
  const colors = [REPORT_THEME.primaryHover, REPORT_THEME.interaction, REPORT_THEME.warning, REPORT_THEME.success, REPORT_THEME.danger];
  // 紧凑模式：高度不足 250px 时，收缩环形图避免被容器裁剪
  const compact = chartHeight !== undefined && chartHeight < 250;
  const centerY = compact ? '48%' : '55%';
  const centerX = compact ? '38%' : '42%';
  const radiusInner = compact ? '38%' : '45%';
  const radiusOuter = compact ? '55%' : '65%';
  const legendConfig: any = compact
    ? { orient: 'vertical' as const, right: '10%', top: 'center', itemGap: 4 }
    : { orient: 'vertical' as const, right: '8%', top: 'center', itemGap: 8 };
  const titleFontSize = compact ? 16 : 22;
  const titleLineHeight = compact ? 22 : 30;
  const subLineHeight = compact ? 13 : 18;
  return {
    tooltip: {
      trigger: 'item' as const,
      backgroundColor: 'rgba(10,22,40,0.95)',
      borderColor: 'rgba(125,211,252,0.3)',
      textStyle: { color: '#e2e8f0', fontSize: 11 },
      formatter: '{b}: {c} ({d}%)',
    },
    legend: {
      ...legendConfig,
      textStyle: { color: '#64748b', fontSize: 10 },
      itemWidth: 8, itemHeight: 8,
    },
    series: [{
      type: 'pie' as const,
      radius: [radiusInner, radiusOuter],
      center: [centerX, centerY],
      avoidLabelOverlap: false,
      itemStyle: { borderRadius: 6, borderColor: '#0a1628', borderWidth: 2 },
      label: { show: false },
      emphasis: { scale: true, scaleSize: 5 },
      data: data.map((d, i) => ({
        ...d,
        itemStyle: { color: colors[i % colors.length] }
      })),
    }, {
      type: 'pie' as const,
      radius: ['0%', '0%'],
      center: [centerX, centerY],
      silent: true,
      label: {
        show: true,
        position: 'center',
        formatter: `{a|${mainItem.value.toLocaleString()}}\n{b|${mainItem.name}}`,
        rich: {
          a: { fontSize: titleFontSize, fontWeight: 'bold' as const, color: '#7DD3FC', lineHeight: titleLineHeight, textShadow: '0 0 10px rgba(125,211,252,0.5)' },
          b: { fontSize: 12, color: '#94a3b8', lineHeight: subLineHeight }
        }
      },
      data: [{ value: 0, name: '' }]
    }],
  };
}

function buildRadarOption(data: number[], color: string) {
  return {
    tooltip: {
      trigger: 'item' as const,
      backgroundColor: 'rgba(10,22,40,0.95)',
      borderColor: 'rgba(125,211,252,0.3)',
      textStyle: { color: '#e2e8f0', fontSize: 11 },
    },
    radar: {
      indicator: [
        { name: '维度A', max: 100 }, { name: '维度B', max: 100 },
        { name: '维度C', max: 100 }, { name: '维度D', max: 100 },
        { name: '维度E', max: 100 }, { name: '维度F', max: 100 },
      ],
      radius: '60%', center: ['50%', '58%'], splitNumber: 4,
      axisName: { color: '#64748b', fontSize: 9, padding: [2, 4] },
      splitLine: { lineStyle: { color: 'rgba(125,211,252,0.1)' } },
      splitArea: { areaStyle: { color: ['rgba(125,211,252,0.01)', 'rgba(125,211,252,0.04)'] } },
      axisLine: { lineStyle: { color: 'rgba(125,211,252,0.15)' } }
    },
    series: [{
      type: 'radar' as const,
      data: [{
        value: data,
        areaStyle: { color: `${color}33` },
        lineStyle: { color, width: 2 },
        itemStyle: { color },
        symbol: 'circle', symbolSize: 4,
      }]
    }]
  };
}

function makeTableHTML(tableData: Record<string, unknown>[], maxRows?: number) {
  if (!tableData || tableData.length === 0) return '<div style="padding:20px;text-align:center;color:#64748b;">暂无数据</div>';
  const headers = Object.keys(tableData[0] || {});
  const rows = maxRows ? tableData.slice(0, maxRows) : tableData;
  const formatVal = (v: unknown) => {
    if (v === null || v === undefined) return '-';
    if (typeof v === 'number') {
      if (!Number.isFinite(v)) return '-';
      if (Number.isInteger(v)) return v.toLocaleString();
      return v.toFixed(2);
    }
    return String(v);
  };
  return `
<table style="width:100%;border-collapse:collapse;font-size:12px;">
  <thead>
    <tr>${headers.map(h => `<th style="padding:10px 12px;text-align:left;font-weight:600;color:#7DD3FC;border-bottom:1px solid rgba(56,189,248,0.2);font-size:11px;text-transform:uppercase;letter-spacing:0.05em;">${h}</th>`).join('')}</tr>
  </thead>
  <tbody>
    ${rows.map((row, i) => `<tr style="${i % 2 === 0 ? 'background:rgba(15,23,42,0.5)' : ''}">
      ${headers.map(h => `<td style="padding:8px 12px;border-bottom:1px solid rgba(56,189,248,0.06);color:#cbd5e1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:180px;">${formatVal(row[h])}</td>`).join('')}
    </tr>`).join('\n    ')}
  </tbody>
</table>`;
}

function buildMedicalLayout(
  cards: CardItem[],
  meta: CardMeta | undefined,
  title: string,
  hideTitle: boolean,
): string {
  const esc = (s: unknown) =>
    String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

  // ---- 分类卡片（与 MedicalDashboard 完全一致） ----
  const kpis: CardItem[] = [];
  const trendCharts: CardItem[] = [];
  const mapCharts: CardItem[] = [];
  const rankingCards: CardItem[] = [];
  const tableCards: CardItem[] = [];
  const insightCards: CardItem[] = [];
  const warningCards: CardItem[] = [];
  for (const c of cards) {
    const t = c.type;
    const ti = (c.title || '').toLowerCase();
    const isTrend = /trend|趋势|growth|增长|累计|cumul/i.test(ti) || t === 'chart';
    const isMap = /map|地图|region|区域|省份|geo/i.test(ti);
    const isRank = /rank|排名|top|排行/i.test(ti);
    const isTable = t === 'table';
    const isInsight = t === 'insight';
    const isWarning = t === 'warning';
    const isKpi = t === 'kpi';
    if (isKpi) kpis.push(c);
    else if (isWarning) warningCards.push(c);
    else if (isInsight) insightCards.push(c);
    else if (isMap) mapCharts.push(c);
    else if (isRank) rankingCards.push(c);
    else if (isTable) tableCards.push(c);
    else if (isTrend) trendCharts.push(c);
    else kpis.push(c);
  }

  const topKpis = kpis.slice(0, 8);
  const mainTrend = trendCharts.find(c => c.size === 'xl' || c.size === 'l') || trendCharts[0];
  const subTrends = trendCharts.filter(c => c !== mainTrend).slice(0, 2);
  const mainRank = rankingCards[0];
  const sideRanks = rankingCards.slice(1, 3);
  const warnings = warningCards.slice(0, 2);
  const insights = insightCards.slice(0, 4);

  // ---- 图表 items（供 ECharts 脚本渲染） ----
  const chartItems: Array<{ id: string; title: string; option: any }> = [];
  // 与图表卡片渲染逻辑保持一致：option 优先取 data.option，
  // 否则对于 chart 卡片，后端 card_generator._chart_card 把 option 直接存在 data 上
  const getOption = (card: CardItem): any => {
    const d = (card.data || {}) as Record<string, unknown>;
    if (d && d.option) return d.option;
    if (card.type === 'chart') return d || null;
    return null;
  };
  let chartAutoId = 0;
  const chartBlockHtml = (card: CardItem, height: number) => {
    const opt = getOption(card);
    if (!opt) return `<div style="padding:24px;text-align:center;color:#64748b;font-size:12px;">暂无图表数据</div>`;
    const id = `med_chart_${chartAutoId++}`;
    chartItems.push({ id, title: card.title || '', option: opt });
    return `<div style="border-radius:12px;padding:16px;background:rgba(15,23,42,0.5);border:1px solid rgba(125,211,252,0.08);">
      <h3 style="font-size:14px;font-weight:600;color:#38BDF8;margin-bottom:12px;">${esc(card.title)}</h3>
      <div id="${id}" style="width:100%;height:${height}px;"></div>
    </div>`;
  };

  const cardTableHtml = (card: CardItem, maxRows: number) => {
    const d = (card.data || {}) as Record<string, unknown>;
    const rows = (d.rows as unknown[][]) || [];
    const columns = (d.columns as string[]) || [];
    if (!columns.length || !rows.length) return `<div style="padding:24px;text-align:center;color:#64748b;font-size:12px;">暂无数据</div>`;
    const fmt = (v: unknown) => {
      if (v === null || v === undefined) return '-';
      if (typeof v === 'number') return Number.isInteger(v) ? v.toLocaleString() : v.toFixed(2);
      if (typeof v === 'object') return 'value' in (v as any) ? String((v as any).value) : '-';
      return String(v);
    };
    const body = rows.slice(0, maxRows).map((row, ri) => `<tr style="${ri % 2 === 0 ? 'background:rgba(15,23,42,0.5)' : ''};border-bottom:1px solid rgba(125,211,252,0.06);">
      ${columns.map((col, ci) => `<td style="padding:8px 12px;color:#cbd5e1;white-space:nowrap;">${esc(fmt(row[ci]))}</td>`).join('')}
    </tr>`).join('\n');
    return `<div style="overflow:auto;">
      <table style="width:100%;border-collapse:collapse;font-size:12px;">
        <thead><tr>${columns.map(col => `<th style="padding:8px 12px;text-align:left;font-weight:600;color:#94a3b8;border-bottom:1px solid rgba(125,211,252,0.2);">${esc(col)}</th>`).join('')}</tr></thead>
        <tbody>${body}</tbody>
      </table>
    </div>`;
  };

  const rankOrTableHtml = (card: CardItem, maxRows: number) => {
    const opt = getOption(card);
    return opt ? chartBlockHtml(card, 200) : cardTableHtml(card, maxRows);
  };

  const textBlockHtml = (card: CardItem, bg: string, border: string) => {
    const d = (card.data || {}) as Record<string, unknown>;
    const text = String(d.text || d.content || d.message || card.title || '');
    return `<div style="border-radius:12px;padding:12px;background:${bg};border:1px solid ${border};">
      <p style="font-size:12px;color:#cbd5e1;line-height:1.7;">${text ? esc(text) : '暂无内容'}</p>
    </div>`;
  };

  // 预警块：与 WarningBlock 一致，带 ⚠️ 图标 + flex 布局
  const warningBlockHtml = (card: CardItem) => {
    const d = (card.data || {}) as Record<string, unknown>;
    const text = String(d.text || d.message || card.title || '');
    return `<div style="border-radius:12px;padding:12px;display:flex;align-items:flex-start;gap:8px;background:rgba(245,158,11,0.06);border:1px solid rgba(245,158,11,0.2);">
      <span style="font-size:14px;margin-top:2px;">⚠️</span>
      <p style="font-size:12px;color:#cbd5e1;line-height:1.7;">${text ? esc(text) : '暂无内容'}</p>
    </div>`;
  };

  // 排行榜卡片：有 rows/columns 则渲染绿框表格，否则回退图表（与 RankingBlock 一致）
  const rankingCardHtml = (card: CardItem, maxRows: number) => {
    const d = (card.data || {}) as Record<string, unknown>;
    const rows = d?.rows as unknown[][] | undefined;
    const columns = d?.columns as string[] | undefined;
    if (columns && rows && rows.length > 0) {
      return `<div style="border-radius:12px;padding:16px;background:rgba(15,23,42,0.5);border:1px solid rgba(16,185,129,0.08);">
        <h3 style="font-size:14px;font-weight:600;color:#34D399;margin-bottom:12px;">${esc(card.title)}</h3>
        ${cardTableHtml(card, maxRows)}
      </div>`;
    }
    return rankOrTableHtml(card, maxRows);
  };

  // 明细数据卡片：橙框表格（与 TableBlock 一致）
  const detailCardHtml = (card: CardItem, maxRows: number) =>
    `<div style="border-radius:12px;padding:16px;background:rgba(15,23,42,0.5);border:1px solid rgba(245,158,11,0.08);">
      <h3 style="font-size:14px;font-weight:600;color:#FBBF24;margin-bottom:12px;">${esc(card.title)}</h3>
      ${cardTableHtml(card, maxRows)}
    </div>`;

  const kpiColorMap: Record<string, string> = {
    sum: '#38BDF8', rate: '#34D399', change: '#FB7185',
    avg: '#38BDF8', count: '#FBBF24',
  };
  const kpiCardHtml = (card: CardItem) => {
    const d = (card.data || {}) as Record<string, unknown>;
    const value = String(d?.value ?? d?.formatted ?? '0');
    const change = d?.change as string | null;
    const kpiType = d?.kpi_type as string;
    const color = kpiColorMap[kpiType] || '#38BDF8';
    const isUp = change && !String(change).startsWith('-') && String(change) !== '0';
    const isDown = change && String(change).startsWith('-');
    const changeHtml = change
      ? `<p style="font-size:12px;font-weight:700;color:${isUp ? '#34D399' : isDown ? '#FB7185' : '#94a3b8'}">${isUp ? '▲' : isDown ? '▼' : '—'} ${esc(String(change).replace(/[+%]/g, ''))}%</p>`
      : '';
    return `<div style="border-radius:12px;padding:16px;background:rgba(15,23,42,0.6);border:1px solid rgba(125,211,252,0.08);">
      <p style="font-size:10px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:8px;">${esc(card.title)}</p>
      <p style="font-size:24px;font-weight:700;font-family:monospace;color:${color};text-shadow:0 0 12px ${color}55;margin-bottom:4px;">${esc(value)}</p>
      ${changeHtml}
    </div>`;
  };

  const sectionTitle = (barColor: string, label: string) =>
    `<div style="display:flex;align-items:center;gap:8px;margin-bottom:16px;">
      <div style="width:4px;height:16px;background:${barColor};border-radius:2px;"></div>
      <h2 style="font-size:12px;font-weight:700;color:#94a3b8;letter-spacing:0.1em;text-transform:uppercase;">${label}</h2>
    </div>`;

  const metaHtml = meta ? `<div style="display:flex;gap:24px;font-size:12px;color:#64748b;">
    <span>共 <span style="color:#22D3EE;font-weight:700;">${esc(meta.total_cards)}</span> 张卡片</span>
    <span>洞察强度 <span style="color:#A78BFA;font-weight:700;">${esc(meta.insight_strength)}</span></span>
    <span>数据质量 <span style="color:#34D399;font-weight:700;">${esc(meta.data_quality)}</span></span>
  </div>` : '';

  const kpiRow = topKpis.length ? `<section style="border-radius:16px;padding:20px;background:rgba(6,182,212,0.03);border:1px solid rgba(6,182,212,0.1);">
    ${sectionTitle('#22D3EE', '核心指标')}
    <div style="display:grid;gap:16px;grid-template-columns:repeat(${Math.min(topKpis.length, 4)}, 1fr);">
      ${topKpis.map(kpiCardHtml).join('\n')}
    </div>
  </section>` : '';

  const trendRow = (mainTrend || subTrends.length) ? `<section style="border-radius:16px;padding:20px;background:rgba(56,189,248,0.03);border:1px solid rgba(56,189,248,0.1);">
    ${sectionTitle('#A78BFA', '趋势分析')}
    <div style="display:flex;flex-direction:column;gap:24px;">
      ${mainTrend ? chartBlockHtml(mainTrend, 320) : ''}
      ${subTrends.length ? `<div style="display:grid;gap:24px;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));">${subTrends.map(t => chartBlockHtml(t, 200)).join('\n')}</div>` : ''}
    </div>
  </section>` : '';

  // Row 3：与屏幕一致，左右两栏并排——左「排行榜」(emerald)，右「明细数据」(amber)
  const rankTableRow = `<div style="display:grid;gap:24px;grid-template-columns:1fr 1fr;">
    <section style="border-radius:16px;padding:20px;background:rgba(16,185,129,0.03);border:1px solid rgba(16,185,129,0.1);">
      ${sectionTitle('#34D399', '排行榜')}
      <div style="display:flex;flex-direction:column;gap:16px;">
        ${mainRank ? rankingCardHtml(mainRank, 6) : ''}
        ${sideRanks.map(r => rankingCardHtml(r, 6)).join('\n')}
      </div>
    </section>
    <section style="border-radius:16px;padding:20px;background:rgba(245,158,11,0.03);border:1px solid rgba(245,158,11,0.1);">
      ${sectionTitle('#FBBF24', '明细数据')}
      <div style="display:flex;flex-direction:column;gap:16px;">
        ${tableCards.slice(0, 2).map(t => detailCardHtml(t, 8)).join('\n')}
      </div>
    </section>
  </div>`;

  const insightRow = (warnings.length || insights.length) ? `<section style="border-radius:16px;padding:20px;background:rgba(244,63,94,0.03);border:1px solid rgba(244,63,94,0.1);">
    ${sectionTitle('#FB7185', '分析与洞察')}
    <div style="display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));">
      ${warnings.map(w => warningBlockHtml(w)).join('\n')}
      ${insights.map(i => textBlockHtml(i, 'rgba(56,189,248,0.04)', 'rgba(125,211,252,0.1)')).join('\n')}
    </div>
  </section>` : '';

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${esc(title)} - 数据看板</title>
<style>
${COMMON_CSS}
body { background:linear-gradient(180deg,#020518 0%,#060d2a 50%,#0a0a1e 100%); }
</style>
</head>
<body style="min-height:100vh;background:linear-gradient(180deg,#020518 0%,#060d2a 50%,#0a0a1e 100%);">
  <div style="display:flex;align-items:center;justify-content:space-between;padding:16px 32px;border-bottom:1px solid rgba(125,211,252,0.15);">
    <div style="display:flex;align-items:center;gap:16px;">
      <div style="width:6px;height:40px;background:linear-gradient(180deg,#7DD3FC,#38BDF8);border-radius:4px;"></div>
      <h1 style="font-size:20px;font-weight:700;color:#fff;letter-spacing:0.1em;text-shadow:0 0 20px rgba(125,211,252,0.4);">${esc(title)}</h1>
    </div>
    ${metaHtml}
  </div>
  <div style="padding:24px;display:flex;flex-direction:column;gap:24px;">
    ${kpiRow}
    ${trendRow}
    ${rankTableRow}
    ${insightRow}
  </div>
  ${makeEChartsScript(chartItems, hideTitle)}
</body>
</html>`;
}

// ========== 指挥中心辅助：地图 + 同环比（与 CommandScreen / TbHbTable 一致） ==========
const COMMAND_PROVINCE_CENTERS: Record<string, [number, number]> = {
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

function commandMatchProvince(shortName: string): string | null {
  const clean = shortName.replace(/省|市|自治区|特别行政区|壮族|回族|维吾尔/g, '').trim();
  for (const fullName of Object.keys(COMMAND_PROVINCE_CENTERS)) {
    const fullClean = fullName.replace(/省|市|自治区|特别行政区|壮族|回族|维吾尔/g, '').trim();
    if (fullClean === clean || fullName === shortName || fullClean.includes(clean) || clean.includes(fullClean)) return fullName;
  }
  return null;
}

interface CommandMapData {
  hasRealData: boolean;
  maxVal: number;
  effectScatterData: { name: string; value: [number, number, number] }[];
  linesData: { coords: [[number, number], [number, number]] }[];
  regions: Record<string, unknown>[];
}

// 从 echarts 真实图表提取地图散点 + 飞线（移植自 CommandScreen.buildChinaMapOption）
function computeCommandMap(echartsData?: EChartItem[]): CommandMapData {
  type MapItem = { geoName: string; displayName: string; value: number; lng: number; lat: number };
  let mapData: MapItem[] = [];
  if (echartsData && echartsData.length > 0) {
    for (const chart of echartsData) {
      const opt = chart.option || {};
      const geo = (opt as Record<string, unknown>).geo as Record<string, unknown> | undefined;
      const series = ((opt as Record<string, unknown>).series as Array<Record<string, unknown>>) || [];
      if (geo?.regions && Array.isArray(geo.regions)) {
        for (const r of geo.regions as Array<Record<string, unknown>>) {
          const geoName = String(r.name || '');
          const center = COMMAND_PROVINCE_CENTERS[geoName];
          if (center) mapData.push({ geoName, displayName: geoName, value: 0, lng: center[0], lat: center[1] });
          else {
            const matched = commandMatchProvince(geoName);
            if (matched && COMMAND_PROVINCE_CENTERS[matched]) {
              const c = COMMAND_PROVINCE_CENTERS[matched];
              mapData.push({ geoName: matched, displayName: geoName, value: 0, lng: c[0], lat: c[1] });
            }
          }
        }
      }
      for (const s of series) {
        const sType = String(s.type || '');
        if (sType !== 'effectScatter' && sType !== 'scatter') continue;
        if (s.coordinateSystem !== 'geo') continue;
        const scatterData = (s.data as Array<Record<string, unknown>>) || [];
        for (const d of scatterData) {
          const dName = String(d.name || '');
          const dVal = (d.value as number[]) || [];
          if (dVal.length < 3) continue;
          if (mapData.length === 0) {
            const matched = commandMatchProvince(dName);
            const geoName = matched || dName;
            const center = matched ? COMMAND_PROVINCE_CENTERS[matched] : null;
            if (center) mapData.push({ geoName, displayName: dName, value: Number(dVal[2]), lng: center[0], lat: center[1] });
          } else {
            const matchedItem = mapData.find((m) => {
              const a = m.geoName.replace(/省|市|自治区|特别行政区|壮族|回族|维吾尔/g, '').trim();
              const b = dName.replace(/省|市|自治区|特别行政区|壮族|回族|维吾尔/g, '').trim();
              return a === b || a.includes(b) || b.includes(a) || m.geoName === dName;
            });
            if (matchedItem) {
              matchedItem.value = Number(dVal[2]);
              if (dName && dName.length < matchedItem.displayName.length) matchedItem.displayName = dName;
            }
          }
        }
        break;
      }
      if (mapData.length > 0) break;
    }
  }
  const hasRealData = mapData.length > 0 && mapData.some((d) => d.value > 0);
  const maxVal = hasRealData ? Math.max(...mapData.map((d) => d.value)) : 1;
  const colors = ['rgba(15,12,41,0.6)', 'rgba(45,27,105,0.55)', 'rgba(74,45,138,0.5)', 'rgba(59,130,246,0.45)', 'rgba(59,130,246,0.4)', 'rgba(6,182,212,0.38)', 'rgba(125,211,252,0.35)', 'rgba(103,232,249,0.3)'];
  const effectScatterData = hasRealData
    ? mapData.filter((d) => d.value > 0).map((d) => ({ name: d.displayName, value: [d.lng, d.lat, d.value] as [number, number, number] }))
    : [];
  const linesData = hasRealData
    ? (() => {
        const sorted = [...mapData].filter((d) => d.value > 0).sort((a, b) => b.value - a.value).slice(0, 6);
        if (sorted.length < 2) return [] as { coords: [[number, number], [number, number]] }[];
        return sorted.slice(1).map((d) => ({ coords: [[sorted[0].lng, sorted[0].lat], [d.lng, d.lat]] as [[number, number], [number, number]] }));
      })()
    : [];
  const regions = hasRealData
    ? mapData.map((d) => {
        const ratio = maxVal > 0 ? d.value / maxVal : 0;
        const idx = Math.min(Math.floor(ratio * (colors.length - 1)), colors.length - 1);
        return { name: d.geoName, itemStyle: { areaColor: colors[idx] }, label: { show: true, color: '#BFDBFE', fontSize: 10 } };
      })
    : [];
  return { hasRealData, maxVal, effectScatterData, linesData, regions };
}

// 同环比表复刻（与 TbHbTable 一致）
const cmdEsc = (s: string): string =>
  String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c] || c));
const TBHB_MONTHS = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'];
function tbHbFormatValue(v: number | null | undefined): string {
  if (v === null || v === undefined) return '--';
  if (Math.abs(v) >= 100_000_000) return `${(v / 100_000_000).toFixed(2)}亿`;
  if (Math.abs(v) >= 10_000) return `${(v / 10_000).toFixed(2)}万`;
  return v.toLocaleString('zh-CN', { maximumFractionDigits: 2 });
}
function tbHbFormatRate(rate: number | null | undefined, isFirst: boolean): { html: string; color: string } {
  if (rate === null || rate === undefined) return { html: '--', color: '#9ca3af' };
  if (isFirst) return { html: '--', color: '#9ca3af' };
  const pct = (rate as number) * 100;
  const formatted = Number.isInteger(pct) ? `${pct}%` : `${pct.toFixed(2)}%`;
  if ((rate as number) > 0.001) return { html: `🔺 +${formatted}`, color: '#FB7185' };
  if ((rate as number) < -0.001) return { html: `🔻 ${formatted}`, color: '#22c55e' };
  return { html: '➖ 0%', color: '#9ca3af' };
}
function tbHbTableHtml(chart: EChartItem): string {
  const td = chart.table_data as Record<string, unknown> | undefined;
  if (!td || !td.rows || (td.rows as unknown[]).length === 0) return '';
  const rows = td.rows as Array<Record<string, unknown>>;
  const hasYoY = Boolean(td.has_yoy);
  const valueColumn = String(td.value_column || '');
  const currentYear = String(td.current_year || '');
  const previousYear = td.previous_year ? String(td.previous_year) : null;
  const body = rows.map((row, i) => {
    const yoyFmt = tbHbFormatRate(row['同比增长率'] as number | null | undefined, false);
    const momFmt = tbHbFormatRate(row['环比增长率'] as number | null | undefined, i === 0);
    const monthLabel = row.month ? (TBHB_MONTHS[(row.month as number) - 1] || row.period) : row.period;
    const isEven = i % 2 === 0;
    return `<tr style="border-bottom:1px solid rgba(255,255,255,0.04);${isEven ? 'background:rgba(255,255,255,0.02);' : ''}">
      <td style="padding:8px 12px;color:#cbd5e1;font-weight:500;white-space:nowrap;">${cmdEsc(String(monthLabel))}</td>
      ${hasYoY ? `<td style="padding:8px 12px;text-align:right;color:#94a3b8;font-family:monospace;">${tbHbFormatValue(row['上年值'] as number | null)}</td>` : ''}
      <td style="padding:8px 12px;text-align:right;color:#f8fafc;font-weight:600;font-family:monospace;">${tbHbFormatValue(row['本年值'] as number | null)}</td>
      ${hasYoY ? `<td style="padding:8px 12px;text-align:right;color:${yoyFmt.color};font-family:monospace;">${yoyFmt.html}</td>` : ''}
      <td style="padding:8px 12px;text-align:right;color:${momFmt.color};font-family:monospace;">${momFmt.html}</td>
    </tr>`;
  }).join('\n');
  const sub = hasYoY ? `${previousYear}年 vs ${currentYear}年 月度对比` : `${currentYear}年 月度环比`;
  return `<div style="margin:0 12px 12px;padding:16px;border-radius:8px;background:rgba(10,14,30,0.95);border:1px solid rgba(125,211,252,0.12);">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">
      <div><h3 style="font-size:14px;font-weight:600;color:#e2e8f0;">📋 ${cmdEsc(valueColumn)} · 同环比分析</h3><p style="font-size:11px;color:#64748b;margin-top:4px;">${cmdEsc(sub)}</p></div>
      <span style="font-size:11px;color:#64748b;">共 ${rows.length} 个月</span>
    </div>
    <div style="overflow-y:auto;max-height:380px;">
      <table style="width:100%;border-collapse:collapse;font-size:11px;">
        <thead><tr style="background:#1a1a2e;position:sticky;top:0;">
          <th style="padding:8px 12px;text-align:left;color:#94a3b8;font-weight:600;">月份</th>
          ${hasYoY ? `<th style="padding:8px 12px;text-align:right;color:#94a3b8;font-weight:600;">${cmdEsc(previousYear || '')}年</th>` : ''}
          <th style="padding:8px 12px;text-align:right;color:#f8fafc;font-weight:600;">${cmdEsc(currentYear)}年</th>
          ${hasYoY ? `<th style="padding:8px 12px;text-align:right;color:#94a3b8;font-weight:600;">同比增长率</th>` : ''}
          <th style="padding:8px 12px;text-align:right;color:#94a3b8;font-weight:600;">环比增长率</th>
        </tr></thead>
        <tbody>${body}</tbody>
      </table>
    </div>
    <div style="display:flex;gap:16px;font-size:11px;color:#64748b;margin-top:8px;">
      <span style="color:#FB7185;">🔺 增长</span><span style="color:#22c55e;">🔻 下降</span><span style="color:#9ca3af;">➖ 持平 / 无数据</span>
    </div>
  </div>`;
}

// ========== 指挥中心 (command) 布局 HTML 生成 ==========
function buildCommandLayout(
  kpis: KPI[],
  tableData: Record<string, unknown>[],
  title: string,
  echarts: EChartItem[],
): string {
  const columns = tableData?.[0] ? Object.keys(tableData[0]) : [];
  const catCol = columns[0] || '分类';

  const map = computeCommandMap(echarts);
  const tbHbCharts = (echarts || []).filter((c) => c.chart_type === 'table' && c.table_data).map(tbHbTableHtml);
  const tbHbSection = tbHbCharts.length ? tbHbCharts.join('\n') : '';

  // TOP5 排行（与屏幕一致：取数值列降序 top5）
  const valCol = columns.find((k) => typeof (tableData?.[0]?.[k]) === 'number') || columns[1] || '';
  const rankingData = (() => {
    if (!tableData || !tableData.length) return [];
    return tableData
      .map((row, i) => ({ name: String(row[catCol] ?? `项${i + 1}`), value: Number(row[valCol]) || 0 }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 5);
  })();

  const CHINA_GEO_URL = 'https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json';

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${title} - 数据智能指挥中心</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js"></script>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family:'PingFang SC','Microsoft YaHei',system-ui,sans-serif; height:100vh; overflow:hidden; background:radial-gradient(ellipse at center,#0a1628 0%,#050d1a 50%,#020810 100%); color:#cbd5e1; display:flex; flex-direction:column; }
  .header { display:flex; align-items:center; justify-content:space-between; padding:12px 24px; border-bottom:1px solid rgba(125,211,252,0.12); flex-shrink:0; }
  .header-bar { width:6px; height:24px; background:linear-gradient(180deg,#7DD3FC,#38BDF8); border-radius:3px; }
  .main-row { flex:1; display:flex; gap:12px; padding:12px; min-height:0; }
  .side-panel { width:20%; min-width:220px; display:flex; flex-direction:column; border-radius:8px; border:1px solid rgba(125,211,252,0.08); background:rgba(125,211,252,0.03); padding:12px 16px; overflow:hidden; }
  .side-panel .sec-label { font-size:11px; font-weight:600; color:#7DD3FC; margin-bottom:8px; letter-spacing:0.05em; }
  .side-panel .kpi-row { display:flex; align-items:center; justify-content:space-between; padding:6px 0; border-bottom:1px solid rgba(125,211,252,0.06); font-size:11px; }
  .center-panel { flex:1; min-width:0; border-radius:8px; border:1px solid rgba(125,211,252,0.08); background:rgba(125,211,252,0.02); overflow:hidden; }
  .map-label { position:absolute; top:10px; left:14px; z-index:10; font-size:11px; color:#7DD3FC; font-weight:600; letter-spacing:0.05em; }
  table { width:100%; border-collapse:collapse; font-size:10px; }
  thead tr { background:rgba(56,189,248,0.1); }
  th { padding:6px 8px; text-align:left; color:#94a3b8; font-size:10px; font-weight:500; border-bottom:1px solid rgba(125,211,252,0.08); }
  td { padding:5px 8px; border-bottom:1px solid rgba(125,211,252,0.04); }
  .ranking-item { display:flex; align-items:center; justify-content:space-between; padding:8px 10px; border-bottom:1px solid rgba(125,211,252,0.06); }
  .ranking-badge { font-size:12px; font-weight:700; width:28px; text-align:center; }
  .ranking-name { font-size:12px; max-width:100px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .ranking-val { font-size:13px; font-weight:700; color:#7DD3FC; }
  .footer { flex-shrink:0; padding:8px 24px; font-size:11px; color:#64748b; border-top:1px solid rgba(125,211,252,0.08); background:rgba(125,211,252,0.04); }
  @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.4; } }
</style>
</head>
<body>
<div class="header">
  <div style="display:flex;align-items:center;gap:12px;">
    <div class="header-bar"></div>
    <h1 style="font-size:20px;font-weight:700;color:#fff;letter-spacing:0.1em;text-shadow:0 0 30px rgba(125,211,252,0.6);">数据智能指挥中心</h1>
  </div>
  <span style="display:flex;align-items:center;gap:8px;font-size:12px;color:#7DD3FC;">
    <span style="width:8px;height:8px;border-radius:50%;background:#7DD3FC;animation:pulse 2s infinite;"></span>系统运行中
    <span style="margin-left:12px;color:#64748b;font-family:monospace;font-size:11px;">${new Date().toLocaleString('zh-CN')}</span>
  </span>
</div>

<div class="main-row">
  <!-- 左侧面板：数据总览 + 数据预览 -->
  <div class="side-panel">
    <div class="sec-label">📊 数据总览</div>
    <div style="flex:1;overflow:hidden;">
    ${kpis.slice(0, 4).map((kpi) => {
      const color = kpi.color || '#7DD3FC';
      const numVal = typeof kpi.value === 'number' ? kpi.value : parseFloat(String(kpi.value));
      return `<div class="kpi-row">
          <span style="color:#94a3b8;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:100px;">${kpi.title}</span>
          <span style="font-weight:700;font-family:monospace;color:${color};">${isNaN(numVal) ? kpi.value : numVal.toLocaleString()}</span>
        </div>`;
      }).join('\n      ')}
    </div>
    <div class="sec-label" style="margin-top:12px;color:#7DD3FC;">📋 数据预览</div>
    <div style="overflow:auto;height:160px;">
      ${tableData && tableData.length > 0 ? `
      <table>
        <thead>
          <tr><th style="width:28px;">#</th>${columns.slice(0, 3).map(k => `<th>${k}</th>`).join('')}</tr>
        </thead>
        <tbody>
          ${tableData.slice(0, 8).map((row, i) => `
          <tr style="${i % 2 === 0 ? 'background:rgba(15,23,42,0.3)' : ''}">
            <td style="color:#64748b;text-align:center;">${i + 1}</td>
            ${columns.slice(0, 3).map(k => `<td style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:80px;">${String(row[k] ?? '-')}</td>`).join('')}
          </tr>`).join('\n          ')}
        </tbody>
      </table>` : '<div style="text-align:center;color:#64748b;padding:20px;font-size:11px;">暂无数据</div>'}
    </div>
  </div>

  <!-- 中间：中国地图 -->
  <div class="center-panel" style="position:relative;">
    <div class="map-label">🇨🇳 国内数据态势</div>
    <div id="china-map" style="width:100%;height:100%;"></div>
  </div>

  <!-- 右侧面板：关键指标 + 排行 -->
  <div class="side-panel">
    <div class="sec-label">⚡ 关键指标</div>
    <div style="flex:1;overflow:auto;">
    ${kpis.slice(4, 8).map((kpi) => {
      const color = kpi.color || '#7DD3FC';
      const numVal = typeof kpi.value === 'number' ? kpi.value : parseFloat(String(kpi.value));
      return `<div class="kpi-row">
          <span style="color:#94a3b8;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:100px;">${kpi.title}</span>
          <span style="font-weight:700;font-family:monospace;color:${color};">${isNaN(numVal) ? kpi.value : numVal.toLocaleString()}</span>
        </div>`;
      }).join('\n      ')}
    </div>
    <div class="sec-label" style="margin-top:12px;color:#7DD3FC;">🏆 ${catCol} 排行 TOP5</div>
    <div style="height:160px;overflow:auto;">
      ${rankingData.length > 0 ? rankingData.map((item, i) => {
        const badge = i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : i + 1;
        const bg = i < 3 ? 'rgba(125,211,252,0.06)' : 'transparent';
        return `<div class="ranking-item" style="background:${bg};">
          <div style="display:flex;align-items:center;gap:8px;overflow:hidden;">
            <span class="ranking-badge" style="color:${i < 3 ? '#e2e8f0' : '#64748b'};">${badge}</span>
            <span class="ranking-name">${item.name}</span>
          </div>
          <span class="ranking-val">${item.value.toLocaleString()}</span>
        </div>`;
      }).join('\n      ') : '<div style="text-align:center;color:#64748b;padding:20px;font-size:11px;">暂无排行数据</div>'}
    </div>
  </div>
</div>

${tbHbSection}

<div class="footer">
  总记录数：<span style="color:#7DD3FC;font-weight:600;">${tableData?.length || 0}</span>
  &nbsp;|&nbsp; 数据字段：<span style="color:#7DD3FC;font-weight:600;">${columns.length}</span>
  &nbsp;|&nbsp; ${new Date().toLocaleString('zh-CN')}
</div>

<script>
(function() {
  var chartDom = document.getElementById('china-map');
  var chart = echarts.init(chartDom, undefined, { renderer: 'canvas' });
  var FALLBACK_CITIES = [
    { name: '北京', value: [116.46, 39.92, 18] },
    { name: '上海', value: [121.48, 31.22, 16.5] },
    { name: '广州', value: [113.23, 23.16, 13.5] },
    { name: '深圳', value: [114.07, 22.62, 12.75] },
    { name: '成都', value: [104.06, 30.67, 10.5] },
    { name: '武汉', value: [114.31, 30.52, 9.75] },
    { name: '杭州', value: [120.19, 30.26, 11.25] },
    { name: '南京', value: [118.78, 32.04, 9] },
  ];
  var FALLBACK_LINES = [
    { coords: [[116.46, 39.92], [121.48, 31.22]] },
    { coords: [[116.46, 39.92], [113.23, 23.16]] },
    { coords: [[121.48, 31.22], [114.07, 22.62]] },
    { coords: [[104.06, 30.67], [116.46, 39.92]] },
  ];
  var mapData = ${JSON.stringify(map)};
  fetch('${CHINA_GEO_URL}').then(function(r) { return r.json(); }).then(function(geo) {
    echarts.registerMap('china', geo);
    var hasReal = mapData.hasRealData;
    var effectScatterData = hasReal ? mapData.effectScatterData : FALLBACK_CITIES;
    var linesData = hasReal ? mapData.linesData : FALLBACK_LINES;
    var regions = mapData.regions || [];
    var maxVal = mapData.maxVal || 1;
    chart.setOption({
      tooltip: { trigger: 'item', backgroundColor: 'rgba(10,22,40,0.95)', borderColor: 'rgba(125,211,252,0.3)', textStyle: { color: '#e2e8f0', fontSize: 11 } },
      geo: {
        map: 'china', roam: false, zoom: 1.15, center: [104.5, 36], aspectScale: 0.85,
        regions: regions,
        itemStyle: { areaColor: '#0B1025', borderColor: '#312e81', borderWidth: 1, shadowBlur: 6, shadowColor: 'rgba(59,130,246,0.25)' },
        emphasis: { itemStyle: { areaColor: '#4f46e5', shadowBlur: 25, shadowColor: 'rgba(59,130,246,0.7)' }, label: { show: true, color: '#f0e6ff', fontSize: 14, fontWeight: 'bold' } },
      },
      series: [
        {
          type: 'effectScatter', coordinateSystem: 'geo', data: effectScatterData,
          symbol: 'circle',
          symbolSize: function(val) { return hasReal ? Math.max(6, Math.min(18, (val[2] / maxVal) * 16)) : val[2]; },
          showEffectOn: 'render',
          rippleEffect: { brushType: 'stroke', scale: 4, period: 4, color: '#7DD3FC' },
          itemStyle: { color: '#e0e7ff', shadowBlur: 10, shadowColor: 'rgba(125,211,252,0.8)' },
          label: { show: true, position: 'top', distance: 10, color: '#67e8f9', fontSize: 11, fontWeight: 'bold', formatter: '{c}', textShadowBlur: 6, textShadowColor: 'rgba(6,182,212,0.6)' },
          emphasis: { scale: 2, itemStyle: { color: '#f0e6ff', shadowBlur: 20 }, label: { fontSize: 15, color: '#f0e6ff' } },
          zlevel: 1,
        },
        {
          type: 'lines', coordinateSystem: 'geo', data: linesData,
          lineStyle: { color: '#7DD3FC', width: 1, opacity: 0.4, curveness: 0.2 },
          effect: { show: true, period: 5, trailLength: 0.3, trailWidth: 1.5, symbolSize: 4, color: '#7DD3FC' },
          zlevel: 1,
        },
      ],
    });
  }).catch(function() {});
  window.addEventListener('resize', function() { chart.resize(); });
})();
</script>
</body>
</html>`;
}

// ========== 数据分析报告模板 ==========
interface ReportSection {
  title: string;
  subtitle?: string;
  chartIndex?: number; // 对应 echarts 数组索引（仅图表类型 section 有效）
  /** V2：按 analysis_type 匹配 saved_packages 中的图表 */
  analysis_type?: string;
  analysis: string;    // AI 分析文字
  tableData?: Record<string, unknown>[]
  // next_steps 专用字段
  chartsToCreate?: { chart_title: string; chart_type: string; x_axis: string; y_axis: string; guide: string }[];
  actionItems?: { priority: number; action: string }[];
}

/** 把原始值解析为纯数字（兼容 "298,957,289,699,910" / 298957289699910 / "2.99万亿"） */
function parseNumVal(raw: string | number): number {
  if (typeof raw === 'number') return raw;
  const cleaned = raw.replace(/[,，\s]/g, '').replace(/万亿/g, '000000000000').replace(/亿/g, '00000000').replace(/万/g, '0000');
  const n = parseFloat(cleaned);
  return isNaN(n) ? 0 : n;
}

/** KPI 去重：同名 title 只保留首次出现的那条 */
function _deduplicateByTitle(kpis: KPI[]): KPI[] {
  const seen = new Map<string, KPI>();
  for (const k of kpis) {
    const key = k.title || '';
    if (!seen.has(key)) seen.set(key, k);
  }
  return Array.from(seen.values());
}

/** KPI 优先级评分：颜色质量 + 关键词加权，分数越高越值得放在精选区 */
function _scoreKPI(k: KPI): number {
  let score = 0;
  // 颜色质量分
  const colorScores: Record<string, number> = { excellent: 4, good: 3, warning: 2, danger: 1 };
  score += colorScores[k.color || ''] ?? 0;
  // 关键词加分
  const t = (k.title || '').toLowerCase();
  if (/增长率|增速|涨幅|集中度|复购率|利润率|毛利率|转化率/.test(t)) score += 2;
  if (/总|合计|总计|累计/.test(t)) score += 1;
  if (/平均|均值/.test(t)) score += 1;
  return score;
}

/** 去重 + 按分排序 → { top6 精选, rest 折叠 } */
function _splitKPIs(kpis: KPI[]): { top: KPI[]; rest: KPI[] } {
  const deduped = _deduplicateByTitle(kpis);
  const sorted = [...deduped].sort((a, b) => _scoreKPI(b) - _scoreKPI(a));
  return { top: sorted.slice(0, 6), rest: sorted.slice(6) };
}

/** 中文缩写：万(10⁴) / 亿(10⁸) / 万亿(10¹²)，保留 2 位小数并去掉尾部 .00 */
function formatAbbreviatedCN(raw: string | number): string {
  const n = parseNumVal(raw);
  const absN = Math.abs(n);
  if (absN >= 1e12) return (n / 1e12).toFixed(2).replace(/\.?0+$/, '') + '万亿';
  if (absN >= 1e8)  return (n / 1e8).toFixed(2).replace(/\.?0+$/, '') + '亿';
  if (absN >= 1e4)  return (n / 1e4).toFixed(2).replace(/\.?0+$/, '') + '万';
  // 小于 1 万时保留千分位
  return n.toLocaleString('zh-CN');
}

/** 把数字转为千分位完整格式，如 298,957,289,699,910 */
function formatFullNumber(raw: string | number): string {
  const n = parseNumVal(raw);
  if (!Number.isFinite(n)) return String(raw);
  // 整数不显示小数，浮点保留 2 位
  if (Number.isInteger(n)) return n.toLocaleString('zh-CN');
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/**
 * 轻量 Markdown → HTML 转换（专为 AI 报告输出设计）
 * 支持：**bold**、- list、\n、\n\n
 * 必须先 escapeHtml 再做标记替换，避免 XSS
 */
function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function markdownToHtml(md: string): string {
  if (!md) return '';
  // 1) 先 HTML 转义（防 XSS）
  let html = escapeHtml(md);

  // 2) 把 - / 1. 开头的列表项转成 <li>，整段包成 <ul> / <ol>
  //    列表项内的换行合并为 <br/>，避免列表断行
  const lines = html.split('\n');
  const out: string[] = [];
  let inList: 'ul' | 'ol' | null = null;
  for (const line of lines) {
    const t = line.trim();
    // 匹配 "1. " / "2. " 等有序列表
    const olMatch = /^(\d+)\.\s+(.*)$/.exec(t);
    // 匹配 "- " / "* " 无序列表
    const ulMatch = /^[-*]\s+(.*)$/.exec(t);

    if (olMatch || ulMatch) {
      const wantKind: 'ul' | 'ol' = olMatch ? 'ol' : 'ul';
      const content = (olMatch ? olMatch[2] : ulMatch![1]);
      // 切换列表类型时关闭旧列表
      if (inList && inList !== wantKind) {
        out.push(`</${inList}>`);
        inList = null;
      }
      if (!inList) {
        const listStyle = wantKind === 'ol'
          ? '<ol style="margin:6px 0;padding-left:24px;list-style:decimal">'
          : '<ul style="margin:6px 0;padding-left:24px">';
        out.push(listStyle);
        inList = wantKind;
      }
      // 列表项内部允许后续非空行延续（AI 经常写多行说明）
      out.push(`<li style="margin-bottom:4px">${content}`);
    } else if (inList && t !== '') {
      // 列表项内的延续行
      out.push(`<br/>${t}`);
    } else {
      if (inList) {
        out.push(`</${inList}>`);
        inList = null;
      }
      if (t === '') {
        out.push('<br/>');
      } else {
        out.push(t);
      }
    }
  }
  if (inList) out.push(`</${inList}>`);
  // 收尾：给仍在 <li> 但未关闭的列表项补 </li>
  let html2 = out.join('');
  html2 = html2.replace(/(<li[^>]*>(?:(?!<\/li>).)*)(?=<(?:li|\/ol|\/ul))/g, '$1</li>');
  // 修正常见的 "</li><br/>" 多余的 <br/>
  html2 = html2.replace(/<\/li>\s*<br\/>/g, '</li>');
  html = html2;

  // 3) **bold** → <strong>（在 escape 之后做，** 不会受影响）
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong style="color:#5C3D2E">$1</strong>');

  // 4) 连续多个 <br/> 合并为段落分隔
  html = html.replace(/(<br\s*\/?>\s*){3,}/g, '</p><p style="margin:6px 0">');
  html = `<p style="margin:6px 0">${html}</p>`;

  return html;
}

// ========== 导出入口 ==========
export function generateEChartsDashboardHTML(
  template: Template,
  kpis: KPI[],
  echarts: EChartItem[],
  title: string,
  hideChartTitle: boolean,
  navTabs?: string[],
  ringCharts?: RingChartConfig[],
  tableData?: Record<string, unknown>[],
  // 报告专用参数
  reportSections?: ReportSection[],
  reportSummary?: string,
  reportConclusion?: string,
  rowCount: number = 0,
  // 数据看板（medical）导出以 cards 为唯一数据源，与屏幕上 MedicalDashboard 完全一致
  cards?: CardItem[],
  meta?: CardMeta,
  degradation?: ReportDegradation,
): string {
  switch (template) {
    case 'immersive':
      return buildImmersiveLayout(kpis, echarts, title, hideChartTitle);
    case 'command':
      return buildCommandLayout(kpis, tableData || [], title, echarts);
    case 'medical':
      return buildMedicalLayout(
        cards || [], meta, title, hideChartTitle,
      );
    default:
      return buildImmersiveLayout(kpis, echarts, title, hideChartTitle);
  }
}

/**
 * 为某个筛选字段提取可选值（用于导出 HTML 的筛选下拉）。
 * 优先级：schema.filter_options（后端从 DataFrame 提取）→ widget.dim_values → xAxis / pie 名称。
 */
function extractFilterOptions(field: string, schema: Record<string, unknown>): string[] {
  const opts = new Set<string>();
  const isTimeLike = (s: string): boolean => {
    const t = s.trim();
    return /^\d{4}[-/]\d{1,2}([-/]\d{1,2})?(\s\d{1,2}:\d{2}(:\d{2})?)?$/.test(t)
      || /^\d{1,2}[-/]\d{1,2}[-/]\d{2,4}$/.test(t);
  };

  // 1) 后端注入的 filter_options
  const fo = (schema.filter_options as Record<string, unknown>) || {};
  if (Array.isArray(fo[field])) {
    (fo[field] as unknown[]).forEach(v => {
      const sv = String(v);
      if (!isTimeLike(sv)) opts.add(sv);
    });
    if (opts.size > 0) return Array.from(opts).slice(0, 30);
  }

  const widgets = (schema.widgets || []) as Record<string, unknown>[];
  // 2) widget.chart_config.dim_values
  widgets.forEach(w => {
    const cfg = (w.chart_config || {}) as Record<string, unknown>;
    const dv = (cfg.dim_values as Record<string, unknown>) || {};
    if (Array.isArray(dv[field])) {
      (dv[field] as unknown[]).forEach(v => {
        const sv = String(v);
        if (!isTimeLike(sv)) opts.add(sv);
      });
    }
  });
  if (opts.size > 0) return Array.from(opts).slice(0, 30);

  // 3) xAxis / pie 名称兜底
  widgets.forEach(w => {
    const cfg = (w.chart_config || {}) as Record<string, unknown>;
    const opt = (cfg.option || {}) as Record<string, unknown>;
    const xa = opt.xAxis;
    const xAxisObj = Array.isArray(xa) ? (xa[0] as Record<string, unknown>) : (xa as Record<string, unknown>);
    const xData = xAxisObj && xAxisObj.data;
    if (Array.isArray(xData)) {
      (xData as unknown[]).forEach(v => {
        const sv = String(v);
        if (!isTimeLike(sv)) opts.add(sv);
      });
    }
    const series = opt.series;
    if (Array.isArray(series)) {
      (series as Record<string, unknown>[]).forEach(s => {
        const data = s.data;
        if (Array.isArray(data)) {
          (data as unknown[]).forEach(item => {
            if (item && typeof item === 'object' && !Array.isArray(item) && 'name' in (item as object)) {
              const sv = String((item as Record<string, unknown>).name as unknown);
              if (!isTimeLike(sv)) opts.add(sv);
            }
          });
        }
      });
    }
  });
  return Array.from(opts).slice(0, 30);
}

// ========== AI 智能驾驶舱布局 HTML 生成 ==========

/**
 * 基于 DashboardSchema 生成 AI 智能驾驶舱的可导出 HTML 文件。
 * 从 schema.widgets 提取图表/KPI/表格/洞察，按 sections 分区域布局渲染。
 */
export function generateAIDashboardHTML(
  schema: Record<string, unknown>,
  title: string,
  hideTitle: boolean,
): string {
  const widgets = (schema.widgets || []) as Record<string, unknown>[];
  const sections = (schema.sections || []) as Record<string, unknown>[];
  const columns: number = (schema.layout as Record<string, unknown>)?.columns as number || 12;

  // ----- 分类 widgets -----
  const chartWidgets = widgets.filter((w: Record<string, unknown>) =>
    (w.widget_type === 'chart' || w.widget_type === 'map') && (w.chart_config as Record<string, unknown>)?.option
  );
  const kpiWidgets = widgets.filter((w: Record<string, unknown>) =>
    w.widget_type === 'kpi'
  );
  const tableWidgets = widgets.filter((w: Record<string, unknown>) =>
    w.widget_type === 'table'
  );

  // ----- 构建 ECharts chart items -----
  const chartItems: Array<{ id: string; title: string; option: unknown }> = [];
  const widgetChartMap: Record<string, string> = {};

  chartWidgets.forEach((w: Record<string, unknown>, i: number) => {
    const chartId = `ai_chart_${i}`;
    const cfg = w.chart_config as Record<string, unknown> || {};
    chartItems.push({
      id: chartId,
      title: String(w.title || ''),
      option: cfg.option,
    });
    const td = cfg.table_data as { rows?: unknown[][]; columns?: string[] } | undefined;
    const chartDiv = makeChartDiv(
      chartId, String(w.title || ''), 380, hideTitle,
      String(w.chart_type || ''), td,
    );
    // 图表文字说明（空值兜底 + HTML 转义）
    const chartDesc = String((w as Record<string, unknown>).description || '').trim();
    const chartDescHtml = chartDesc
      ? `<p style="margin:10px 4px 2px;font-size:12px;line-height:1.7;color:#94a3b8;">${chartDesc.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')}</p>`
      : '';
    widgetChartMap[String(w.widget_id)] = chartDiv + chartDescHtml;
  });

  // ----- KPI 卡片 HTML（与屏幕上 KPIWidget 一致：title 主 + value + kpi_label 副 + change 趋势） -----
  const kpiHtmlMap: Record<string, string> = {};
  kpiWidgets.forEach((w: Record<string, unknown>) => {
    const cfg = w.chart_config as Record<string, unknown> || {};
    const meta = w.metadata as Record<string, unknown> || {};
    // ★ 与 KPIWidget 一致：value 优先 metadata.formatted/value；副标签 = metadata.kpi_label；主标题 = widget.title
    const value = (meta.formatted ?? meta.value ?? '') as string;
    const title = String(w.title || '');
    const sub = (meta.kpi_label || '') as string;
    const change = (typeof (meta.change ?? 0) === 'number' ? (meta.change as number) : 0);
    // sparkline 数据：有数据就有趋势图
    const hasSpark = cfg.data && Array.isArray(cfg.data) && (cfg.data as unknown[]).length > 0;
    // 既没有数值也没有 sparkline 数据 → 不生成 HTML (避免空白占位)
    if (!value && !hasSpark) return;
    const color = (cfg.color || '#7DD3FC') as string;
    const icon = (cfg.icon || '📊') as string;
    const trendHtml = change !== 0
      ? `<p style="font-size:10px;font-weight:600;margin-top:2px;color:${change > 0 ? '#34D399' : '#FB7185'}">${change > 0 ? '↑' : '↓'} ${Math.abs(change).toFixed(1)}%</p>`
      : '';
    const subHtml = sub ? `<p style="font-size:10px;color:#94a3b8;margin-top:2px;">${cmdEsc(sub)}</p>` : '';
    kpiHtmlMap[String(w.widget_id)] = `
<div style="padding:14px 18px;border-radius:12px;background:rgba(56,189,248,0.08);border:1px solid rgba(56,189,248,0.15);display:flex;flex-direction:column;justify-content:center;min-height:90px;">
  <div style="font-size:20px;margin-bottom:2px;">${icon}</div>
  <p style="font-size:10px;color:#94a3b8;margin-bottom:4px;">${cmdEsc(title)}</p>
  <p style="font-size:18px;font-weight:700;color:${color};text-shadow:0 0 8px ${color}40;">${cmdEsc(value)}</p>
  ${subHtml}${trendHtml}
</div>`;
  });

  // ----- 表格 HTML -----
  const tableHtmlMap: Record<string, string> = {};
  tableWidgets.forEach((w: Record<string, unknown>) => {
    const cfg = w.chart_config as Record<string, unknown> || {};
    const td = cfg.table_data as { rows?: unknown[][]; columns?: string[] } | undefined;
    if (td) {
      const tblDiv = makeChartDiv(
        'tbl_' + w.widget_id, String(w.title || ''), 380, hideTitle, 'table', td,
      );
      // 表格文字说明（空值兜底 + HTML 转义）
      const tblDesc = String((w as Record<string, unknown>).description || '').trim();
      const tblDescHtml = tblDesc
        ? `<p style="margin:10px 4px 2px;font-size:12px;line-height:1.7;color:#94a3b8;">${tblDesc.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')}</p>`
        : '';
      tableHtmlMap[String(w.widget_id)] = tblDiv + tblDescHtml;
    }
  });

  // ★ 检测是否含中国地图（需 registerMap 才能正确渲染）
  const optionHasChinaMap = (opt: unknown): boolean => {
    const o = opt as Record<string, unknown>;
    if (!o) return false;
    if (o.geo && (o.geo as Record<string, unknown>).map === 'china') return true;
    const series = (o.series as Array<Record<string, unknown>>) || [];
    return series.some((s) => s.map === 'china' || s.coordinateSystem === 'geo' || s.type === 'map');
  };
  const hasChinaMap = chartItems.some((c) => optionHasChinaMap(c.option));

  // ----- 按 sections 构建区域 HTML -----
  let sectionsHTML = '';

  sections.forEach((sec: Record<string, unknown>) => {
    const role = String(sec.role || '');
    if (role === 'header') return;

    const widgetIds = (sec.widget_ids || []) as string[];
    if (widgetIds.length === 0) return;

    const widgetIdSet = new Set(widgetIds);

    // 分类整理本 section 的 widgets
    interface SecWidget { type: string; html: string; w: number; h: number; }
    const secItems: SecWidget[] = [];

    widgets.forEach((w: Record<string, unknown>) => {
      const wid = String(w.widget_id);
      if (!widgetIdSet.has(wid)) return;

      const pos = w.position as Record<string, number> || { w: 6, h: 1 };
      const wt = String(w.widget_type);

      if (wt === 'chart' && widgetChartMap[wid]) {
        secItems.push({ type: 'chart', html: widgetChartMap[wid], w: pos.w || 6, h: pos.h || 1 });
      } else if (wt === 'kpi' && kpiHtmlMap[wid]) {
        secItems.push({ type: 'kpi', html: kpiHtmlMap[wid], w: pos.w || 3, h: pos.h || 1 });
      } else if (wt === 'table' && tableHtmlMap[wid]) {
        secItems.push({ type: 'table', html: tableHtmlMap[wid], w: pos.w || 6, h: pos.h || 1 });
      } else if (wt === 'insight' || wt === 'summary') {
        const cfg = w.chart_config as Record<string, unknown> || {};
        const text = String(cfg.analysis || cfg.content || w.title || '');
        if (text) {
          const escaped = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
          secItems.push({
            type: 'insight',
            html: `<div style="padding:16px;background:rgba(125,211,252,0.04);border-radius:12px;border:1px solid rgba(125,211,252,0.08);"><p style="font-size:12px;color:#94a3b8;line-height:1.8;margin:0;">${escaped}</p></div>`,
            w: pos.w || 6, h: pos.h || 1,
          });
        }
      }
    });

    if (secItems.length === 0) return;

    const secTitle = sec.title
      ? `<div style="padding:6px 24px;font-size:12px;font-weight:600;color:#7DD3FC;display:flex;align-items:center;gap:8px;"><span style="width:5px;height:14px;background:linear-gradient(180deg,#38BDF8,#7DD3FC);border-radius:2px;"></span>${sec.title}</div>`
      : '';

    // Hero section: 全宽单列
    const isHero = role === 'hero';
    const gridStyle = isHero
      ? 'display:flex;flex-direction:column;gap:16px;padding:12px 24px;'
      : `display:grid;grid-template-columns:repeat(${columns},minmax(80px,1fr));gap:16px;padding:12px 24px;`;

    const itemsHTML = secItems.map((item) => {
      const span = isHero ? '' : `grid-column:span ${Math.min(item.w, columns)};grid-row:span ${item.h};`;
      return `<div style="${span}">${item.html}</div>`;
    }).join('\n');

    sectionsHTML += `
<div style="margin-bottom:8px;">
  ${secTitle}
  <div style="${gridStyle}">
    ${itemsHTML}
  </div>
</div>`;
  });

  // 如果 sections 为空，回退：把所有 widgets 铺成一个 grid
  if (!sectionsHTML) {
    const allItems: Array<{ html: string; w: number; h: number }> = [];
    widgets.forEach((w: Record<string, unknown>) => {
      const wid = String(w.widget_id);
      const pos = w.position as Record<string, number> || { w: 6, h: 1 };
      let html = '';
      if (widgetChartMap[wid]) html = widgetChartMap[wid];
      else if (kpiHtmlMap[wid]) html = kpiHtmlMap[wid];
      else if (tableHtmlMap[wid]) html = tableHtmlMap[wid];
      if (html) allItems.push({ html, w: pos.w || 6, h: pos.h || 1 });
    });
    if (allItems.length > 0) {
      const itemsHTML = allItems.map((item) =>
        `<div style="grid-column:span ${Math.min(item.w, columns)};">${item.html}</div>`
      ).join('\n');
      sectionsHTML = `
<div style="margin-bottom:8px;">
  <div style="display:grid;grid-template-columns:repeat(${Math.min(columns, 12)},minmax(100px,1fr));gap:20px;padding:16px 24px;">
    ${itemsHTML}
  </div>
</div>`;
    }
  }

  // ----- 全局筛选栏 HTML（仅当 schema 含 global_filters 时渲染） -----
  const globalFilters = (((schema.interactions as Record<string, unknown> | undefined)?.global_filters)
    || []) as Array<Record<string, unknown>>;
  let filterBarHTML = '';
  if (globalFilters.length > 0) {
    const selectsHtml = globalFilters.map(f => {
      const field = String(f.field || '');
      const name = String(f.name || field);
      const scope = String(f.scope || 'global');
      const scopeBadge = scope === 'global' ? '🌐' : scope === 'section' ? '📦' : '📌';
      const widgetType = String(f.widget_type || 'dropdown');
      const esc = (s: string) =>
        s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
      if (widgetType === 'date_range') {
        return `<div style="display:flex;align-items:center;gap:8px;">
          <label style="font-size:12px;color:#94a3b8;white-space:nowrap;">${scopeBadge} ${esc(name)}</label>
          <input type="date" data-field="${esc(field)}" onchange="onGlobalFilterChange('${esc(field)}', this.value)"
            style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:8px;padding:6px 10px;font-size:12px;color:#cbd5e1;">
        </div>`;
      }
      const options = extractFilterOptions(field, schema);
      const optsHtml = ['<option value="">全部</option>']
        .concat(options.map(o => `<option value="${esc(o)}">${esc(o)}</option>`))
        .join('');
      return `<div style="display:flex;align-items:center;gap:8px;">
        <label style="font-size:12px;color:#94a3b8;white-space:nowrap;">${scopeBadge} ${esc(name)}</label>
        <select data-field="${esc(field)}" onchange="onGlobalFilterChange('${esc(field)}', this.value)"
          style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:8px;padding:6px 10px;font-size:12px;color:#cbd5e1;cursor:pointer;">
          ${optsHtml}
        </select>
      </div>`;
    }).join('');
    filterBarHTML = `<div style="display:flex;flex-wrap:wrap;align-items:center;gap:16px;padding:12px 24px;border-bottom:1px solid rgba(56,189,248,0.1);background:rgba(56,189,248,0.04);">
      <span style="font-size:12px;color:#7DD3FC;font-weight:600;">🔍 数据筛选</span>
      ${selectsHtml}
    </div>`;
  }

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${title} - 智能驾驶舱</title>
<style>${COMMON_CSS}</style>
</head>
<body style="min-height:100vh;background:linear-gradient(180deg,#050816 0%,#0a0e27 50%,#0f0d1f 100%);max-width:1600px;margin:0 auto;">
${makeHeader(title, true)}
${filterBarHTML}
${sectionsHTML}
${makeEChartsScript(chartItems, hideTitle)}
${hasChinaMap ? `<script>
(function() {
  var GEO_URL = 'https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json';
  var mapOpts = ${JSON.stringify(
    chartItems.filter((c) => optionHasChinaMap(c.option)).map((c) => ({ id: c.id, option: c.option })),
    (_key, v) => (typeof v === 'number' && !Number.isFinite(v)) ? null : v,
  )};
  fetch(GEO_URL).then(function(r) { return r.json(); }).then(function(geo) {
    echarts.registerMap('china', geo);
    mapOpts.forEach(function(o) {
      var el = document.getElementById(o.id);
      if (!el) return;
      var chart = echarts.getInstanceByDom(el);
      if (chart) { chart.setOption(o.option); chart.resize(); }
    });
  }).catch(function() {});
})();
</script>` : ''}
</body>
</html>`;
}


export function downloadEChartsHTML(html: string, filename: string) {
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
