/* 生成自包含 ECharts 交互式 HTML 大屏文件，保留所有 ECharts 交互和深色主题 */
import type { EChartItem } from '../types/api';

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
<div style="display:flex;align-items:center;justify-content:space-between;padding:16px 32px;border-bottom:2px solid rgba(139,92,246,0.15);">
  <div style="display:flex;align-items:center;gap:16px;">
    <div style="width:8px;height:32px;background:linear-gradient(180deg,#8b5cf6,#22d3ee);border-radius:4px;"></div>
    <h1 style="font-size:28px;font-weight:700;letter-spacing:0.05em;text-shadow:0 0 25px rgba(139,92,246,0.5);">${title}</h1>
  </div>
  <div style="display:flex;align-items:center;gap:24px;font-size:13px;color:#94a3b8;">
    <span style="display:flex;align-items:center;gap:8px;">
      <span style="width:8px;height:8px;border-radius:50%;background:#4ade80;animation:pulse 2s infinite;"></span>
      实时数据
    </span>
    <span style="font-family:monospace;">${new Date().toLocaleString('zh-CN')}</span>
  </div>
</div>
<style>@keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.4; } }</style>`;
}

function makeKPICard(kpi: KPI) {
  const color = kpi.color || '#8b5cf6';
  const trendHtml = (kpi as any).trend && (kpi as any).trend !== 'flat' && (kpi as any).change != null && (kpi as any).change !== 0
    ? `<p style="font-size:10px;font-weight:600;margin-top:2px;color:${(kpi as any).trend === 'up' ? '#4ade80' : '#f87171'}">${(kpi as any).trend === 'up' ? '↑' : '↓'} ${Math.abs((kpi as any).change) >= 100 ? Math.abs((kpi as any).change).toFixed(0) : Math.abs((kpi as any).change).toFixed(1)}%</p>`
    : '';
  return `
<div style="flex:1;min-width:0;padding:16px;border-radius:12px;background:rgba(139,92,246,0.08);border:1px solid rgba(139,92,246,0.15);">
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
<div style="padding:10px 16px;border-bottom:1px solid rgba(139,92,246,0.1);display:flex;align-items:center;gap:10px;">
  <span style="width:8px;height:8px;border-radius:50%;background:#8b5cf6;"></span>
  <span style="font-size:13px;font-weight:600;color:#cbd5e1;">${title}</span>
</div>`;

  if (chartType === 'table' && tableData) {
    const convertedData = convertTableData(tableData);
    const tableHtml = makeTableHTML(convertedData);
    return `
<div data-chart-wrapper style="border-radius:16px;overflow:hidden;background:rgba(15,23,42,0.7);border:1px solid rgba(139,92,246,0.15);">
  ${titleHtml}
  <div style="width:100%;padding:12px;overflow:auto;max-height:${hideTitle ? height : height - 40}px;">
    ${tableHtml}
  </div>
</div>`;
  }

  if (chartType === 'analysis_table' && tableData) {
    const columns = tableData.columns || [];
    const rows = tableData.rows || [];
    let theadHtml = `<thead><tr style="background:rgba(34,211,238,0.1);"><th style="padding:8px 12px;text-align:left;font-size:11px;font-weight:600;color:#94a3b8;border-bottom:1px solid rgba(34,211,238,0.15);">${columns.join('</th><th style="padding:8px 12px;text-align:left;font-size:11px;font-weight:600;color:#94a3b8;border-bottom:1px solid rgba(34,211,238,0.15);">')}</th></tr></thead>`;
    let tbodyHtml = '<tbody>';
    rows.forEach((row: unknown[], ri: number) => {
      tbodyHtml += `<tr style="border-bottom:1px solid rgba(34,211,238,0.04);background:${ri % 2 === 0 ? 'rgba(15,23,42,0.5)' : 'transparent'};">`;
      row.forEach((cell: unknown) => {
        const val = cell !== null && cell !== undefined ? String(cell) : '-';
        tbodyHtml += `<td style="padding:8px 12px;font-size:11px;color:#e2e8f0;">${val}</td>`;
      });
      tbodyHtml += '</tr>';
    });
    tbodyHtml += '</tbody>';
    return `
<div data-chart-wrapper style="border-radius:16px;overflow:hidden;background:rgba(15,23,42,0.7);border:1px solid rgba(139,92,246,0.15);">
  ${titleHtml}
  <div style="width:100%;padding:12px;overflow:auto;max-height:${hideTitle ? height : height - 40}px;">
    <table style="width:100%;border-collapse:collapse;">${theadHtml}${tbodyHtml}</table>
  </div>
</div>`;
  }

  return `
<div data-chart-wrapper style="border-radius:16px;overflow:hidden;background:rgba(15,23,42,0.7);border:1px solid rgba(139,92,246,0.15);">
  ${titleHtml}
  <div id="${id}" style="width:100%;height:${hideTitle ? height : height - 40}px;"></div>
</div>`;
}

/** 环形图专用：去掉 overflow:hidden，避免 ECharts 渲染时边缘被裁 */
function makeRingChartDiv(id: string, title: string, height: number, hideTitle: boolean) {
  const titleHtml = hideTitle ? '' : `
<div style="padding:10px 16px;border-bottom:1px solid rgba(139,92,246,0.1);display:flex;align-items:center;gap:10px;">
  <span style="width:8px;height:8px;border-radius:50%;background:#8b5cf6;"></span>
  <span style="font-size:13px;font-weight:600;color:#cbd5e1;">${title}</span>
</div>`;
  return `
<div data-chart-wrapper style="border-radius:16px;background:rgba(15,23,42,0.7);border:1px solid rgba(139,92,246,0.15);">
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
    }

    function createHighlightBar() {
      var bar = document.createElement('div');
      bar.id = 'highlight-bar';
      bar.className = 'highlight-bar';
      bar.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:99999;display:none;align-items:center;justify-content:center;gap:12px;padding:8px 16px;background:rgba(139,92,246,0.15);border-bottom:1px solid rgba(139,92,246,0.2);';
      bar.innerHTML = '<span style="font-size:13px;color:#a78bfa;">🔗 联动高亮：<strong id="highlight-label-text" style="color:#fff;"></strong></span>' +
        '<button id="clear-highlight-btn" style="padding:4px 12px;font-size:12px;border-radius:6px;background:rgba(139,92,246,0.3);border:1px solid rgba(139,92,246,0.3);color:#a78bfa;cursor:pointer;font-family:inherit;">✕ 清除高亮</button>' +
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

    function renderAllCharts() {
      charts.forEach(function(c, idx) {
        var el = document.getElementById(c.id);
        if (!el) return;
        // 确保容器有最小尺寸（处理隐藏 tab 中的图表）
        if (el.offsetWidth === 0 || el.offsetHeight === 0) {
          el.style.width = '100%';
          el.style.minHeight = '400px';
          el.style.position = 'relative';
        }
        var chart = echarts.init(el);
        var option = JSON.parse(JSON.stringify(c.option));
        option.backgroundColor = 'transparent';
        chart.setOption(option);

        chart.on('click', function(params) {
          processClick(idx, params);
        });

        chart.getZr().on('click', function(e) {
          if (!e.target) {
            applyHighlight(null);
          }
        });
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
<div style="display:flex;gap:16px;padding:20px 32px;border-bottom:1px solid rgba(139,92,246,0.08);flex-wrap:wrap;">
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
    const color = k.color || '#8b5cf6';
    return `<div style="padding:12px;border-radius:10px;text-align:center;background:rgba(139,92,246,0.08);border:1px solid rgba(139,92,246,0.12);">
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
    ? '<div data-chart-wrapper style="flex:1;border-radius:16px;overflow:hidden;background:rgba(15,23,42,0.4);border:1px solid rgba(139,92,246,0.2);">' +
      (hideTitle ? '' : '<div style="padding:12px 20px;border-bottom:1px solid rgba(139,92,246,0.1);display:flex;align-items:center;gap:12px;">' +
        '<span style="width:10px;height:10px;border-radius:50%;background:#22d3ee;"></span>' +
        '<span style="font-size:15px;font-weight:600;">' + (mainChart.title || '主视图') + '</span>' +
        '</div>') +
      '<div style="width:100%;padding:12px;overflow:auto;max-height:520px;">' +
      makeTableHTML(convertTableData(mainChart.table_data)) +
      '</div></div>'
    : `<div data-chart-wrapper style="flex:1;border-radius:16px;overflow:hidden;background:rgba(15,23,42,0.4);border:1px solid rgba(139,92,246,0.2);">
  ${hideTitle ? '' : `<div style="padding:12px 20px;border-bottom:1px solid rgba(139,92,246,0.1);display:flex;align-items:center;gap:12px;">
    <span style="width:10px;height:10px;border-radius:50%;background:#22d3ee;"></span>
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
  <div style="position:absolute;top:0;left:50%;transform:translateX(-50%);width:400px;height:2px;background:linear-gradient(90deg,transparent,#8b5cf6,transparent);"></div>
  <h1 style="font-size:30px;font-weight:700;letter-spacing:0.15em;text-shadow:0 0 40px rgba(139,92,246,0.6);">${title}</h1>
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
    const color = k.color || '#22d3ee';
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
    const titleColor = isMain ? '#22d3ee' : '#8b5cf6';
    const titleHtml = hideTitle ? '' : '<div style="padding:10px 16px;border-bottom:1px solid #1e1e3a80;display:flex;align-items:center;gap:10px;">' +
      '<span style="width:10px;height:10px;border-radius:50%;background:' + titleColor + ';"></span>' +
      '<span style="font-size:13px;font-weight:600;color:#cbd5e1;">' + c.title + '</span>' +
      '</div>';
    if (c.chart_type === 'table' && c.table_data) {
      return '<div data-chart-wrapper style="border-radius:16px;overflow:hidden;background:rgba(10,10,30,0.8);border:1px solid rgba(139,92,246,0.15);position:relative;' + (isMain ? 'grid-row:span 2;' : '') + '">' +
        titleHtml +
        '<div style="width:100%;padding:12px;overflow:auto;max-height:' + chartH + 'px;">' +
        makeTableHTML(convertTableData(c.table_data)) +
        '</div></div>';
    }
    return '<div data-chart-wrapper style="border-radius:16px;overflow:hidden;background:rgba(10,10,30,0.8);border:1px solid rgba(139,92,246,0.15);position:relative;' + (isMain ? 'grid-row:span 2;' : '') + '">' +
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
  <div><h1 style="font-size:30px;font-weight:700;color:#fff;letter-spacing:0.2em;text-shadow:0 0 50px rgba(139,92,246,0.6);">⚡ ${title}</h1></div>
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
  const colors = ['#22d3ee', '#6366f1', '#f59e0b', '#10b981', '#ef4444'];
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
      borderColor: 'rgba(34,211,238,0.3)',
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
          a: { fontSize: titleFontSize, fontWeight: 'bold' as const, color: '#22d3ee', lineHeight: titleLineHeight, textShadow: '0 0 10px rgba(34,211,238,0.5)' },
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
      borderColor: 'rgba(34,211,238,0.3)',
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
      splitLine: { lineStyle: { color: 'rgba(34,211,238,0.1)' } },
      splitArea: { areaStyle: { color: ['rgba(34,211,238,0.01)', 'rgba(34,211,238,0.04)'] } },
      axisLine: { lineStyle: { color: 'rgba(34,211,238,0.15)' } }
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
    <tr>${headers.map(h => `<th style="padding:10px 12px;text-align:left;font-weight:600;color:#a78bfa;border-bottom:1px solid rgba(139,92,246,0.2);font-size:11px;text-transform:uppercase;letter-spacing:0.05em;">${h}</th>`).join('')}</tr>
  </thead>
  <tbody>
    ${rows.map((row, i) => `<tr style="${i % 2 === 0 ? 'background:rgba(15,23,42,0.5)' : ''}">
      ${headers.map(h => `<td style="padding:8px 12px;border-bottom:1px solid rgba(139,92,246,0.06);color:#cbd5e1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:180px;">${formatVal(row[h])}</td>`).join('')}
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
  const radarColors = ['#22d3ee', '#a78bfa', '#f59e0b'];
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
      const color = kpi.color || '#22d3ee';
      return `
    <div style="flex:0 0 auto;display:flex;flex-direction:column;align-items:center;padding:12px 24px;min-width:150px;background:linear-gradient(180deg,rgba(34,211,238,0.08) 0%,rgba(34,211,238,0.02) 100%);border:1px solid rgba(34,211,238,0.15);border-radius:4px;">
      <span style="font-size:10px;color:#94a3b8;margin-bottom:8px;">${kpi.title}</span>
      <div style="display:flex;gap:2px;align-items:center;">
        ${isNum ? digits.map((d: string) => `<div style="width:24px;height:32px;display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:bold;font-family:monospace;background:linear-gradient(180deg,rgba(34,211,238,0.2) 0%,rgba(34,211,238,0.05) 100%);border:1px solid rgba(34,211,238,0.3);color:${color};text-shadow:0 0 10px ${color}50;">${d}</div>`).join('') : `<span style="font-size:18px;font-weight:bold;color:${color};">${kpi.value}</span>`}
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
            <div style="padding:10px 16px;border-bottom:1px solid rgba(139,92,246,0.1);display:flex;align-items:center;gap:10px;">
              <span style="width:8px;height:8px;border-radius:50%;background:#8b5cf6;"></span>
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
              const bg = i < 3 ? 'rgba(34,211,238,0.08)' : 'transparent';
              return `<div style="display:flex;align-items:center;justify-content:space-between;padding:6px 10px;border-bottom:1px solid rgba(34,211,238,0.04);background:${bg};">
                <div style="display:flex;align-items:center;gap:8px;">
                  <span style="font-size:12px;font-weight:700;width:24px;text-align:center;color:${i < 3 ? '#e2e8f0' : '#64748b'};">${top8Badge(i)}</span>
                  <span class="text-truncate" style="max-width:100px;font-size:12px;color:#cbd5e1;">${String(item.name).slice(0, 12)}</span>
                </div>
                <span style="font-size:12px;font-weight:600;color:#22d3ee;">${item.value}</span>
              </div>`;
            }).join('\n            ') : '<div class="med-empty">暂无数据</div>'}
          </div>
        </div>
        ${displayRingCharts.length >= 3 ? `
        <div class="med-card" style="overflow:visible;">
          <div style="padding:10px 16px;border-bottom:1px solid rgba(139,92,246,0.1);display:flex;align-items:center;gap:10px;">
            <span style="width:8px;height:8px;border-radius:50%;background:#8b5cf6;"></span>
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
          style="width:192px;padding:6px 12px;border-radius:8px;border:1px solid rgba(139,92,246,0.2);background:rgba(15,23,42,0.9);color:#e2e8f0;font-size:12px;font-family:inherit;" />
        <select id="detail-filter-col" onchange="onFilterColChange()"
          style="padding:6px 8px;border-radius:8px;border:1px solid rgba(139,92,246,0.2);background:rgba(15,23,42,0.9);color:#94a3b8;font-size:12px;font-family:inherit;">
          <option value="">📌 按列过滤</option>
          ${Object.keys(tableData?.[0] || {}).map((col) => `<option value="${col}">${col}</option>`).join('\n          ')}
        </select>
        <input id="detail-filter-val" type="text" placeholder="过滤值..." oninput="filterDetailTable()"
          style="display:none;padding:6px 12px;border-radius:8px;border:1px solid rgba(139,92,246,0.2);background:rgba(15,23,42,0.9);color:#e2e8f0;font-size:12px;font-family:inherit;width:144px;" />
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
    setTimeout(function() {
      document.querySelectorAll('.med-panel.active [id]').forEach(function(el) {
        if (typeof echarts !== 'undefined') {
          var chart = echarts.getInstanceByDom(el);
          if (chart) chart.resize();
        }
      });
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
    html += '<th style="padding:8px 8px;text-align:left;font-weight:600;color:#94a3b8;border-bottom:1px solid rgba(34,211,238,0.1);font-size:11px;width:30px;">#</th>';
    headers.forEach(function(h) {
      html += '<th style="padding:8px 12px;text-align:left;font-weight:600;color:#94a3b8;border-bottom:1px solid rgba(34,211,238,0.1);font-size:11px;cursor:pointer;" onclick="sortDetailTable(' + headers.indexOf(h) + ')()">' + h + ' <span id="sort-arrow-' + headers.indexOf(h) + '" style="font-size:9px;"></span></th>';
    });
    html += '</tr></thead>';
    html += '<tbody>';
    rows.forEach(function(row, i) {
      html += '<tr style="' + (i % 2 === 0 ? '' : 'background:rgba(15,23,42,0.3)') + ';border-top:1px solid rgba(255,255,255,0.03);">';
      html += '<td style="padding:6px 8px;border-bottom:1px solid rgba(34,211,238,0.04);color:#64748b;font-size:10px;">' + (i + 1) + '</td>';
      headers.forEach(function(h) { html += '<td style="padding:6px 12px;border-bottom:1px solid rgba(34,211,238,0.04);color:#cbd5e1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:180px;">' + formatVal(row[h]) + '</td>'; });
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
  border-bottom: 1px solid rgba(34,211,238,0.1);
  background: linear-gradient(90deg, transparent 0%, rgba(34,211,238,0.05) 20%, rgba(34,211,238,0.05) 80%, transparent 100%);
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
  color: #22d3ee;
  background: rgba(34,211,238,0.1);
  border-top: 1px solid rgba(34,211,238,0.5);
  clip-path: polygon(10% 0%, 90% 0%, 100% 100%, 0% 100%);
}
.med-panel { display: none; padding-top: 16px; }
.med-panel.active { display: block; }
.med-card {
  border-radius: 12px;
  overflow: hidden;
  background: rgba(15,23,42,0.7);
  border: 1px solid rgba(139,92,246,0.15);
}
.med-card-inner { padding: 12px; }
.med-label {
  font-size: 12px;
  color: #22d3ee;
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
th:hover { color: #22d3ee; }
</style>
</head>
<body style="min-height:100vh;background:linear-gradient(180deg,#0a0f1a 0%,#0d1525 50%,#0a1628 100%);">
<div style="position:relative;display:flex;align-items:center;justify-content:center;padding:12px 24px;background:linear-gradient(90deg,transparent 0%,rgba(34,211,238,0.05) 20%,rgba(34,211,238,0.05) 80%,transparent 100%);border-bottom:1px solid rgba(34,211,238,0.15);">
  <div style="position:absolute;left:16px;top:50%;transform:translateY(-50%);display:flex;align-items:center;gap:8px;">
    <span style="width:8px;height:8px;border-radius:50%;background:#22d3ee;animation:pulse 2s infinite;"></span>
    <span style="font-size:12px;color:#64748b;">${new Date().toLocaleString('zh-CN')}</span>
  </div>
  <div style="display:flex;flex-direction:column;align-items:center;">
    <h1 style="font-size:20px;font-weight:700;color:#fff;letter-spacing:0.1em;margin-bottom:8px;text-shadow:0 0 20px rgba(34,211,238,0.5);">${title}</h1>
    <div class="med-tab-bar" style="border-bottom:none;background:transparent;padding:0;">
      ${tabs.map((t, i) => `<button class="med-tab${i === 0 ? ' active' : ''}" onclick="switchTab(${i})">${t}</button>`).join('\n      ')}
    </div>
  </div>
  <div style="position:absolute;right:16px;top:50%;transform:translateY(-50%);display:flex;align-items:center;gap:8px;">
    <span style="display:flex;align-items:center;gap:6px;font-size:12px;color:#22d3ee;">
      <span style="width:6px;height:6px;border-radius:50%;background:#22d3ee;animation:pulse 2s infinite;"></span>系统正常
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
    const color = kpi.color || '#22d3ee';
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
  .header { display:flex; align-items:center; justify-content:space-between; padding:12px 24px; border-bottom:1px solid rgba(34,211,238,0.12); flex-shrink:0; }
  .header-bar { width:6px; height:24px; background:linear-gradient(180deg,#22d3ee,#8b5cf6); border-radius:3px; }
  .kpis-wrap { display:flex; justify-content:center; gap:12px; flex-wrap:wrap; padding:12px 24px; border-bottom:1px solid rgba(34,211,238,0.08); flex-shrink:0; }
  .kpi-card { display:flex; flex-direction:column; align-items:center; padding:12px 24px; min-width:150px; background:linear-gradient(180deg,rgba(34,211,238,0.08) 0%,rgba(34,211,238,0.02) 100%); border:1px solid rgba(34,211,238,0.15); border-radius:4px; }
  .kpi-card .label { font-size:10px; color:#94a3b8; margin-bottom:6px; }
  .kpi-card .value { font-size:22px; font-weight:700; text-shadow:0 0 10px rgba(34,211,238,0.5); }
  .digit { width:24px; height:32px; display:flex; align-items:center; justify-content:center; font-size:18px; font-weight:700; font-family:monospace; background:linear-gradient(180deg,rgba(34,211,238,0.2),rgba(34,211,238,0.05)); border:1px solid rgba(34,211,238,0.3); border-radius:2px; }
  .main-row { flex:1; display:flex; gap:12px; padding:12px; min-height:0; }
  .side-panel { width:20%; min-width:220px; display:flex; flex-direction:column; border-radius:8px; border:1px solid rgba(34,211,238,0.08); background:rgba(34,211,238,0.03); padding:12px 16px; overflow:hidden; }
  .side-panel .sec-label { font-size:11px; font-weight:600; color:#22d3ee; margin-bottom:8px; letter-spacing:0.05em; }
  .side-panel .kpi-row { display:flex; align-items:center; justify-content:space-between; padding:6px 0; border-bottom:1px solid rgba(34,211,238,0.06); font-size:11px; }
  .center-panel { flex:1; min-width:0; border-radius:8px; border:1px solid rgba(34,211,238,0.08); background:rgba(34,211,238,0.02); overflow:hidden; }
  .map-label { position:absolute; top:10px; left:14px; z-index:10; font-size:11px; color:#22d3ee; font-weight:600; letter-spacing:0.05em; }
  table { width:100%; border-collapse:collapse; font-size:10px; }
  thead tr { background:rgba(139,92,246,0.1); }
  th { padding:6px 8px; text-align:left; color:#94a3b8; font-size:10px; font-weight:500; border-bottom:1px solid rgba(34,211,238,0.08); }
  td { padding:5px 8px; border-bottom:1px solid rgba(34,211,238,0.04); }
  .ranking-item { display:flex; align-items:center; justify-content:space-between; padding:8px 10px; border-bottom:1px solid rgba(34,211,238,0.06); }
  .ranking-badge { font-size:12px; font-weight:700; width:28px; text-align:center; }
  .ranking-name { font-size:12px; max-width:100px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .ranking-val { font-size:13px; font-weight:700; color:#22d3ee; }
  .footer { flex-shrink:0; padding:8px 24px; font-size:11px; color:#64748b; border-top:1px solid rgba(34,211,238,0.08); background:rgba(34,211,238,0.04); }
  @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.4; } }
</style>
</head>
<body>
<div class="header">
  <div style="display:flex;align-items:center;gap:12px;">
    <div class="header-bar"></div>
    <h1 style="font-size:20px;font-weight:700;color:#fff;letter-spacing:0.1em;text-shadow:0 0 30px rgba(34,211,238,0.6);">数据智能指挥中心</h1>
  </div>
  <span style="display:flex;align-items:center;gap:8px;font-size:12px;color:#22d3ee;">
    <span style="width:8px;height:8px;border-radius:50%;background:#22d3ee;animation:pulse 2s infinite;"></span>系统运行中
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
        const color = kpi.color || '#22d3ee';
        const numVal = typeof kpi.value === 'number' ? kpi.value : parseFloat(String(kpi.value));
        return `<div class="kpi-row">
          <span style="color:#94a3b8;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:100px;">${kpi.title}</span>
          <span style="font-weight:700;font-family:monospace;color:${color};">${isNaN(numVal) ? kpi.value : numVal.toLocaleString()}</span>
        </div>`;
      }).join('\n      ')}
    </div>
    <div class="sec-label" style="margin-top:12px;color:#a78bfa;">📋 数据预览</div>
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
        const color = kpi.color || '#22d3ee';
        const numVal = typeof kpi.value === 'number' ? kpi.value : parseFloat(String(kpi.value));
        return `<div class="kpi-row">
          <span style="color:#94a3b8;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:100px;">${kpi.title}</span>
          <span style="font-weight:700;font-family:monospace;color:${color};">${isNaN(numVal) ? kpi.value : numVal.toLocaleString()}</span>
        </div>`;
      }).join('\n      ')}
    </div>
    <div class="sec-label" style="margin-top:12px;color:#a78bfa;">🏆 ${catCol} 排行 TOP5</div>
    <div style="height:160px;overflow:auto;">
      ${rankingData.length > 0 ? rankingData.map((item, i) => {
        const badge = i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : i + 1;
        const bg = i < 3 ? 'rgba(34,211,238,0.06)' : 'transparent';
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
  总记录数：<span style="color:#22d3ee;font-weight:600;">${tableData?.length || 0}</span>
  &nbsp;|&nbsp; 数据字段：<span style="color:#22d3ee;font-weight:600;">${columns.length}</span>
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
      tooltip: { trigger: 'item', backgroundColor: 'rgba(10,22,40,0.95)', borderColor: 'rgba(34,211,238,0.3)', textStyle: { color: '#e2e8f0', fontSize: 11 } },
      geo: {
        map: 'china',
        roam: false,
        itemStyle: { areaColor: 'rgba(34,211,238,0.08)', borderColor: 'rgba(34,211,238,0.25)', borderWidth: 0.5 },
        emphasis: { itemStyle: { areaColor: 'rgba(34,211,238,0.3)' }, label: { show: true, color: '#fff', fontSize: 10 } },
      },
      series: [
        {
          type: 'effectScatter',
          coordinateSystem: 'geo',
          data: cities.map(function(d) { return { name: d.name, value: [d.value[0], d.value[1], d.value[2] * 15] }; }),
          symbolSize: function(val) { return val[2]; },
          rippleEffect: { scale: 3, period: 5, color: '#22d3ee' },
          itemStyle: { color: '#22d3ee' },
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
          lineStyle: { color: '#22d3ee', width: 1, opacity: 0.5, curveness: 0.2 },
          effect: { show: true, period: 5, trailLength: 0.3, symbolSize: 4, color: '#22d3ee' },
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

function buildReportHTML(
  kpis: KPI[],
  echarts: EChartItem[],
  title: string,
  sections: ReportSection[],
  aiSummary: string,
  aiConclusion: string,
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
    font-size: 14px; line-height: 1.8; color: #333;
    margin: 0; padding: 20px 40px;
    background: #ffffff; max-width: 1100px; margin: 0 auto;
  }
  @media print {
    body { padding: 0; }
  }
  .cover-page {
    text-align: center; padding: 40px 20px;
    background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
    border: 1px solid #dee2e6; border-radius: 8px; margin-bottom: 20px;
  }
  .cover-title { font-size: 32px; color: #0d1b2a; font-weight: bold; margin-bottom: 8px; }
  .cover-subtitle { font-size: 16px; color: #6c757d; margin-bottom: 18px; }
  .cover-meta { font-size: 13px; color: #6c757d; }
  .cover-meta span { margin: 0 12px; }
  h1 {
    font-size: 26px; color: #0d1b2a;
    border-bottom: 3px solid #0d1b2a;
    padding-bottom: 6px; margin: 14px 0 8px;
  }
  h2 {
    font-size: 20px; color: #0d1b2a;
    border-bottom: 2px solid #1b4965;
    padding-bottom: 6px; margin: 12px 0 8px;
  }
  h3 { font-size: 16px; color: #1b4965; margin: 8px 0 6px; }
  .metrics-row { text-align: center; margin: 10px 0; display: flex; flex-wrap: wrap; justify-content: center; gap: 10px; }
  .metric-card {
    background: #f8f9fa; border: 1px solid #dee2e6;
    border-radius: 8px; padding: 12px 20px; text-align: center;
    min-width: 140px; flex: 1 1 auto;
    display: flex; flex-direction: column; justify-content: center; align-items: center;
  }
  .metric-abbr { font-size: 26px; font-weight: bold; margin: 2px 0; white-space: nowrap; }
  .metric-full { font-size: 10px; color: #adb5bd; margin: 2px 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%; }
  .metric-label { font-size: 11px; color: #6c757d; margin-top: 2px; }
  .metric-excellent { color: #28a745; }
  .metric-good { color: #00b4d8; }
  .metric-warning { color: #fd7e14; }
  .metric-danger { color: #dc3545; }
  table { width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 12px; }
  th, td { border: 1px solid #dee2e6; padding: 8px 6px; text-align: center; }
  th { background: #0d1b2a; color: #fff; font-weight: 600; }
  tr:nth-child(even) { background: #f8f9fa; }
  .chart-container { text-align: center; margin: 10px 0; width: 100%; display: block; overflow: hidden; }
  .chart-caption { font-size: 13px; color: #6c757d; margin-top: 6px; text-align: center; font-style: italic; }
  .analysis-text { margin: 10px 0; text-indent: 2em; }
  .trend-up { color: #28a745; font-weight: 700; }
  .trend-down { color: #dc3545; font-weight: 700; }
  .trend-flat { color: #6c757d; font-weight: 700; }
  .highlight-box {
    background: #d4edda; border: 1px solid #28a745;
    padding: 15px 20px; margin: 20px 0; border-radius: 8px;
  }
  .warning-box {
    background: #fff3cd; border: 1px solid #fd7e14;
    padding: 15px 20px; margin: 20px 0; border-radius: 8px;
  }
  .section { margin-bottom: 6px; }
  .toc { background: #f8f9fa; padding: 16px 24px; border-radius: 8px; margin: 16px 0; line-height: 2.2; }
  .toc ol { margin: 8px 0 0 0; padding: 0 0 0 24px; }
  .footer { text-align: center; color: #adb5bd; font-size: 11px; margin-top: 20px; padding-top: 12px; border-top: 1px solid #dee2e6; }
  /* ★ 洞察标签样式 */
  .insight-tag {
    display: inline-block; font-size: 11px; padding: 1px 8px; border-radius: 8px;
    margin-right: 6px; font-weight: 600;
  }
  .insight-trend { background: #d4edda; color: #155724; }
  .insight-structure { background: #cce5ff; color: #004085; }
  .insight-concentration { background: #fff3cd; color: #856404; }
  .insight-anomaly { background: #f8d7da; color: #721c24; }
  .insight-risk { background: #ffeaa7; color: #6c5b00; }
</style>
</head>
<body>
<div class="cover-page">
  <div class="cover-title">${title}</div>
  <div class="cover-subtitle">专业数据分析报告 | Data Analysis Report</div>
  <div class="cover-meta">
    <span>📅 ${new Date().toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })}</span>
    <span>📊 数据行数: ${kpis.reduce((a, k) => a + (Number(k.value) || 0), 0).toLocaleString()}</span>
  </div>
</div>

<div class="toc">
  <strong>📋 报告目录</strong>
  <ol>${tocItems.map(t => `<li>${t}</li>`).join('')}</ol>
</div>

${kpiHTML ? `<div class="metrics-row-container">${kpiHTML}</div>` : ''}

<div class="section">
  <h1>1. ${overviewSection ? cleanTitle(overviewSection.title) : '数据概览'}</h1>
  ${aiSummary ? `<div class="analysis-text">${aiSummary.replace(/\n/g, '<br>')}</div>` : ''}
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
  const items = kpis.map(k => <strong>\</strong>：\\</strong>).join('<br>');
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
