/**
 * 仙气毛玻璃表格（React 版）
 * ★ 严格移植自「可视化模板库/同期群分析/表格组件.js」，视觉风格未改（背景.png / 胶囊 / 毛玻璃 / 浅色文字）。
 * 仅增强「数据读取层」，让组件能直接识别三种输入形态（统一全站表格出口）：
 *   1) 纯值 dict 行：rows = [{列名: 值}, ...]            （看板 DataTable 走这种）
 *   2) 含 {value} 包装的 dict 行：rows = [{列名: {value,...}}, ...]   （分析包 dict 行形态）
 *   3) 二维 cell 数组：rows = [[{value,color,direction,highlight}, ...], ...]  （后端 RenderedCell[][]，profile_overview 走这种）
 * 第1列始终渲染为彩色胶囊（colorPalette 认得 RFM 群名，否则默认紫色兜底）；
 * 其余列的 RenderedCell 若带 direction 字段则显示 ↑/↓ 箭头；cell.color 优先于调色板决定胶囊颜色。
 * 去掉原版自动 fetch mock7.json 的自愈逻辑，数据全部由 props 传入。
 */
import React from 'react';

const CARD_BG_URL = new URL('../../assets/ethereal/背景.png', import.meta.url).href;

/** 后端下发的结构化单元格（package_render.RenderedCell） */
interface RenderedCell {
  value?: unknown;
  color?: string;
  highlight?: boolean;
  rank?: unknown;
  direction?: 'up' | 'down' | 'flat' | string;
  cell_type?: string;
  type?: string;
  [k: string]: unknown;
}

interface Props {
  chartNode?: { title?: string; columns?: string[]; rows?: unknown[] };
  /** rows 为二维 cell 数组时显式传 columns（后端 RenderedCell[][] 形态） */
  columns?: string[];
  /** 是否在第1列前额外渲染「#」序号列（看板数据预览表保留序号习惯） */
  showIndex?: boolean;
  title?: string;
  cardBgUrl?: string;
}

const colorPalette: Record<string, { bg: string; text: string }> = {
  高价值核心客户: { bg: '#C8E1F5', text: '#1E3A8A' },
  潜力高价值客户: { bg: '#D7EFE5', text: '#064E3B' },
  沉睡高价值客户: { bg: '#E2C9F3', text: '#4C1D95' },
  流失预警高价值客户: { bg: '#FCCDDF', text: '#831843' },
  稳定普通客户: { bg: '#FCDDC8', text: '#7C2D12' },
  潜力普通客户: { bg: '#F9F1C6', text: '#713F12' },
  沉睡普通客户: { bg: '#BAC2F0', text: '#312E81' },
  流失预警普通客户: { bg: '#E8C9CE', text: '#881337' },
  重要价值: { bg: '#C8E1F5', text: '#1E3A8A' },
  重要保持: { bg: '#E2C9F3', text: '#4C1D95' },
  重要发展: { bg: '#FCCDDF', text: '#831843' },
  重要挽留: { bg: '#D7EFE5', text: '#064E3B' },
  一般价值: { bg: '#FCDDC8', text: '#7C2D12' },
  一般保持: { bg: '#F9F1C6', text: '#713F12' },
  一般发展: { bg: '#BAC2F0', text: '#312E81' },
  一般挽留: { bg: '#E8C9CE', text: '#881337' },
};
const defaultBadge = { bg: '#E2C9F3', text: '#4C1D95' };

/** 从任意形态的单元格抽取 {文本, 胶囊色, 方向箭头} */
function extractCell(raw: unknown): { text: string; color?: string; direction?: string; isObject: boolean } {
  if (raw == null) return { text: '-', isObject: false };
  // 结构化单元格 {value, color, direction, ...}
  if (typeof raw === 'object') {
    const c = raw as RenderedCell;
    const v = c.value;
    let text: string;
    if (v == null) text = '-';
    else if (typeof v === 'number') text = Number.isInteger(v) ? v.toLocaleString() : v.toFixed(2);
    else text = String(v);
    return { text, color: c.color, direction: c.direction, isObject: true };
  }
  // 纯值
  let text: string;
  if (typeof raw === 'number') text = Number.isInteger(raw) ? raw.toLocaleString() : raw.toFixed(2);
  else text = String(raw);
  return { text, isObject: false };
}

/** 方向箭头符号 */
function dirArrow(direction?: string): string {
  if (!direction) return '';
  if (direction === 'up' || direction === '↑' || direction === '+' || direction === 'increase') return '↑';
  if (direction === 'down' || direction === '↓' || direction === '-' || direction === 'decrease') return '↓';
  if (direction === 'flat' || direction === '→') return '→';
  return '';
}

export const EtherealTable: React.FC<Props> = ({
  chartNode,
  columns: columnsProp,
  showIndex = false,
  title,
  cardBgUrl = CARD_BG_URL,
}) => {
  const node = chartNode || {};
  const titleText = title || node.title || '数据汇总表';
  const columns = columnsProp || node.columns || [];
  const rawRows: unknown[] = node.rows || [];

  // 判断 rows 形态：二维数组（每个元素是数组）→ RenderedCell[][] 形态；否则 dict 行数组
  const is2D = rawRows.length > 0 && rawRows.every((r) => Array.isArray(r));

  // 取某一行某一列的原始单元格
  const rawAt = (row: unknown, ci: number, colName: string): unknown => {
    if (is2D) {
      const arr = (row as unknown[]) || [];
      return arr[ci];
    }
    const obj = (row as Record<string, unknown>) || {};
    return obj[colName] ?? obj[ci];
  };

  // 渲染用列（是否带序号列）
  const renderColumns = showIndex ? ['#', ...columns] : columns;

  return (
    <div
      style={{
        position: 'relative',
        background: `url('${cardBgUrl}') center / cover fixed`,
        borderRadius: 24,
        boxShadow: '0 20px 40px -10px rgba(99,102,241,0.05), 0 0 0 1px rgba(255,255,255,0.8)',
        padding: 40,
        boxSizing: 'border-box',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        gap: 30,
        width: '100%',
      }}
    >
      <style>{`
        .ethereal-table-wrap { width: 100%; border-collapse: collapse; text-align: center; }
        .ethereal-table-wrap th { padding: 0 15px 20px 15px; font-weight: 600; color: #1E293B; font-size: 15px; border-bottom: 2px solid rgba(0,0,0,0.08); }
        .ethereal-table-wrap th.segment-header { text-align: left; }
        .ethereal-table-wrap td { padding: 20px 15px; color: #475569; font-size: 14px; font-weight: 600; border-bottom: 1px dashed rgba(0,0,0,0.06); }
        .ethereal-table-wrap td.segment-col { text-align: left; }
        .ethereal-table-wrap tr:last-child td { border-bottom: none; }
        .ethereal-table-wrap td:not(:first-child):not(:last-child), .ethereal-table-wrap th:not(:first-child):not(:last-child) { border-right: 1px dashed rgba(0,0,0,0.04); }
        .badge-pill { display: inline-block; padding: 6px 16px; border-radius: 20px; font-size: 13px; font-weight: 600; box-shadow: 0 2px 6px rgba(0,0,0,0.02); }
        .dir-arrow { font-size: 13px; margin-left: 4px; font-weight: 700; }
        .dir-up { color: #16A34A; }
        .dir-down { color: #DC2626; }
        .dir-flat { color: #94A3B8; }
      `}</style>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ fontSize: 24, fontWeight: 600, color: '#1E293B', letterSpacing: '0.5px' }}>{titleText}</div>
      </div>
      <table className="ethereal-table-wrap">
        <thead>
          <tr>
            {renderColumns.map((col, index) => (
              <th key={index} className={index === 0 ? 'segment-header' : ''}>{col}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rawRows.map((row, ri) => {
            // 序号列偏移：若 showIndex，真实数据列从 ci=1 开始
            const dataStart = showIndex ? 1 : 0;
            return (
              <tr key={ri}>
                {renderColumns.map((colName, ci) => {
                  // 序号列
                  if (showIndex && ci === 0) {
                    return <td key={ci} style={{ color: '#94A3B8' }}>{ri + 1}</td>;
                  }
                  const dataCi = ci - dataStart;
                  const rawCell = rawAt(row, dataCi, columns[dataCi] || '');
                  const cell = extractCell(rawCell);

                  // 第1个真实数据列 → 彩色胶囊
                  if (dataCi === 0) {
                    const textVal = cell.text;
                    const colors = cell.color
                      ? { bg: cell.color, text: '#1E293B' }
                      : (colorPalette[textVal] || defaultBadge);
                    return (
                      <td key={ci} className="segment-col">
                        <span className="badge-pill" style={{ backgroundColor: colors.bg, color: colors.text }}>{textVal}</span>
                      </td>
                    );
                  }
                  // 其余列：文本 + 方向箭头
                  const arrow = dirArrow(cell.direction);
                  const arrowClass = cell.direction === 'up' || cell.direction === '↑' || cell.direction === '+'
                    ? 'dir-up'
                    : cell.direction === 'down' || cell.direction === '↓' || cell.direction === '-'
                      ? 'dir-down'
                      : cell.direction
                        ? 'dir-flat'
                        : '';
                  return (
                    <td key={ci}>
                      {cell.text}
                      {arrow && <span className={`dir-arrow ${arrowClass}`}>{arrow}</span>}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

export default EtherealTable;
