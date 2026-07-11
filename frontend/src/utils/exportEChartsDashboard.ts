/* 生成自包含 ECharts 交互式 HTML 大屏文件，保留所有 ECharts 交互和深色主题 */
import type { EChartItem } from '../types/api';
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

type Template = 'grid' | 'classic' | 'immersive' | 'medical' | 'command' | 'report';

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

function makeHeader(title: string) {
  return `
<div style="display:flex;align-items:center;justify-content:space-between;padding:16px 32px;border-bottom:2px solid rgba(56,189,248,0.15);">
  <div style="display:flex;align-items:center;gap:16px;">
    <div style="width:8px;height:32px;background:linear-gradient(180deg,#38BDF8,#7DD3FC);border-radius:4px;"></div>
    <h1 style="font-size:28px;font-weight:700;letter-spacing:0.05em;text-shadow:0 0 25px rgba(56,189,248,0.5);">${title}</h1>
  </div>
  <div style="display:flex;align-items:center;gap:24px;font-size:13px;color:#94a3b8;">
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

function makeChartDiv(id: string, title: string, height: number, hideTitle: boolean, chartType?: string, tableData?: TableDataRaw) {
  const titleHtml = hideTitle ? '' : `
<div style="padding:10px 16px;border-bottom:1px solid rgba(56,189,248,0.1);display:flex;align-items:center;gap:10px;">
  <span style="width:8px;height:8px;border-radius:50%;background:#38BDF8;"></span>
  <span style="font-size:13px;font-weight:600;color:#cbd5e1;">${title}</span>
</div>`;

  if (chartType === 'table' && tableData) {
    const convertedData = convertTableData(tableData);
    const tableHtml = makeTableHTML(convertedData);
    return `
<div data-chart-wrapper style="border-radius:16px;overflow:hidden;background:rgba(15,23,42,0.7);border:1px solid rgba(56,189,248,0.15);">
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
<div data-chart-wrapper style="border-radius:16px;overflow:hidden;background:rgba(15,23,42,0.7);border:1px solid rgba(56,189,248,0.15);">
  ${titleHtml}
  <div style="width:100%;padding:12px;overflow:auto;max-height:${hideTitle ? height : height - 40}px;">
    <table style="width:100%;border-collapse:collapse;">${theadHtml}${tbodyHtml}</table>
  </div>
</div>`;
  }

  return `
<div data-chart-wrapper style="border-radius:16px;overflow:hidden;background:rgba(15,23,42,0.7);border:1px solid rgba(56,189,248,0.15);">
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

function buildGridLayout(kpis: KPI[], charts: EChartItem[], title: string, hideTitle: boolean): string {
  const kpiHtml = kpis.length > 0 ? `
<div style="display:flex;gap:16px;padding:20px 32px;border-bottom:1px solid rgba(56,189,248,0.08);flex-wrap:wrap;">
  ${kpis.slice(0, 6).map(makeKPICard).join('\n  ')}
</div>` : '';

  const chartHtml = charts.length > 0 ? `
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:20px;padding:24px;">
  ${charts.slice(0, 6).map((c, i) => makeChartDiv('chart_' + i, c.title, 420, hideTitle, c.chart_type, c.table_data)).join('\n  ')}
</div>` : `
<div style="padding:60px;text-align:center;color:#64748b;font-size:18px;">暂无图表</div>`;

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${title} - 数据大屏</title>
<style>${COMMON_CSS}</style>
</head>
<body style="min-height:100vh;background:linear-gradient(135deg,#050816 0%,#0a0e27 50%,#0f0d1f 100%);">
${makeHeader(title)}
${kpiHtml}
${chartHtml}
${makeEChartsScript(charts, hideTitle)}
</body>
</html>`;
}

function buildClassicLayout(kpis: KPI[], charts: EChartItem[], title: string, hideTitle: boolean): string {
  const mainChart = charts[0];
  const leftCharts = charts.slice(1, 4);
  const rightCharts = charts.slice(4, 7);

  const kpiHtml = kpis.length > 0 ? `
<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:4px;">
  ${kpis.slice(0, 4).map(k => {
    const color = k.color || '#38BDF8';
    return `<div style="padding:12px;border-radius:10px;text-align:center;background:rgba(56,189,248,0.08);border:1px solid rgba(56,189,248,0.12);">
    <p style="font-size:10px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:4px;">${k.title}</p>
    <p style="font-size:18px;font-weight:700;color:${color};">${k.value}</p>
  </div>`;
  }).join('\n  ')}
</div>` : '';

  const leftHtml = `<div style="width:22%;display:flex;flex-direction:column;gap:12px;">
  ${kpiHtml}
  ${leftCharts.map((c, i) => makeChartDiv(`chart_${i + (mainChart ? 1 : 0)}`, c.title, 260, hideTitle, c.chart_type, c.table_data)).join('\n  ')}
</div>`;

  const centerHtml = mainChart && mainChart.chart_type === 'table' && mainChart.table_data
    ? '<div data-chart-wrapper style="flex:1;border-radius:16px;overflow:hidden;background:rgba(15,23,42,0.4);border:1px solid rgba(56,189,248,0.2);">' +
      (hideTitle ? '' : '<div style="padding:12px 20px;border-bottom:1px solid rgba(56,189,248,0.1);display:flex;align-items:center;gap:12px;">' +
        '<span style="width:10px;height:10px;border-radius:50%;background:#7DD3FC;"></span>' +
        '<span style="font-size:15px;font-weight:600;">' + (mainChart.title || '主视图') + '</span>' +
        '</div>') +
      '<div style="width:100%;padding:12px;overflow:auto;max-height:520px;">' +
      makeTableHTML(convertTableData(mainChart.table_data)) +
      '</div></div>'
    : `<div data-chart-wrapper style="flex:1;border-radius:16px;overflow:hidden;background:rgba(15,23,42,0.4);border:1px solid rgba(56,189,248,0.2);">
  ${hideTitle ? '' : `<div style="padding:12px 20px;border-bottom:1px solid rgba(56,189,248,0.1);display:flex;align-items:center;gap:12px;">
    <span style="width:10px;height:10px;border-radius:50%;background:#7DD3FC;"></span>
    <span style="font-size:15px;font-weight:600;">${mainChart?.title || '主视图'}</span>
  </div>`}
  <div id="chart_0" style="width:100%;height:560px;"></div>
</div>`;

  const rightHtml = `<div style="width:22%;display:flex;flex-direction:column;gap:12px;">
  ${rightCharts.map((c, i) => makeChartDiv(`chart_${i + (mainChart ? 1 : 0) + leftCharts.length}`, c.title, 260, hideTitle, c.chart_type, c.table_data)).join('\n  ')}
</div>`;

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${title} - 数据大屏</title>
<style>${COMMON_CSS}</style>
</head>
<body style="min-height:100vh;background:linear-gradient(180deg,#0a0a1a 0%,#0f0f2a 100%);">
<div style="position:relative;padding:16px 32px;text-align:center;border-bottom:1px solid #1e1e3a;">
  <div style="position:absolute;top:0;left:50%;transform:translateX(-50%);width:400px;height:2px;background:linear-gradient(90deg,transparent,#38BDF8,transparent);"></div>
  <h1 style="font-size:30px;font-weight:700;letter-spacing:0.15em;text-shadow:0 0 40px rgba(56,189,248,0.6);">${title}</h1>
</div>
<div style="display:flex;gap:16px;padding:20px;">
  ${leftHtml}
  ${centerHtml}
  ${rightHtml}
</div>
${makeEChartsScript(charts, hideTitle)}
</body>
</html>`;
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
  kpis: KPI[],
  charts: EChartItem[],
  title: string,
  hideTitle: boolean,
  navTabs: string[],
  ringCharts: RingChartConfig[],
  tableData: Record<string, unknown>[],
): string {
  const tabs = navTabs.length >= 4 ? navTabs.slice(0, 4) : ['数据总览', '趋势洞察', '分类分析', '明细查询'];

  // ---- 规范化 ringCharts（与 MedicalDashboard displayRingCharts 保持一致） ----
  const displayRingCharts: RingChartConfig[] = (ringCharts && ringCharts.length >= 3)
    ? ringCharts.slice(0, 3)
    : [
        { title: '数据占比', data: [{ name: '类型A', value: 65 }, { name: '其他', value: 35 }] },
        { title: '完成率', data: [{ name: '已完成', value: 78 }, { name: '进行中', value: 22 }] },
        { title: '分布情况', data: [{ name: '主要', value: 55 }, { name: '次要', value: 45 }] },
      ];

  // ---- 辅助：判断图表类型 ----
  function getChartTypes(c: EChartItem): string[] {
    const series = (c.option as any)?.series;
    if (!series || !Array.isArray(series)) return [];
    return series.map((s: any) => s.type || 'unknown');
  }
  const isTrend = (c: EChartItem) => getChartTypes(c).some((t: string) => ['line', 'area'].includes(t));
  const isCategory = (c: EChartItem) => getChartTypes(c).some((t: string) => ['bar', 'pie', 'radar'].includes(t));

  // ---- 提前计算 Tab 2 分类图表列表（供 HTML + 独立 ECharts items 使用） ----
  const categoryCharts = charts.filter(isCategory);
  const catDisplay = categoryCharts.length > 0 ? categoryCharts : charts.filter((_, i) => i < 4);

  // ---- 构建环形图 ECharts items ----（Tab 0 用）
  const ringChartItems: Array<{ id: string; title: string; option: any }> = displayRingCharts.map((rc, i) => ({
    id: `ring_${i}`,
    title: rc.title || '占比分析',
    option: buildRingChartEChartsOption(rc.data, rc.title || ''),
  }));

  // ---- 构建环形图 ECharts items ----（Tab 2 用，独立 ID 避免与 Tab 0 冲突）
  // 三个环形图统一 chartHeight=230
  const catRingChartItems: Array<{ id: string; title: string; option: any }> = displayRingCharts.map((rc, i) => ({
    id: `cat_ring_${i}`,
    title: rc.title || '占比分析',
    option: buildRingChartEChartsOption(rc.data, rc.title || '', 230),
  }));

  // ---- 构建 Tab 2 分类图表 ECharts items ----（独立 ID 避免与 Tab 1 趋势 chart_ ID 冲突）
  const catChartItems: Array<{ id: string; title: string; option: any }> = catDisplay.map((c) => ({
    id: `cat_chart_${charts.indexOf(c)}`,
    title: c.title,
    option: c.option,
  }));

  // ---- 构建雷达图 ECharts items (web 版多维对比用) ----
  const radarDataSets = [[85, 70, 90, 65, 80, 75], [60, 88, 72, 95, 55, 82], [78, 82, 65, 70, 92, 68]];
  const radarColors = [REPORT_THEME.primaryHover, REPORT_THEME.primaryHover, REPORT_THEME.warning];
  const radarNames = ['指标一', '指标二', '指标三'];
  const radarChartItems: Array<{ id: string; title: string; option: any }> = radarNames.map((name, i) => ({
    id: `radar_${i}`,
    title: name,
    option: buildRadarOption(radarDataSets[i % 3], radarColors[i % 3]),
  }));

  // 合并所有图表用于脚本渲染（含 Tab 2 独立 ID 的分类图表和环形图）
  const allChartItems = [...charts, ...ringChartItems, ...catRingChartItems, ...catChartItems, ...radarChartItems];

  // ---- KPI 卡片 HTML (数字翻牌样式) ----
  const kpiHtml = kpis.length > 0 ? `
<div style="padding:16px 28px;display:flex;justify-content:center;">
  <div style="display:flex;justify-content:center;gap:12px;flex-wrap:wrap;max-width:1100px;">
    ${kpis.slice(0, 6).map((kpi) => {
      const numVal = typeof kpi.value === 'number' ? kpi.value : parseFloat(String(kpi.value));
      const isNum = !isNaN(numVal);
      const digits = isNum ? String(Math.floor(numVal)).split('') : [];
      const color = kpi.color || '#7DD3FC';
      return `
    <div style="flex:0 0 auto;display:flex;flex-direction:column;align-items:center;padding:12px 24px;min-width:150px;background:linear-gradient(180deg,rgba(125,211,252,0.08) 0%,rgba(125,211,252,0.02) 100%);border:1px solid rgba(125,211,252,0.15);border-radius:4px;">
      <span style="font-size:10px;color:#94a3b8;margin-bottom:8px;">${kpi.title}</span>
      <div style="display:flex;gap:2px;align-items:center;">
        ${isNum ? digits.map((d: string) => `<div style="width:24px;height:32px;display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:bold;font-family:monospace;background:linear-gradient(180deg,rgba(125,211,252,0.2) 0%,rgba(125,211,252,0.05) 100%);border:1px solid rgba(125,211,252,0.3);color:${color};text-shadow:0 0 10px ${color}50;">${d}</div>`).join('') : `<span style="font-size:18px;font-weight:bold;color:${color};">${kpi.value}</span>`}
      </div>
      ${kpi.unit ? `<span style="font-size:9px;color:#64748b;margin-top:4px;">${kpi.unit}</span>` : ''}
    </div>`;
    }).join('\n    ')}
  </div>
</div>` : '';

  // ======== Tab 0 - 数据总览（匹配组件 60%/38% 布局） ========
  const hasRing0 = displayRingCharts.length > 0;
  const hasRingMore = displayRingCharts.length > 1;
  const overviewRingBottom = displayRingCharts.slice(1); // ring 1, 2, ...

  const overviewLeftHtml = `
      <div class="med-flex-col" style="flex:1;min-width:0;max-width:60%;">
        <div style="display:flex;gap:16px;height:${hasRing0 ? '45%' : '100%'};">
          <div class="med-card flex-1">
            <div class="med-label" style="margin:0 0 8px 12px;">📈 趋势总览</div>
            ${charts.length > 0 ? makeChartDiv('chart_0', charts[0].title, hasRing0 ? 220 : 380, hideTitle) : '<div class="med-empty">暂无数据</div>'}
          </div>
          ${hasRing0 ? `
          <div class="med-card" style="width:256px;">
            <div class="med-label" style="margin:0 0 8px 12px;">🥧 ${displayRingCharts[0].title || '占比分析'}</div>
            ${makeChartDiv('ring_0', '', 220, true)}
          </div>` : ''}
        </div>
        <div class="med-card" style="flex:1;margin-top:16px;">
          <div class="med-label" style="margin:0 0 8px 12px;">📊 多维对比</div>
          <div style="display:flex;gap:12px;height:calc(100% - 24px);">
            ${radarNames.map((name, i) => `
            <div style="flex:1;">${makeChartDiv(`radar_${i}`, name, 180, hideTitle)}</div>`).join('\n            ')}
          </div>
        </div>
      </div>`;

  // 右侧：表格预览 + 底部环形图
  const overviewRightHtml = `
      <div class="med-flex-col" style="width:38%;min-width:300px;">
        <div class="med-card flex-1" style="overflow:hidden;">
          <div class="med-label med-label-row" style="margin:0 0 12px 12px;">
            <span>📋 数据预览</span>
            <span style="font-size:10px;color:#64748b;">共 ${tableData?.length || 0} 条</span>
          </div>
          <div style="overflow:auto;height:calc(100% - 32px);">${makeTableHTML(tableData, 10)}</div>
        </div>
        ${hasRingMore ? `
        <div style="display:flex;gap:12px;height:180px;margin-top:12px;">
          ${overviewRingBottom.map((rc, i) => `
          <div class="med-card flex-1">
            ${makeChartDiv(`ring_${i + 1}`, rc.title, 160, true)}
          </div>`).join('\n          ')}
        </div>` : ''}
      </div>`;

  const overviewHtml = `
  <div class="med-panel active" id="panel-0">
    <div style="display:flex;gap:16px;padding:0 28px 20px;">
      ${overviewLeftHtml}
      ${overviewRightHtml}
    </div>
  </div>`;

  // ======== Tab 1 - 趋势洞察 ========
  const trendCharts = charts.filter(isTrend);
  const trendDisplay = trendCharts.length > 0 ? trendCharts : charts.filter((_, i) => i < 3);
  const trendCols = trendDisplay.length === 1 ? 1 : 2;
  const trendHtml = trendDisplay.length > 0 ? `
  <div class="med-panel" id="panel-1">
    <div style="padding:0 28px 4px;font-size:12px;color:#94a3b8;">
      📈 ${trendDisplay.length} 张趋势图表 — 自动筛选折线图/面积图
    </div>
    <div style="display:grid;grid-template-columns:repeat(${trendCols},1fr);gap:16px;padding:8px 28px 20px;">
      ${trendDisplay.map((c) => {
        const idx = charts.indexOf(c);
        return `<div class="med-card">${makeChartDiv(`chart_${idx}`, c.title, trendCols === 1 ? 420 : 300, hideTitle)}</div>`;
      }).join('\n      ')}
    </div>
  </div>` : `
  <div class="med-panel" id="panel-1">
    <div style="padding:60px;text-align:center;color:#64748b;">暂无趋势图表 — 请选择包含折线图/面积图的数据集</div>
  </div>`;

  // ======== Tab 2 - 分类分析 ========
  // TOP8 排行数据
  const columns = tableData?.[0] ? Object.keys(tableData[0]) : [];
  const topNData = (() => {
    if (!tableData || !columns[0]) return [];
    const counts: Record<string, number> = {};
    tableData.forEach((row) => {
      const key = String(row[columns[0]] ?? '未知');
      counts[key] = (counts[key] || 0) + 1;
    });
    return Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 8)
      .map(([name, value]) => ({ name, value }));
  })();

  const top8Badge = (i: number) => i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : String(i + 1);

  const catHtml = catDisplay.length > 0 ? `
  <div class="med-panel" id="panel-2">
    <div style="display:flex;gap:16px;padding:0 28px 20px;">
      <div style="flex:1;min-width:0;">
        <div style="font-size:12px;color:#94a3b8;margin-bottom:8px;">📊 ${catDisplay.length + Math.min(displayRingCharts.length, 2)} 张图表 — 分类柱状图/饼图/雷达图</div>
        <div style="display:grid;grid-template-columns:repeat(2,1fr);grid-template-rows:repeat(3,1fr);gap:12px;">
          ${catDisplay.map((c) => {
            const idx = charts.indexOf(c);
            return `<div class="med-card">${makeChartDiv(`cat_chart_${idx}`, c.title, 220, hideTitle)}</div>`;
          }).join('\n          ')}
          ${displayRingCharts.slice(0, 2).map((rc, i) => `
          <div class="med-card" style="overflow:visible;">
            <div style="padding:10px 16px;border-bottom:1px solid rgba(56,189,248,0.1);display:flex;align-items:center;gap:10px;">
              <span style="width:8px;height:8px;border-radius:50%;background:#38BDF8;"></span>
              <span style="font-size:13px;font-weight:600;color:#cbd5e1;">${rc.title || '占比分析'}</span>
            </div>
            ${makeRingChartDiv(`cat_ring_${i}`, '', 220, true)}
          </div>`).join('\n          ')}
        </div>
      </div>
      <div class="med-flex-col" style="width:28%;min-width:220px;">
        <div class="med-card flex-1" style="overflow:hidden;">
          <div class="med-label">🏆 ${columns[0] || '分类'} 排行 TOP8</div>
          <div style="overflow:auto;height:calc(100% - 28px);">
            ${topNData.length > 0 ? topNData.map((item, i) => {
              const bg = i < 3 ? 'rgba(125,211,252,0.08)' : 'transparent';
              return `<div style="display:flex;align-items:center;justify-content:space-between;padding:6px 10px;border-bottom:1px solid rgba(125,211,252,0.04);background:${bg};">
                <div style="display:flex;align-items:center;gap:8px;">
                  <span style="font-size:12px;font-weight:700;width:24px;text-align:center;color:${i < 3 ? '#e2e8f0' : '#64748b'};">${top8Badge(i)}</span>
                  <span class="text-truncate" style="max-width:100px;font-size:12px;color:#cbd5e1;">${String(item.name).slice(0, 12)}</span>
                </div>
                <span style="font-size:12px;font-weight:600;color:#7DD3FC;">${item.value}</span>
              </div>`;
            }).join('\n            ') : '<div class="med-empty">暂无数据</div>'}
          </div>
        </div>
        ${displayRingCharts.length >= 3 ? `
        <div class="med-card" style="overflow:visible;">
          <div style="padding:10px 16px;border-bottom:1px solid rgba(56,189,248,0.1);display:flex;align-items:center;gap:10px;">
            <span style="width:8px;height:8px;border-radius:50%;background:#38BDF8;"></span>
            <span style="font-size:13px;font-weight:600;color:#cbd5e1;">${displayRingCharts[2]?.title || '占比分析'}</span>
          </div>
          ${makeRingChartDiv(`cat_ring_2`, '', 220, true)}
        </div>` : ''}
      </div>
    </div>
  </div>` : `
  <div class="med-panel" id="panel-2">
    <div style="padding:60px;text-align:center;color:#64748b;">暂无分类图表 — 请选择包含柱状图/饼图/雷达图的数据集</div>
  </div>`;

  // ======== Tab 3 - 明细查询 ========
  const detailHtml = `
  <div class="med-panel" id="panel-3">
    <div style="padding:0 28px 20px;">
      <div class="med-label med-label-row" style="margin:0 0 8px 0;">
        <span>📄 数据明细表</span>
        <span id="filtered-count" style="font-size:10px;color:#64748b;">共 ${tableData?.length || 0} 条</span>
      </div>
      <div style="display:flex;gap:8px;margin-bottom:8px;flex-wrap:wrap;">
        <input id="detail-search" type="text" placeholder="🔍 搜索全部列..." oninput="filterDetailTable()"
          style="width:192px;padding:6px 12px;border-radius:8px;border:1px solid rgba(56,189,248,0.2);background:rgba(15,23,42,0.9);color:#e2e8f0;font-size:12px;font-family:inherit;" />
        <select id="detail-filter-col" onchange="onFilterColChange()"
          style="padding:6px 8px;border-radius:8px;border:1px solid rgba(56,189,248,0.2);background:rgba(15,23,42,0.9);color:#94a3b8;font-size:12px;font-family:inherit;">
          <option value="">📌 按列过滤</option>
          ${Object.keys(tableData?.[0] || {}).map((col) => `<option value="${col}">${col}</option>`).join('\n          ')}
        </select>
        <input id="detail-filter-val" type="text" placeholder="过滤值..." oninput="filterDetailTable()"
          style="display:none;padding:6px 12px;border-radius:8px;border:1px solid rgba(56,189,248,0.2);background:rgba(15,23,42,0.9);color:#e2e8f0;font-size:12px;font-family:inherit;width:144px;" />
      </div>
      <div class="med-card" style="max-height:520px;overflow:auto;" id="detail-table-wrapper">
        ${makeTableHTML(tableData)}
      </div>
    </div>
  </div>`;

  // tab 切换 & 搜索脚本
  const tabSwitchScript = `
<script>
  var tableData = ${JSON.stringify(tableData || [])};
  var headers = ${JSON.stringify(tableData?.[0] ? Object.keys(tableData[0]) : [])};
  var filterCol = null;

  function switchTab(idx) {
    document.querySelectorAll('.med-tab').forEach(function(b, i) { b.classList.toggle('active', i === idx); });
    document.querySelectorAll('.med-panel').forEach(function(p, i) { p.classList.toggle('active', i === idx); });
    var targetPanel = document.getElementById('panel-' + idx);
    // ★ 先初始化该面板内尚未渲染的延迟图表（切过一次就不再延迟）
    if (typeof initDeferredChartsInPanel === 'function' && targetPanel) {
      initDeferredChartsInPanel('panel-' + idx);
    }
    setTimeout(function() {
      if (targetPanel) {
        targetPanel.querySelectorAll('[id]').forEach(function(el) {
          if (typeof echarts !== 'undefined') {
            var chart = echarts.getInstanceByDom(el);
            if (chart) chart.resize();
          }
        });
      }
    }, 150);
  }

  function onFilterColChange() {
    var sel = document.getElementById('detail-filter-col');
    var valInput = document.getElementById('detail-filter-val');
    if (sel && valInput) {
      filterCol = sel.value || null;
      if (filterCol) {
        valInput.style.display = 'block';
        valInput.placeholder = '过滤 ' + filterCol + '...';
      } else {
        valInput.style.display = 'none';
        valInput.value = '';
      }
      filterDetailTable();
    }
  }

  function formatVal(v) {
    if (v === null || v === undefined) return '-';
    if (typeof v === 'number') {
      if (!isFinite(v)) return '-';
      if (Number.isInteger(v)) return v.toLocaleString();
      return v.toFixed(2);
    }
    return String(v);
  }

  function filterDetailTable() {
    var q = (document.getElementById('detail-search')?.value || '').toLowerCase();
    var filterVal = (document.getElementById('detail-filter-val')?.value || '').toLowerCase();
    var rows = tableData;
    if (q) {
      rows = rows.filter(function(row) {
        return headers.some(function(h) { return formatVal(row[h]).toLowerCase().indexOf(q) !== -1; });
      });
    }
    if (filterCol && filterVal) {
      rows = rows.filter(function(row) {
        return formatVal(row[filterCol]).toLowerCase().indexOf(filterVal) !== -1;
      });
    }
    var html = '<table style="width:100%;border-collapse:collapse;font-size:11px;">';
    html += '<thead><tr>';
    html += '<th style="padding:8px 8px;text-align:left;font-weight:600;color:#94a3b8;border-bottom:1px solid rgba(125,211,252,0.1);font-size:11px;width:30px;">#</th>';
    headers.forEach(function(h) {
      html += '<th style="padding:8px 12px;text-align:left;font-weight:600;color:#94a3b8;border-bottom:1px solid rgba(125,211,252,0.1);font-size:11px;cursor:pointer;" onclick="sortDetailTable(' + headers.indexOf(h) + ')()">' + h + ' <span id="sort-arrow-' + headers.indexOf(h) + '" style="font-size:9px;"></span></th>';
    });
    html += '</tr></thead>';
    html += '<tbody>';
    rows.forEach(function(row, i) {
      html += '<tr style="' + (i % 2 === 0 ? '' : 'background:rgba(15,23,42,0.3)') + ';border-top:1px solid rgba(255,255,255,0.03);">';
      html += '<td style="padding:6px 8px;border-bottom:1px solid rgba(125,211,252,0.04);color:#64748b;font-size:10px;">' + (i + 1) + '</td>';
      headers.forEach(function(h) { html += '<td style="padding:6px 12px;border-bottom:1px solid rgba(125,211,252,0.04);color:#cbd5e1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:180px;">' + formatVal(row[h]) + '</td>'; });
      html += '</tr>';
    });
    html += '</tbody></table>';
    var wrapper = document.getElementById('detail-table-wrapper');
    if (wrapper) wrapper.innerHTML = html;
    var cnt = document.getElementById('filtered-count');
    if (cnt) cnt.textContent = rows.length + ' / ' + tableData.length + ' 条';
  }

  function sortDetailTable(colIdx) {
    var ascending = true;
    return function() {
      ascending = !ascending;
      tableData.sort(function(a, b) {
        var va = a[headers[colIdx]], vb = b[headers[colIdx]];
        if (typeof va === 'number' && typeof vb === 'number') return ascending ? va - vb : vb - va;
        return ascending ? String(va).localeCompare(String(vb)) : String(vb).localeCompare(String(va));
      });
      filterDetailTable();
    };
  }
</script>`;

  // ---- 组装完整 HTML ----
  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${title} - 数据看板</title>
<style>
${COMMON_CSS}
.med-tab-bar {
  display: flex;
  justify-content: center;
  gap: 2px;
  padding: 8px 28px 0;
  border-bottom: 1px solid rgba(125,211,252,0.1);
  background: linear-gradient(90deg, transparent 0%, rgba(125,211,252,0.05) 20%, rgba(125,211,252,0.05) 80%, transparent 100%);
}
.med-tab {
  padding: 4px 16px;
  font-size: 12px;
  font-weight: 500;
  color: #64748b;
  background: transparent;
  border: none;
  cursor: pointer;
  font-family: inherit;
  transition: all 0.25s;
}
.med-tab:hover { color: #cbd5e1; }
.med-tab.active {
  color: #7DD3FC;
  background: rgba(125,211,252,0.1);
  border-top: 1px solid rgba(125,211,252,0.5);
  clip-path: polygon(10% 0%, 90% 0%, 100% 100%, 0% 100%);
}
.med-panel { display: none; padding-top: 16px; }
.med-panel.active { display: block; }
.med-card {
  border-radius: 12px;
  overflow: hidden;
  background: rgba(15,23,42,0.7);
  border: 1px solid rgba(56,189,248,0.15);
}
.med-card-inner { padding: 12px; }
.med-label {
  font-size: 12px;
  color: #7DD3FC;
  margin-bottom: 8px;
  padding: 4px 0;
}
.med-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.med-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 80px;
  color: #64748b;
  font-size: 12px;
}
.med-flex-col {
  display: flex;
  flex-direction: column;
  gap: 0;
}
.flex-1 { flex: 1; }
.text-truncate {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
/* 消除 med-card 内 makeChartDiv 的双重边框 */
.med-card > [data-chart-wrapper] {
  border: none !important;
  border-radius: 0 !important;
  background: transparent !important;
}
th { cursor: pointer; transition: color 0.2s; }
th:hover { color: #7DD3FC; }
</style>
</head>
<body style="min-height:100vh;background:linear-gradient(180deg,#0a0f1a 0%,#0d1525 50%,#0a1628 100%);">
<div style="position:relative;display:flex;align-items:center;justify-content:center;padding:12px 24px;background:linear-gradient(90deg,transparent 0%,rgba(125,211,252,0.05) 20%,rgba(125,211,252,0.05) 80%,transparent 100%);border-bottom:1px solid rgba(125,211,252,0.15);">
  <div style="position:absolute;left:16px;top:50%;transform:translateY(-50%);display:flex;align-items:center;gap:8px;">
    <span style="width:8px;height:8px;border-radius:50%;background:#7DD3FC;animation:pulse 2s infinite;"></span>
    <span style="font-size:12px;color:#64748b;">${new Date().toLocaleString('zh-CN')}</span>
  </div>
  <div style="display:flex;flex-direction:column;align-items:center;">
    <h1 style="font-size:20px;font-weight:700;color:#fff;letter-spacing:0.1em;margin-bottom:8px;text-shadow:0 0 20px rgba(125,211,252,0.5);">${title}</h1>
    <div class="med-tab-bar" style="border-bottom:none;background:transparent;padding:0;">
      ${tabs.map((t, i) => `<button class="med-tab${i === 0 ? ' active' : ''}" onclick="switchTab(${i})">${t}</button>`).join('\n      ')}
    </div>
  </div>
  <div style="position:absolute;right:16px;top:50%;transform:translateY(-50%);display:flex;align-items:center;gap:8px;">
    <span style="display:flex;align-items:center;gap:6px;font-size:12px;color:#7DD3FC;">
      <span style="width:6px;height:6px;border-radius:50%;background:#7DD3FC;animation:pulse 2s infinite;"></span>系统正常
    </span>
  </div>
</div>
${kpiHtml}
${overviewHtml}
${trendHtml}
${catHtml}
${detailHtml}
${makeEChartsScript(allChartItems, hideTitle)}
${tabSwitchScript}
<script>
  // 注入排序点击事件
  (function() {
    var ths = document.querySelectorAll('#detail-table-wrapper th');
    ths.forEach(function(th, i) {
      th.addEventListener('click', sortDetailTable(i));
    });
  })();
</script>
</body>
</html>`;
}

// ========== 指挥中心 (command) 布局 HTML 生成 ==========
function buildCommandLayout(
  kpis: KPI[],
  tableData: Record<string, unknown>[],
  title: string,
): string {
  const columns = tableData?.[0] ? Object.keys(tableData[0]) : [];
  const catCol = columns[0] || '分类';

  // TOP5 排行
  const rankingData = (() => {
    if (!tableData || !columns[0]) return [];
    const counts: Record<string, number> = {};
    tableData.forEach((row) => {
      const key = String(row[columns[0]] ?? '未知');
      counts[key] = (counts[key] || 0) + 1;
    });
    return Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 5)
      .map(([name, value]) => ({ name, value }));
  })();

  // 构建 KPI 行的 HTML
  const kpiCardsHtml = kpis.length > 0 ? kpis.map((kpi) => {
    const numVal = typeof kpi.value === 'number' ? kpi.value : parseFloat(String(kpi.value));
    const isNum = !isNaN(numVal);
    const digits = isNum ? String(Math.floor(numVal)).split('') : [];
    const color = kpi.color || '#7DD3FC';
    return `<div class="kpi-card">
    <div class="label">${kpi.title}</div>
    <div style="display:flex;gap:2px;align-items:center;">
      ${isNum ? digits.map((d: string) => `<div class="digit" style="color:${color};text-shadow:0 0 10px ${color}50;">${d}</div>`).join('') : `<span class="value" style="color:${color};">${kpi.value}</span>`}
    </div>
  </div>`;
  }).join('\n  ') : '';

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
  .kpis-wrap { display:flex; justify-content:center; gap:12px; flex-wrap:wrap; padding:12px 24px; border-bottom:1px solid rgba(125,211,252,0.08); flex-shrink:0; }
  .kpi-card { display:flex; flex-direction:column; align-items:center; padding:12px 24px; min-width:150px; background:linear-gradient(180deg,rgba(125,211,252,0.08) 0%,rgba(125,211,252,0.02) 100%); border:1px solid rgba(125,211,252,0.15); border-radius:4px; }
  .kpi-card .label { font-size:10px; color:#94a3b8; margin-bottom:6px; }
  .kpi-card .value { font-size:22px; font-weight:700; text-shadow:0 0 10px rgba(125,211,252,0.5); }
  .digit { width:24px; height:32px; display:flex; align-items:center; justify-content:center; font-size:18px; font-weight:700; font-family:monospace; background:linear-gradient(180deg,rgba(125,211,252,0.2),rgba(125,211,252,0.05)); border:1px solid rgba(125,211,252,0.3); border-radius:2px; }
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

${kpiCardsHtml ? `<div class="kpis-wrap">${kpiCardsHtml}</div>` : ''}

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

<div class="footer">
  总记录数：<span style="color:#7DD3FC;font-weight:600;">${tableData?.length || 0}</span>
  &nbsp;|&nbsp; 数据字段：<span style="color:#7DD3FC;font-weight:600;">${columns.length}</span>
  &nbsp;|&nbsp; ${new Date().toLocaleString('zh-CN')}
</div>

<script>
(function() {
  var chartDom = document.getElementById('china-map');
  var chart = echarts.init(chartDom, undefined, { renderer: 'svg' });
  var cities = [
    { name: '北京', value: [116.46, 39.92, 1.2] },
    { name: '上海', value: [121.48, 31.22, 1.1] },
    { name: '广州', value: [113.23, 23.16, 0.9] },
    { name: '深圳', value: [114.07, 22.62, 0.85] },
    { name: '成都', value: [104.06, 30.67, 0.7] },
    { name: '武汉', value: [114.31, 30.52, 0.65] },
    { name: '杭州', value: [120.19, 30.26, 0.75] },
    { name: '南京', value: [118.78, 32.04, 0.6] },
  ];
  fetch('${CHINA_GEO_URL}').then(function(r) { return r.json(); }).then(function(geo) {
    echarts.registerMap('china', geo);
    chart.setOption({
      tooltip: { trigger: 'item', backgroundColor: 'rgba(10,22,40,0.95)', borderColor: 'rgba(125,211,252,0.3)', textStyle: { color: '#e2e8f0', fontSize: 11 } },
      geo: {
        map: 'china',
        roam: false,
        itemStyle: { areaColor: 'rgba(125,211,252,0.08)', borderColor: 'rgba(125,211,252,0.25)', borderWidth: 0.5 },
        emphasis: { itemStyle: { areaColor: 'rgba(125,211,252,0.3)' }, label: { show: true, color: '#fff', fontSize: 10 } },
      },
      series: [
        {
          type: 'effectScatter',
          coordinateSystem: 'geo',
          data: cities.map(function(d) { return { name: d.name, value: [d.value[0], d.value[1], d.value[2] * 15] }; }),
          symbolSize: function(val) { return val[2]; },
          rippleEffect: { scale: 3, period: 5, color: '#7DD3FC' },
          itemStyle: { color: '#7DD3FC' },
          zlevel: 1,
        },
        {
          type: 'lines',
          coordinateSystem: 'geo',
          data: [
            { coords: [[116.46, 39.92], [121.48, 31.22]] },
            { coords: [[116.46, 39.92], [113.23, 23.16]] },
            { coords: [[121.48, 31.22], [114.07, 22.62]] },
            { coords: [[104.06, 30.67], [116.46, 39.92]] },
          ],
          lineStyle: { color: '#7DD3FC', width: 1, opacity: 0.5, curveness: 0.2 },
          effect: { show: true, period: 5, trailLength: 0.3, symbolSize: 4, color: '#7DD3FC' },
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

function buildReportHTML(
  kpis: KPI[],
  echarts: EChartItem[],
  title: string,
  sections: ReportSection[],
  aiSummary: string,
  aiConclusion: string,
  rowCount: number = 0,
): string {
  // 鈽?sections 涓虹┖/杩囧皯鏃讹紝鐢熸垚鍏嶈矗鎶ュ憡缁撴瀯
  const effectiveSections = sections && sections.length > 0 ? sections : _buildFallbackReportSections(kpis, echarts, aiSummary, aiConclusion);

  // ★ 为 ECharts 图表生成脚本
  const chartScript = makeEChartsScript(echarts.map((c, i) => ({ ...c, id: `report_chart_${i}` })), false);

  // ★ KPI 核心指标卡片
  const kpiHTML = kpis.length > 0 ? `
<div class="metrics-row">
  ${kpis.map((k) => `
  <div class="metric-card">
    <div class="metric-abbr ${k.color ? `metric-${k.color}` : ''}">${formatAbbreviatedCN(k.value)}${k.unit || ''}</div>
    <div class="metric-full">${formatFullNumber(k.value)}</div>
    <div class="metric-label">${k.title || k.label || "指标"}</div>
  </div>`).join('\n  ')}
</div>` : '';

  // ★ 去除标题中可能存在的任意数字编号前缀（"1." "1.1." "1、" 等）
  const cleanTitle = (raw: string) => (raw || '').replace(/^[\d\.\、\s]+/, '').trim();

  // ★ 将 sections 拆分为 overview + 正文 sections（确保 TOC 与正文编号一致）
  const overviewSection = effectiveSections.find(s => cleanTitle(s.title).includes('概览') && effectiveSections.indexOf(s) === 0);
  const bodySections = overviewSection
    ? effectiveSections.slice(1)  // overview 一定是第一个，skip 它
    : effectiveSections.filter(s => !cleanTitle(s.title).includes('概览'));  // 兜底：过滤所有概览
  // 确保 bodySections 中不会有被遗漏的概览
  const finalBodySections = bodySections.filter(s => !cleanTitle(s.title).includes('概览'));

  // ★ 构建 TOC：所有 sections 按顺序
  const allSectionTitles = overviewSection
    ? [cleanTitle(overviewSection.title), ...finalBodySections.map(s => cleanTitle(s.title))]
    : finalBodySections.map(s => cleanTitle(s.title));
  const tocItems = allSectionTitles.map(t => t);

  // ★ 构建正文章节（从第 2 节开始，第 1 节是概览单独渲染）
  let sectionCounter = 2;
  const sectionsHTML = finalBodySections.map((sec, _i) => {
    const sectionNum = sectionCounter++;
    // 关联的图表：仅当 echarts 数组中有对应索引的数据时才生成图表容器
    const hasChart = sec.chartIndex !== undefined && sec.chartIndex < echarts.length;
    const chartId = hasChart ? `report_chart_${sec.chartIndex}` : '';
    const chartDiv = chartId
      ? `<div class="chart-container"><div id="${chartId}" style="width:100%!important;min-width:600px;height:420px;display:block;"></div><div class="chart-caption">${sec.subtitle || cleanTitle(sec.title)}</div></div>`
      : '';

    // 分析文本：转换 Markdown 加粗 **xxx** → <strong>xxx</strong>，去除末尾空行
    let analysisHtml = (sec.analysis || '')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\n/g, '<br>')
      .replace(/(<br>\s*)+$/, '')  // ★ 去除末尾多余 <br>，避免空白
      // 突出显示增长率符号
      .replace(/🔺/g, '<span style="color:#28a745;font-weight:bold;">🔺</span>')
      .replace(/🔻/g, '<span style="color:#dc3545;font-weight:bold;">🔻</span>')
      .replace(/➖/g, '<span style="color:#6c757d;font-weight:bold;">➖</span>');

    // 表格数据
    const tableHTML = sec.tableData && sec.tableData.length > 0 ? `
<div style="overflow-x:auto;margin:15px 0;">
  <table>
    <thead><tr>${Object.keys(sec.tableData[0]).map(k => `<th>${k}</th>`).join('')}</tr></thead>
    <tbody>${sec.tableData.slice(0, 10).map(row => `<tr>${Object.keys(sec.tableData![0]).map(k => `<td>${formatReportVal(row[k])}</td>`).join('')}</tr>`).join('')}</tbody>
  </table>
</div>` : '';

    // 去除 subtitle 中的【】括号
    const cleanSubtitle = sec.subtitle ? sec.subtitle.replace(/^【/, '').replace(/】$/, '') : '';

    // ★ next_steps 特殊渲染：操作建议
    let extraHTML = '';
    if (sec.actionItems && sec.actionItems.length > 0) {
      extraHTML += '<div style="margin:10px 0 10px 20px;"><strong>✅ 操作清单</strong><br>';
      extraHTML += sec.actionItems.sort((a, b) => (a.priority || 99) - (b.priority || 99)).map(a =>
        `<p style="margin:4px 0 2px 10px;">${a.priority !== 99 ? a.priority + '. ' : ''}${a.action}</p>`
      ).join('');
      extraHTML += '</div>';
    }

    return `
<div class="section">
  <h1>${sectionNum}. ${cleanTitle(sec.title)}</h1>
  ${cleanSubtitle ? `<h3>${cleanSubtitle}</h3>` : ''}
  ${analysisHtml ? `<div class="analysis-text">${analysisHtml}</div>` : ''}
  ${extraHTML}
  ${tableHTML}
  ${chartDiv}
</div>`;
  }).join('\n');

  // ★ 报告目录：与本文章节编号完全一致
  // tocItems 已在上方构建完毕

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>数据分析报告 - ${title}</title>
<style>
  @page { size: A4; margin: 2cm }
  * { box-sizing: border-box; }
  body {
    font-family: 'PingFang SC', 'Microsoft YaHei', Arial, sans-serif;
    font-size: 14px; line-height: 1.8; color: #e2e8f0;
    margin: 0; padding: 20px 40px;
    background: #020617; max-width: 1100px; margin: 0 auto;
  }
  /* 打印回退浅色，省墨 */
  @media print {
    body { padding: 0; background: #ffffff !important; color: #333 !important; }
    .cover-page { background: #f8f9fa !important; border-color: #dee2e6 !important; box-shadow: none !important; }
    .cover-title { color: #0d1b2a !important; text-shadow: none !important; }
    .cover-subtitle, .cover-meta { color: #6c757d !important; }
    h1 { color: #0d1b2a !important; border-color: #0d1b2a !important; }
    h2 { color: #0d1b2a !important; border-color: #1b4965 !important; }
    h3 { color: #1b4965 !important; }
    .metric-card { background: #f8f9fa !important; border-color: #dee2e6 !important; box-shadow: none !important; }
    .metric-full, .metric-label { color: #6c757d !important; }
    .toc { background: #f8f9fa !important; border-color: #dee2e6 !important; }
    .toc li { color: #333 !important; }
    table th { background: #0d1b2a !important; color: #fff !important; }
    table td { border-color: #dee2e6 !important; color: #333 !important; }
    tr:nth-child(even) { background: #f8f9fa !important; }
    .highlight-box { background: #d4edda !important; border-color: #28a745 !important; color: #155724 !important; }
    .warning-box { background: #fff3cd !important; border-color: #fd7e14 !important; color: #856404 !important; }
    .footer { color: #adb5bd !important; border-color: #dee2e6 !important; }
    .insight-tag { filter: brightness(0.9) saturate(1.4); }
  }
  .cover-page {
    text-align: center; padding: 40px 20px;
    background: linear-gradient(135deg, #0F172A 0%, #1e293b 100%);
    border: 1px solid rgba(56,189,248,0.35); border-radius: 12px; margin-bottom: 20px;
    box-shadow: 0 0 24px rgba(56,189,248,0.12);
  }
  .cover-title {
    font-size: 32px; color: #f1f5f9; font-weight: bold; margin-bottom: 8px;
    text-shadow: 0 0 18px rgba(139,92,246,0.55);
  }
  .cover-subtitle { font-size: 16px; color: #94A3B8; margin-bottom: 18px; }
  .cover-meta { font-size: 13px; color: #94A3B8; }
  .cover-meta span { margin: 0 12px; }
  h1 {
    font-size: 26px; color: #f1f5f9;
    border-bottom: 3px solid rgba(56,189,248,0.5);
    padding-bottom: 6px; margin: 14px 0 8px;
  }
  h2 {
    font-size: 20px; color: #f1f5f9;
    border-bottom: 2px solid rgba(56,189,248,0.4);
    padding-bottom: 6px; margin: 12px 0 8px;
  }
  h3 { font-size: 16px; color: #cbd5e1; margin: 8px 0 6px; }
  .metrics-row { text-align: center; margin: 10px 0; display: flex; flex-wrap: wrap; justify-content: center; gap: 10px; }
  .metric-card {
    background: #0F172A; border: 1px solid rgba(56,189,248,0.3);
    border-radius: 10px; padding: 12px 20px; text-align: center;
    min-width: 140px; flex: 1 1 auto;
    display: flex; flex-direction: column; justify-content: center; align-items: center;
    box-shadow: 0 0 16px rgba(56,189,248,0.08);
  }
  .metric-abbr { font-size: 26px; font-weight: bold; margin: 2px 0; white-space: nowrap; }
  .metric-full { font-size: 10px; color: #94A3B8; margin: 2px 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%; }
  .metric-label { font-size: 11px; color: #94A3B8; margin-top: 2px; }
  .metric-excellent { color: #34D399; }
  .metric-good { color: #38BDF8; }
  .metric-warning { color: #FBBF24; }
  .metric-danger { color: #FB7185; }
  table { width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 12px; }
  th, td { border: 1px solid rgba(56,189,248,0.18); padding: 8px 6px; text-align: center; }
  th { background: rgba(56,189,248,0.15); color: #e2e8f0; font-weight: 600; }
  tr:nth-child(even) { background: rgba(255,255,255,0.04); }
  .chart-container { text-align: center; margin: 10px 0; width: 100%; display: block; overflow: hidden; }
  .chart-caption { font-size: 13px; color: #94A3B8; margin-top: 6px; text-align: center; font-style: italic; }
  .analysis-text { margin: 10px 0; text-indent: 2em; color: #e2e8f0; }
  .trend-up { color: #34D399; font-weight: 700; }
  .trend-down { color: #FB7185; font-weight: 700; }
  .trend-flat { color: #94A3B8; font-weight: 700; }
  .highlight-box {
    background: rgba(52,211,153,0.08); border: 1px solid rgba(52,211,153,0.5);
    color: #a7f3d0;
    padding: 15px 20px; margin: 20px 0; border-radius: 8px;
  }
  .warning-box {
    background: rgba(251,191,36,0.08); border: 1px solid rgba(251,191,36,0.5);
    color: #fde68a;
    padding: 15px 20px; margin: 20px 0; border-radius: 8px;
  }
  .section { margin-bottom: 6px; }
  .toc { background: #0F172A; padding: 16px 24px; border-radius: 8px; margin: 16px 0; line-height: 2.2; border: 1px solid rgba(56,189,248,0.2); }
  .toc ol { margin: 8px 0 0 0; padding: 0 0 0 24px; }
  .toc li { color: #e2e8f0; }
  .footer { text-align: center; color: #64748b; font-size: 11px; margin-top: 20px; padding-top: 12px; border-top: 1px solid rgba(56,189,248,0.15); }
  /* ★ 洞察标签样式 */
  .insight-tag {
    display: inline-block; font-size: 11px; padding: 1px 8px; border-radius: 8px;
    margin-right: 6px; font-weight: 600;
  }
  .insight-trend { background: rgba(52,211,153,0.15); color: #34D399; }
  .insight-structure { background: rgba(56,189,248,0.15); color: #38BDF8; }
  .insight-concentration { background: rgba(251,191,36,0.15); color: #FBBF24; }
  .insight-anomaly { background: rgba(251,113,133,0.15); color: #FB7185; }
  .insight-risk { background: rgba(167,139,250,0.15); color: #A78BFA; }
</style>
</head>
<body>
<div class="cover-page">
  <div class="cover-title">${title}</div>
  <div class="cover-subtitle">专业数据分析报告 | Data Analysis Report</div>
  <div class="cover-meta">
    <span>📅 ${new Date().toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })}</span>
    <span>📊 数据行数: ${rowCount > 0 ? rowCount.toLocaleString() : '—'}</span>
  </div>
</div>

<div class="toc">
  <strong>📋 报告目录</strong>
  <ol>${tocItems.map(t => `<li>${t}</li>`).join('')}</ol>
</div>

${kpiHTML ? `<div class="metrics-row-container">${kpiHTML}</div>` : ''}

<div class="section">
  <h1>1. ${overviewSection ? cleanTitle(overviewSection.title) : '数据概览'}</h1>
  ${aiSummary ? `<div class="analysis-text">${markdownToHtml(aiSummary)}</div>` : ''}
</div>

${sectionsHTML}

<div class="footer">
  <p>本报告由 DataMind AI 自动生成 | ${new Date().toLocaleString('zh-CN')}</p>
  <p>数据来源：用户上传数据集 | 基于 pandas 精确统计 + AI 洞察分析 | 仅供内部参考</p>
</div>

${chartScript}
</body></html>`;
}

function formatReportVal(val: unknown): string {
  if (val === null || val === undefined) return '-';
  if (typeof val === 'number') {
    if (!Number.isFinite(val)) return '-';
    if (Number.isInteger(val)) return val.toLocaleString();
    return val.toFixed(2);
  }
  const str = String(val);
  const isoMatch = str.match(/^(\\d{4}-\\d{2}-\\d{2})T\\d{2}:\\d{2}:\\d{2}/);
  return isoMatch ? isoMatch[1] : str;
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
): string {
  switch (template) {
    case 'grid':
      return buildGridLayout(kpis, echarts, title, hideChartTitle);
    case 'classic':
      return buildClassicLayout(kpis, echarts, title, hideChartTitle);
    case 'immersive':
      return buildImmersiveLayout(kpis, echarts, title, hideChartTitle);
    case 'command':
      return buildCommandLayout(kpis, tableData || [], title);
    case 'medical':
      return buildMedicalLayout(
        kpis, echarts, title, hideChartTitle,
        navTabs || ['数据总览', '趋势洞察', '分类分析', '明细查询'],
        ringCharts || [],
        tableData || [],
      );
    case 'report':
      return buildReportHTML(
        kpis, echarts, title,
        reportSections || [],
        reportSummary || `数据共包含 ${kpis.length} 项关键指标，涵盖 ${echarts.length} 个可视化图表。`,
        reportConclusion || generateDefaultConclusion(kpis),
        rowCount,
      );
    default:
      return buildGridLayout(kpis, echarts, title, hideChartTitle);
  }
}

function generateDefaultConclusion(kpis: KPI[]): string {
  if (kpis.length === 0) return '暂无数据，无法生成结论。';
  const items = kpis.map(k => `${k.name}：${k.value}`).join('<br>');
  return `<strong>关键指标总结</strong><br>${items}<br><br><strong>建议</strong><br>• 持续关注核心指标变化趋势<br>• 对异常波动及时预警<br>• 定期更新数据以保持分析时效性`;
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
    w.widget_type === 'chart' && (w.chart_config as Record<string, unknown>)?.option
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

  // ----- KPI 卡片 HTML -----
  const kpiHtmlMap: Record<string, string> = {};
  kpiWidgets.forEach((w: Record<string, unknown>) => {
    const cfg = w.chart_config as Record<string, unknown> || {};
    const meta = w.metadata as Record<string, unknown> || {};
    // 优先 chart_config.value, 兜底 metadata (KPI 数值可能在 metadata.formatted/kpi_label/value 中)
    const val = (cfg.value ?? meta?.formatted ?? meta?.value ?? meta?.kpi_label ?? '') as string;
    const label = (cfg.label || meta?.kpi_label || meta?.label || w.title || '') as string;
    // 检查 sparkline 数据: 有数据就有趋势图
    const hasSpark = cfg.data && Array.isArray(cfg.data) && (cfg.data as unknown[]).length > 0;
    // 既没有数值也没有 sparkline 数据 → 不生成 HTML (避免空白占位)
    if (!val && !hasSpark) return;
    const color = (cfg.color || '#7DD3FC') as string;
    const icon = (cfg.icon || '📊') as string;
    kpiHtmlMap[String(w.widget_id)] = `
<div style="padding:14px 18px;border-radius:12px;background:rgba(56,189,248,0.08);border:1px solid rgba(56,189,248,0.15);display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:90px;">
  <div style="font-size:20px;margin-bottom:2px;">${icon}</div>
  <p style="font-size:10px;color:#94a3b8;margin-bottom:4px;">${label}</p>
  <p style="font-size:18px;font-weight:700;color:${color};text-shadow:0 0 8px ${color}40;">${val}</p>
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
${makeHeader(title)}
${filterBarHTML}
${sectionsHTML}
${makeEChartsScript(chartItems, hideTitle)}
</body>
</html>`;
}


function _buildFallbackReportSections(
  kpis: KPI[],
  echarts: EChartItem[],
  summary: string,
  conclusion: string,
): ReportSection[] {
  return [
    {
      type: 'overview',
      title: '数据概览',
      analysis: summary || `本数据集包含 ${kpis.length} 项关键指标`,
    },
    ...(kpis.length > 0 ? [{
      type: 'kpi',
      title: '核心指标',
      content: `<strong>关键指标总结</strong><br>${kpis.map(k => `${k.name}：${k.value}`).join('<br>')}<br><br><strong>建议</strong><br>• 持续关注核心指标变化趋势<br>• 对异常波动及时预警<br>• 定期更新数据以保持分析时效性`,
    }] : []),
    ...(echarts.length > 0 ? [{
      type: 'trend',
      title: '图表分析',
      analysis: echarts.map((e, i) => `图表 ${i+1}：${e.title || '未命名'}（${e.type || '未知'}）`).join('\n'),
    }] : []),
    ...(conclusion ? [{
      type: 'conclusion',
      title: '核心结论',
      analysis: conclusion,
    }] : []),
  ];
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
