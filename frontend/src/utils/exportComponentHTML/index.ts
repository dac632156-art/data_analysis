/**
 * index.ts —— 将数据看板（SmartDashboard）导出为单文件 HTML。
 *
 * 策略（路径甲：组件打包 UMD，与屏幕共用一份代码）：
 *   - 导出前在本模块（构建期）跑 layout.ts 纯函数算出 layout（与屏幕一致）
 *   - 仙气组件树打包成 ethereal-core.js UMD（vite build:lib 产出，含 echarts/gl，
 *     external React/ReactDOM 走 CDN），内联进 HTML
 *   - 水彩背景图（背景.png / bg5.png）通过 assets.ts 的 ?inline 转 base64，
 *     经 cardBgUrl prop 传给组件（饼图用 bg5 染色、其余卡片用背景图）
 *   - HTML 内用 CDN React + 内联 UMD，直接 <EtherealCore.EtherealChart .../>
 *     复用屏幕同款渲染（饼图 canvas 染色 / 单位函数 / 阈值线 / EChartView 增强层全自带）
 *
 * 导出内容严格与屏幕当前模式一致（mode 由 DashboardPage 受控传入）。
 */
import * as api from '../../api/client';
import { extractChartsFromSavedPackages, buildSemanticLayout } from '../../components/BigScreen/layout';
import type { SmartLayoutChart, SmartLayoutItem } from '../../types/dashboard';
import { BG_CARD, BG_SLICE } from './assets';
import { THEME_CSS } from './theme.css.ts';
// 仙气看板组件树 UMD（由 `npm run build:lib` 产出，含 echarts/gl，external React/ReactDOM 走 CDN）
// 注意：dist-lib 是构建产物，需先执行 build:lib 才会存在。
// @ts-ignore - ?raw 在 vite/client 已声明，但 dist-lib 在 src 外，tsc 可能找不到模块
import etherealCoreJs from '../../../dist-lib/ethereal-core.js?raw';

export interface GenerateComponentHTMLOptions {
  mode: 'A' | 'B' | 'C';
  sessionId: string;
  title: string;
}

/**
 * 主入口：生成单文件 HTML 字符串。
 */
export async function generateComponentHTML(opts: GenerateComponentHTMLOptions): Promise<string> {
  const { mode, sessionId, title } = opts;

  // 1) 拉同款 packages（与屏幕 SmartDashboard 同源）
  let packages: any[] = [];
  try {
    const res: any = await api.getSavedPackages(sessionId);
    packages = (res && res.packages) || [];
  } catch (err) {
    console.error('[generateComponentHTML] 拉取 saved_packages 失败:', err);
    throw err;
  }
  if (!packages.length) {
    throw new Error('暂无可视化内容，无法导出');
  }

  // 2) 跑布局纯函数（与屏幕一致）
  let remappedData: {
    charts: SmartLayoutChart[];
    items: SmartLayoutItem[];
    layout: { gridTemplateAreas: string; rowHeights: string; assignments: any[]; rowCount: number };
  };
  try {
    const { charts, items } = extractChartsFromSavedPackages(packages);
    const layout = buildSemanticLayout(charts as any, items, mode);
    remappedData = { charts, items, layout };
  } catch (err) {
    console.error('[generateComponentHTML] 布局计算失败:', err);
    throw err;
  }

  // 3) 序列化：把 charts/layout 转 JSON，转义 </script> 防注入
  const payload = JSON.stringify({
    charts: remappedData.charts,
    layout: remappedData.layout,
    bgCard: BG_CARD,
    bgSlice: BG_SLICE,
    mode,
    title,
    exportTime: new Date().toLocaleString('zh-CN'),
  }).replace(/<\/script>/gi, '<\\/script>');

  // 4) 组装 HTML（内联 UMD + 数据 + 渲染器）
  return buildHTML(payload, etherealCoreJs as unknown as string);
}

/**
 * 组装完整 HTML 文档。
 * @param payload 注入的看板数据 JSON（已转义）
 * @param umd 仙气组件树 UMD 源码（含 echarts/gl，external React/ReactDOM）
 */
function buildHTML(payload: string, umd: string): string {
  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>数据看板导出</title>
<!-- 注意：需先 build:lib 生成 dist-lib/ethereal-core.js -->
<script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
<script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
<style>
${THEME_CSS}
</style>
</head>
<body>
<div id="root"></div>
<script>
// ===== 注入数据（含内联水彩 png base64）=====
window.__DASHBOARD_DATA__ = ${payload};
</script>
<script>
// ===== 仙气看板组件树 UMD（含 echarts/gl，与屏幕共用一份代码）=====
${umd}
</script>
<script>
// ===== 渲染器：复用屏幕同款 EtherealChart 组件 =====
(function () {
  try {
    var React = window.React;
    var ReactDOM = window.ReactDOM;
    var Core = window.EtherealCore;
    if (!Core || !Core.EtherealChart) {
      document.getElementById('root').innerHTML = '<div style="padding:40px;color:#b91c1c">组件库加载失败（EtherealCore 未就绪）</div>';
      return;
    }
    var DATA = window.__DASHBOARD_DATA__ || { charts: [], layout: { assignments: [] } };
    var BG_CARD = DATA.bgCard;
    var BG_SLICE = DATA.bgSlice;

    // 判断是否为表格类卡片（兼容多种字段命名）
    function isTableType(c) {
      if (!c) return false;
      var t = (c.chart_type || '').toLowerCase();
      if (t === 'table') return true;
      if (c.table_data && (c.table_data.columns || c.table_data.rows)) return true;
      return false;
    }

    // 内联表格渲染：对齐屏幕端 EtherealTable 视觉风格
    //   A) table_data = { columns:[{key,label}], rows:[{key:val,...}] }（dict 行）
    //   B) table_data = { columns:['a','b'], rows:[[v1,v2],...] }（二维数组，RenderedCell 可能带 .value）
    function ExportTable(props) {
      var chart = props.chart || {};
      var td = chart.table_data || {};
      var rawColumns = td.columns || [];
      var rows = td.rows || [];

      // ★ 样式声明必须放在函数体顶部：headCells/bodyRows 在下面通过闭包引用这些变量，
      //   var 声明虽然会 hoisting 但赋值不会前移；声明放顶部保证引用时已是已赋值的对象。
      // ★ tableLayout:'fixed' + 第一列固定宽，其余列等宽均分：避免 auto 模式下
      //   "前几列内容短挤左边、最后一列内容长拉满右边" 导致的视觉错位（列数对、但看着歪）。
      var tableStyle = {
        borderCollapse: 'collapse', width: '100%',
        tableLayout: 'fixed', fontSize: 13,
        fontFamily: '-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif',
      };
      // 表头单元格样式：表头文本都很短，允许 nowrap + ellipsis 兜底
      var thStyle = { textAlign: 'left', padding: '9px 10px', borderBottom: '2px solid rgba(139,92,246,.35)', color: '#4C1D95', fontWeight: 700, whiteSpace: 'nowrap', letterSpacing: '.02em', overflow: 'hidden', textOverflow: 'ellipsis' };
      // 普通 td 样式：不要 ellipsis / nowrap —— 内容允许换行，超长文本会自动撑高行高，
      // 而不是被截成 "高历史消费久未…" 这种残缺（之前误给所有 td 加 ellipsis 导致的回归 bug）。
      var tdStyle = { padding: '8px 10px', borderBottom: '1px solid rgba(148,163,184,.15)', color: '#334155', lineHeight: '1.5', verticalAlign: 'middle', wordBreak: 'break-word', overflowWrap: 'anywhere' };
      // 第一列固定 180px（之前 116 太窄，长簇名如「高历史消费久未活跃客」被 ellipsis 截断）：
      // 180px 在 12.5px 字号下可容下约 14 个汉字，足够覆盖所有常见簇名。
      // 保留 ellipsis + nowrap 是为了：万一以后出现 14 字以上的簇名，能优雅省略而不撑爆表格。
      var firstColStyle = { width: 180, minWidth: 180, maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' };
      // 最后一列：内容（如「VIP_Targeted_Bundle」）通常较长且不可拆分（保持完整才有意义），允许换行
      var lastColStyle = { wordBreak: 'break-word', overflowWrap: 'anywhere' };

      // ★ 行数限制
      var MAX_ROWS = 12;
      if (rows.length > MAX_ROWS) rows = rows.slice(0, MAX_ROWS);

      // ★ 以实际数据行为准确定真实列集合：避免 columns 声明了 N 列但 dict 行只有 M 个 key（N≠M，
      //   例如后端给关联规则表多声明了「总收入」列但个别行没有该字段），导致表头比数据多/少列 → 错位。
      //   dict 行：只保留 columns 中 row 实际存在的列（过滤掉 row 里没有的「幽灵列」），表头与数据严格一致。
      var columns;
      if (rows.length > 0 && typeof rows[0] === 'object' && rows[0] !== null && !Array.isArray(rows[0])) {
        var firstKeys = Object.keys(rows[0]);
        columns = rawColumns.filter(function (c) {
          var k = (typeof c === 'object') ? (c.key != null ? c.key : c.label) : c;
          return firstKeys.indexOf(k) !== -1;
        });
        // 兜底：若 columns 过滤后为空（极端情况），直接回退到 dict 实际 key 列表
        if (columns.length === 0) columns = firstKeys;
      } else if (rows.length > 0 && Array.isArray(rows[0])) {
        // 数组行：以首行 cell 数为准截断 columns
        columns = rawColumns.slice(0, rows[0].length);
        if (columns.length === 0) {
          for (var _i = 0; _i < rows[0].length; _i++) columns.push('列' + (_i + 1));
        }
      } else {
        columns = rawColumns.slice();
      }
      // 兜底：若 columns 过滤后仍为空（极端情况），按数据行实际列数生成序号列头，
      // 避免整张表因 columns 为空而渲染空白。actualColCount 使用数据行的真实列数（数组行长或 dict keys 长）。
      if (columns.length === 0 && rows.length > 0) {
        var fallbackCount = Array.isArray(rows[0]) ? rows[0].length : Object.keys(rows[0]).length;
        for (var _i = 0; _i < fallbackCount; _i++) { columns.push('列' + (_i + 1)); }
      }

      var cellText = function (cell) {
        if (cell == null) return '';
        if (typeof cell === 'object') return ('' + (cell.value != null ? cell.value : (cell.text != null ? cell.text : '')));
        return '' + cell;
      };

      // 胶囊色板（与 EtherealTable 一致）
      var PILL_COLORS = ['#DDD6FE', '#C7D2FE', '#BFDBFE', '#A5F3FC', '#A7F3D0', '#FDE68A', '#FECACA'];
      var getPillColor = function (ri) { return PILL_COLORS[ri % PILL_COLORS.length]; };

      // 列头（应用 thStyle），第一列固定宽，其余均分
      var headCells = columns.map(function (col, i) {
        var label = (typeof col === 'object') ? (col.label != null ? col.label : col.key) : col;
        var st = (i === 0) ? Object.assign({}, thStyle, firstColStyle) : (i === columns.length - 1 ? Object.assign({}, thStyle, lastColStyle) : thStyle);
        return React.createElement('th', { key: 'h' + i, style: st }, label);
      });

      // 数据行——第一列渲染为胶囊标签
      //   dict 行：按 columns 顺序取 row[col]（严格对齐表头）
      //   数组行：直接按索引取值
      var colCount = columns.length;
      var bodyRows = rows.map(function (row, ri) {
        var cells;
        if (Array.isArray(row)) {
          cells = row.slice(0, colCount).map(function (cell, ci) {
            var st = (ci === 0) ? Object.assign({}, tdStyle, firstColStyle)
                  : (ci === colCount - 1 ? Object.assign({}, tdStyle, lastColStyle) : tdStyle);
            if (ci === 0) {
              return React.createElement('td', { key: 'c' + ci, style: st },
                React.createElement('span', { style: pillStyle(getPillColor(ri)) }, cellText(cell))
              );
            }
            return React.createElement('td', { key: 'c' + ci, style: st }, cellText(cell));
          });
        } else if (typeof row === 'object') {
          // ★ dict 行：严格按 columns（已过滤为 row 的有效 key 集合）顺序取 row[key]，
          //   保证每行列数 = 表头列数，且值与列头一一对应（杜绝错位）。
          cells = columns.map(function (col, ci) {
            var key = (typeof col === 'object') ? (col.key != null ? col.key : col.label) : col;
            var val = (row != null) ? row[key] : undefined;
            var st = (ci === 0) ? Object.assign({}, tdStyle, firstColStyle)
                  : (ci === columns.length - 1 ? Object.assign({}, tdStyle, lastColStyle) : tdStyle);
            if (ci === 0) {
              return React.createElement('td', { key: 'c' + ci, style: st },
                React.createElement('span', { style: pillStyle(getPillColor(ri)) }, cellText(val))
              );
            }
            return React.createElement('td', { key: 'c' + ci, style: st }, cellText(val));
          });
        } else {
          cells = [React.createElement('td', { key: 'c0' },
            React.createElement('span', { style: pillStyle(getPillColor(ri)) }, '' + row)
          )];
        }
        // 补齐不足的单元格（用空 td），保证每行列数 = 表头列数
        while (cells.length < colCount) {
          var padIdx = cells.length;
          var padSt = (padIdx === 0) ? Object.assign({}, tdStyle, firstColStyle)
                    : (padIdx === colCount - 1 ? Object.assign({}, tdStyle, lastColStyle) : tdStyle);
          cells.push(React.createElement('td', { key: 'pad' + padIdx, style: padSt }, ''));
        }
        return React.createElement('tr', { key: 'r' + ri }, cells);
      });

      // 毛玻璃卡片容器（对齐屏幕端 EtherealTable 外观）
      var wrapStyle = {
        width: '100%', height: '100%', overflow: 'auto',
        padding: '18px 22px', boxSizing: 'border-box',
        backgroundImage: props.cardBg ? 'url(' + props.cardBg + ')' : undefined,
        backgroundSize: 'cover', backgroundPosition: 'center',
        borderRadius: 16,
      };

      // tableStyle/thStyle/tdStyle/firstColStyle/lastColStyle 已在函数顶部声明

      return React.createElement('div', { style: wrapStyle, className: 'ed-table-wrap' },
        props.title ? React.createElement('div', { style: { color: '#1E293B', fontSize: 15, fontWeight: 800, marginBottom: 16, letterSpacing: '.01em' } }, props.title) : null,
        React.createElement('table', { style: tableStyle },
          React.createElement('thead', null, headCells.length ? React.createElement('tr', null, headCells) : null),
          React.createElement('tbody', null, bodyRows)
        )
      );
    }

    // 胶囊标签样式工厂（闭包复用）
    function pillStyle(bg) {
      return {
        display: 'inline-block', padding: '4px 14px', borderRadius: 999,
        background: bg, color: '#4C1D95', fontWeight: 700, fontSize: 12.5,
        whiteSpace: 'nowrap', letterSpacing: '.01em',
      };
    }

  function ChartSlot(props) {
    var chart = props.chart;
    var a = props.assignment;
    var ct = (chart.chart_type || '').toLowerCase();
    var isPie = (ct === 'pie' || ct === 'donut');
    // 外层卡片背景统一用背景图(BG_CARD)；饼图扇区染色专用 bg5(BG_SLICE)
    var cardBg = BG_CARD;
    var sliceUrl = isPie ? BG_SLICE : undefined;
    if (ct === 'metric') {
      var o = chart.option || {};
      return React.createElement(Core.EtherealMetricCard, {
        metricData: {
          title: o.label || chart.title || '核心指标',
          label: o.label,
          value: o.value,
          change: o.change,
          unit: o.unit,
        },
      });
    }
    // ★ 表格卡片：数据在 chart.table_data（columns/rows），EtherealChart 只认 echarts option，
    //   option 为空 → 空白。UMD 未暴露 EtherealTable，故此处内联原生表格渲染，
    //   兼容「二维 RenderedCell 数组」与「dict 行数组」两种形态。
    if (ct === 'table' || isTableType(chart)) {
      return React.createElement(ExportTable, { chart: chart, title: a.title || chart.title, cardBg: cardBg });
    }
    // 注意：传给 EtherealChart 的 chartNode 必须是真正的 echarts option（含 series/data），
    // 与屏幕端 ChartRegistry.renderSmartChart 传 chart.option 保持一致；
    // 不能传整个 SmartLayoutChart（其 series 在 .option 里，子组件读 node.series 会拿到 undefined → 图表空白）。
    return React.createElement(Core.EtherealChart, {
      slot: chart.slot || '',
      chartType: ct,
      chartNode: chart.option || {},
      data: chart.raw_data || undefined,
      title: a.title || chart.title,
      cardBgUrl: cardBg,
      sliceTextureUrl: sliceUrl,
      height: '100%',
    });
  }

  function Card(props) {
    var a = props.assignment;
    var chart = props.chart;
    if (!chart) {
      return React.createElement('div', {
        style: { gridArea: a.area || a.slot, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#94A3B8', fontSize: 13 },
      }, '— 暂无图表 —');
    }
    return React.createElement('div', { style: { gridArea: a.area || a.slot, minHeight: 0, minWidth: 0 } },
      React.createElement(ChartSlot, { key: a.slot, assignment: a, chart: chart })
    );
  }

  function App() {
    var layout = DATA.layout;
    // ★ 修复白屏根因：charts[i].slot 可能全为 null（序列化/数据源问题），
    //   导致纯 slot 匹配全部失败 → 50 个格子全是「— 暂无图表 —」。
    //   策略：构建双索引 map（slot key + index fallback），匹配时先 slot 后 index。
    var chartsByKey = {};   // slot → chart（slot 非空时）
    var chartsByIndex = []; // index → chart（有序，用于 index fallback）
    (DATA.charts || []).forEach(function (c, idx) {
      if (!c) return;
      chartsByIndex[idx] = c;
      if (c.slot) chartsByKey[c.slot] = c;
    });
    // assignments 按布局顺序排列，依次消费 chartsByIndex
    var nextIdx = 0;
    function resolveChart(a, ai) {
      if (a.slot && chartsByKey[a.slot]) return chartsByKey[a.slot];
      if (nextIdx < chartsByIndex.length) return chartsByIndex[nextIdx++];
      return undefined;
    }
    return React.createElement('div', { style: { minHeight: '100vh' } },
      React.createElement('div', { className: 'ed-topbar' },
        React.createElement('div', { className: 'ed-title' }, DATA.title || '数据看板'),
        React.createElement('div', { className: 'ed-mode-badge' }, '模式 ' + DATA.mode)
      ),
      React.createElement('div', {
        className: 'ed-grid',
        style: { gridTemplateAreas: layout.gridTemplateAreas, gridTemplateRows: layout.rowHeights },
      }, (layout.assignments || []).map(function (a, ai) {
        return React.createElement(Card, { key: a.slot || ('a_' + ai), assignment: a, chart: resolveChart(a, ai) });
      })),
      React.createElement('div', { className: 'ed-footer' },
        '导出时间：' + DATA.exportTime + ' · 数据来源：已保存分析包')
    );
  }

  ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(App));
  } catch (e) {
    var msg = (e && e.message) ? e.message : String(e);
    document.getElementById('root').innerHTML = '<div style="padding:40px;color:#b91c1c;font-size:13px">渲染异常：' + msg + '</div>';
  }
})();
</script>
</body>
</html>`;
}
