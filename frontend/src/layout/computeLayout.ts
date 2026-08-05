/**
 * 智能排版引擎（纯函数，不依赖 React）
 *
 * 输入：排版项（SmartLayoutItem[]，含 attention_weight + chart_type + title）
 * 输出：CSS Grid 布局描述（gridTemplateAreas + rowHeights + assignments）
 *
 * 排版风格：4 行混合列宽（参考用户理想大屏）
 *   Row 1: 4-4-4      3 个等宽 KPI 卡片（110px 高）
 *   Row 2: 3-6-3      横条图 + 中央大环形图 + 漏斗图
 *   Row 3: 6-6        折线图 + 多系列面积图
 *   Row 4: 6-3-3      表格 + 折线图 + 环形图
 *   Row 5+: full / 6-6 兜底（多余图表按 chart_type 自适应）
 *
 * LLM 决定「选谁」（attention_weight），本引擎决定「放哪 / 多大」。
 */

export interface LayoutInputItem {
  slot: string;
  title: string;
  chart_type: string;
  attention_weight: number;
  /** 是否强制全宽（外部覆盖） */
  forceFull?: boolean;
  // ★ 阶段B：LLM 直接输出的形状-槽位绑定（有则优先按蓝图落位，无则走启发式兜底）
  shape?: string | null;
  slot_id?: string | null;
}

export type SizeClass = 'kpi' | 'wide' | 'full';

export interface LayoutAssignment {
  slot: string;
  title: string;
  chartType: string;
  sizeClass: SizeClass;
  area: string;
  rowIndex: number;
  colIndex: number;
}

export interface ComputeLayoutResult {
  gridTemplateAreas: string;
  rowHeights: string;
  assignments: LayoutAssignment[];
  rowCount: number;
}

const COLS = 12;

// ============================================================
// 固定空间蓝图（与后端 llm_layout_engine.BLUEPRINT 对齐）
// LLM 输出的 slot_id 必须命中这里；前端按蓝图纯函数落位。
// ============================================================
export type ShapeTag = 'kpi' | 'hero_square' | 'side_strip' | 'hero_wide' | 'side_square' | 'full_width';

export interface BlueprintSlot {
  slot_id: string;
  shape: ShapeTag;
  col_span: number;
  rowIndex: number;      // 1-based
  colStart: number;      // 1-based
}

export const BLUEPRINT: { columns: number; slots: BlueprintSlot[]; overflow: BlueprintSlot[] } = {
  columns: 12,
  slots: [
    { slot_id: 'kpi_1',            shape: 'kpi',          col_span: 4, rowIndex: 1, colStart: 1 },
    { slot_id: 'kpi_2',            shape: 'kpi',          col_span: 4, rowIndex: 1, colStart: 5 },
    { slot_id: 'kpi_3',            shape: 'kpi',          col_span: 4, rowIndex: 1, colStart: 9 },
    { slot_id: 'side_strip_left',  shape: 'side_strip',   col_span: 3, rowIndex: 2, colStart: 1 },
    { slot_id: 'hero_square',      shape: 'hero_square',  col_span: 6, rowIndex: 2, colStart: 4 },
    { slot_id: 'side_strip_right', shape: 'side_strip',   col_span: 3, rowIndex: 2, colStart: 10 },
    { slot_id: 'hero_wide_left',   shape: 'hero_wide',    col_span: 6, rowIndex: 3, colStart: 1 },
    { slot_id: 'side_square',      shape: 'side_square',  col_span: 3, rowIndex: 3, colStart: 7 },
    { slot_id: 'side_tail',        shape: 'side_square',  col_span: 3, rowIndex: 3, colStart: 10 },
    { slot_id: 'full_wide',        shape: 'full_width',   col_span: 12, rowIndex: 4, colStart: 1 },
  ],
  overflow: [
    { slot_id: 'extra_wide_1', shape: 'hero_wide', col_span: 6, rowIndex: 5, colStart: 1 },
    { slot_id: 'extra_wide_2', shape: 'hero_wide', col_span: 6, rowIndex: 5, colStart: 7 },
  ],
};

// shape → 落位尺寸档
const SHAPE_SIZE: Record<ShapeTag, SizeClass> = {
  kpi: 'kpi',
  hero_square: 'wide',
  side_strip: 'wide',
  hero_wide: 'wide',
  side_square: 'wide',
  full_width: 'full',
};

// 行高（与蓝图各 row 对应），full 行更高以容纳排行/明细大图
const ROW_HEIGHTS: Record<number, string> = {
  1: 'auto',
  2: '2.2fr',
  3: '2fr',
  4: '2.8fr',   // ★ full 行（排行/明细）给更高高度，修复「排行图只占半屏」
  5: '2fr',
};

// 2x2 KPI 组：把 4 个 kpi_grid_* 横排到 Row 1（4 等宽 KPI 卡）。
//   注：CSS Grid 无法在同一 area 内做 2x2 子网格，最简实现是 4 个独立 KPI 等宽横排。
//   若后续要做严格 2x2 视觉，可在 React 层用父容器 + display:grid 子网格改造。
const KPI_GRID_LAYOUT = {
  slot_ids: ['kpi_grid_1', 'kpi_grid_2', 'kpi_grid_3', 'kpi_grid_4'],
  rowIndex: 1,                       // 顶部 KPI 行
  colStart: 1,
  colSpan: 3,                        // 每个 KPI 占 3 列；4 × 3 = 12 列
};

/** 行模板：[每槽宽度]（块数 = 该行可放几张图） */
const ROW_TEMPLATES: { row: number; template: number[]; height: string; sizeClass: SizeClass }[] = [
  { row: 1, template: [4, 4, 4], height: '0.8fr', sizeClass: 'kpi' },
  { row: 2, template: [3, 6, 3], height: '2.2fr', sizeClass: 'wide' },
  { row: 3, template: [6, 6],    height: '2fr',   sizeClass: 'wide' },
  { row: 4, template: [12],      height: '2.6fr', sizeClass: 'full' },
  { row: 5, template: [6, 6],    height: '2fr',   sizeClass: 'wide' },
];

/** 需要宽度放中央 6col 或全宽（折线图/区域图/同期群/漏斗/雷达）—— 不能塞进 3col 侧边 */
const WIDE_TYPES = new Set(['line', 'area', 'area_chart', 'cohort_heatmap', 'heatmap', 'funnel', 'funnel_chart', 'radar', 'dual_axis', 'dual']);
/** Hero 类型（视觉冲击大 → 放 Row 2 中央 6col 槽） */
const HERO_TYPES = new Set(['pie', 'ring', 'donut']);
/** 边角类型（适合紧凑 3col 侧边槽）—— 横条/柱状/排行图 */
const SIDE_TYPES = new Set(['hbar', 'hbar_family', 'horizontal_bar', 'bar', 'v_bar', 'ranking']);
/** KPI/Metric 类型（→ 放 Row 1 三个 4col 等宽槽） */
const KPI_TYPES = new Set(['metric', 'kpi', 'card', 'metric_card']);

/**
 * 判断给定 chart_type 是否属于 Hero（视觉冲击型）
 */
function isHero(t: string): boolean {
  const tl = (t || '').toLowerCase();
  return HERO_TYPES.has(tl) || WIDE_TYPES.has(tl);
}
function isWide(t: string): boolean {
  return WIDE_TYPES.has((t || '').toLowerCase());
}
function isSide(t: string): boolean {
  return SIDE_TYPES.has((t || '').toLowerCase());
}
function isKpi(t: string): boolean {
  return KPI_TYPES.has((t || '').toLowerCase());
}
/** 排行榜 → 进 side_strip（环形图两侧），不再强制全宽 */

const COL_AREA = (row: number, colStart: number, width: number) =>
  `r${row}c${colStart}s${width}`;

function isFullWidth(chartType: string): boolean {
  const t = (chartType || '').toLowerCase();
  // 排行榜（ranking）已纳入 side_strip，不再强制全宽
  return t === 'table' || t === 'cohort_heatmap' || t === 'heatmap';
}

/**
 * 给图表分配位置 + 尺寸。
 *
 * 双模式：
 *   ★ 模式A（蓝图驱动，优先）：若 item.slot_id 命中 BLUEPRINT 槽位，
 *     则按蓝图纯函数落位（shape 决定尺寸档），这是 LLM 通过 few-shot 学会的排版。
 *   ★ 模式B（启发式兜底）：item 无 slot_id（旧版 LLM / 兜底），
 *     按 attention_weight 排序 + 形状谓词自动落位（保留原逻辑）。
 */
export function computeLayout(items: LayoutInputItem[]): ComputeLayoutResult {
  if (!items || items.length === 0) {
    const empty = COL_AREA(0, 1, COLS);
    return {
      gridTemplateAreas: `"${Array(COLS).fill(empty).join(' ')}"`,
      rowHeights: '1fr',
      assignments: [],
      rowCount: 1,
    };
  }

  // ★ 优先判断是否走蓝图驱动：任意 slot_id 命中蓝图主槽位 OR KPI 网格槽位（kpi_grid_*）即走 A
  const blueprintItems = items.filter(
    (it) =>
      it.slot_id &&
      (BLUEPRINT.slots.some((s) => s.slot_id === it.slot_id) ||
        KPI_GRID_LAYOUT.slot_ids.includes(it.slot_id as string)),
  );

  if (blueprintItems.length > 0) {
    return computeLayoutBlueprint(items, blueprintItems);
  }
  // 否则走旧版启发式兜底
  return computeLayoutHeuristic(items);
}

// ============================================================
// 模式A：蓝图驱动落位（LLM 输出 slot_id + shape）
// ============================================================
function computeLayoutBlueprint(
  allItems: LayoutInputItem[],
  blueprintItems: LayoutInputItem[],
): ComputeLayoutResult {
  const assignments: LayoutAssignment[] = [];
  const rows: Record<number, string[]> = {};
  const heights: Record<number, string> = {};

  // ★ KPI 组（kpi_grid_1~4）：4 个 KPI 各占一个独立 area，横排在 Row 1
  const kpiGridItems = blueprintItems.filter(
    (it) => KPI_GRID_LAYOUT.slot_ids.includes(it.slot_id as string),
  );
  const usedSlotIds = new Set<string>();

  for (let i = 0; i < kpiGridItems.length && i < 4; i++) {
    const it = kpiGridItems[i];
    usedSlotIds.add(it.slot_id as string);
    const r = KPI_GRID_LAYOUT.rowIndex;
    const c = 1 + i * KPI_GRID_LAYOUT.colSpan;   // 1, 4, 7, 10
    const w = KPI_GRID_LAYOUT.colSpan;
    const area = COL_AREA(r, c, w);
    if (!rows[r]) rows[r] = Array(COLS).fill('.');
    for (let j = 0; j < w; j++) rows[r][c + j - 1] = area;
    heights[r] = ROW_HEIGHTS[r] || 'auto';
    assignments.push({
      slot: it.slot,
      title: it.title,
      chartType: it.chart_type,
      sizeClass: SHAPE_SIZE['kpi'],
      area,
      rowIndex: r,
      colIndex: c,
    });
  }

  // 蓝图主槽位（排除已并入 KPI 组的）
  for (const it of blueprintItems) {
    if (usedSlotIds.has(it.slot_id as string)) continue;
    const bp = BLUEPRINT.slots.find((s) => s.slot_id === it.slot_id);
    if (!bp) continue;
    if (usedSlotIds.has(bp.slot_id)) continue;
    usedSlotIds.add(bp.slot_id);
    const area = COL_AREA(bp.rowIndex, bp.colStart, bp.col_span);
    assignments.push({
      slot: it.slot,
      title: it.title,
      chartType: it.chart_type,
      sizeClass: SHAPE_SIZE[bp.shape] ?? 'wide',
      area,
      rowIndex: bp.rowIndex,
      colIndex: bp.colStart,
    });
    if (!rows[bp.rowIndex]) rows[bp.rowIndex] = Array(COLS).fill('.');
    for (let j = 0; j < bp.col_span; j++) rows[bp.rowIndex][bp.colStart + j - 1] = area;
    heights[bp.rowIndex] = ROW_HEIGHTS[bp.rowIndex] || '2fr';
  }

  // 多余候选（未命中蓝图槽位）依次填 overflow 行
  const overflowUsed = new Set<string>();
  const overflowCandidates = allItems.filter(
    (it) => !blueprintItems.includes(it) || !BLUEPRINT.slots.some((s) => s.slot_id === it.slot_id),
  ).filter((it) => it.slot_id && !BLUEPRINT.slots.some((s) => s.slot_id === it.slot_id));
  let oi = 0;
  for (const it of overflowCandidates) {
    const bp = BLUEPRINT.overflow[oi % BLUEPRINT.overflow.length];
    const oKey = `${bp.rowIndex}:${bp.slot_id}`;
    if (overflowUsed.has(oKey)) {
      oi++;
      continue;
    }
    overflowUsed.add(oKey);
    const area = COL_AREA(bp.rowIndex, bp.colStart, bp.col_span);
    assignments.push({
      slot: it.slot,
      title: it.title,
      chartType: it.chart_type,
      sizeClass: SHAPE_SIZE[bp.shape] ?? 'wide',
      area,
      rowIndex: bp.rowIndex,
      colIndex: bp.colStart,
    });
    if (!rows[bp.rowIndex]) rows[bp.rowIndex] = Array(COLS).fill('.');
    for (let j = 0; j < bp.col_span; j++) rows[bp.rowIndex][bp.colStart + j - 1] = area;
    heights[bp.rowIndex] = ROW_HEIGHTS[bp.rowIndex] || '2fr';
    oi++;
    if (oi >= BLUEPRINT.overflow.length) oi = 0;
  }

  return assembleGrid(assignments, rows, heights);
}

// ============================================================
// 模式B：启发式兜底（无 slot_id 时，保留原 attention_weight 分档逻辑）
// ============================================================
function computeLayoutHeuristic(items: LayoutInputItem[]): ComputeLayoutResult {
  const sorted = [...items].sort(
    (a, b) => (b.attention_weight ?? 0) - (a.attention_weight ?? 0),
  );

  const assignments: LayoutAssignment[] = [];
  const rows: Record<number, string[]> = {};
  const heights: Record<number, string> = {};

  // ─── 阶段 1：分离「表格类强制全宽」与「普通」 ───
  //   ★ 排行图(ranking)也强制全宽：否则会落入 6col 普通池，呈现「只占半屏」(用户反馈)
  const forcedFull: LayoutInputItem[] = [];
  const kpiQueue: LayoutInputItem[] = [];
  const normal: LayoutInputItem[] = [];
  for (const it of sorted) {
    if (isKpi(it.chart_type)) {
      kpiQueue.push(it);
    } else if ((it.forceFull || isFullWidth(it.chart_type))) {
      forcedFull.push(it);
    } else {
      normal.push(it);
    }
  }

  // ─── 阶段 2.5：先填 Row 4 表格全宽行（如果有 table） ───
  if (normal.some((it) => isFullWidth(it.chart_type))) {
    const tableIdx = normal.findIndex((it) => isFullWidth(it.chart_type));
    if (tableIdx !== -1) {
      const item = normal[tableIdx];
      const area = COL_AREA(4, 1, COLS);
      const rowAreaNames: string[] = Array(COLS).fill(area);
      assignments.push({
        slot: item.slot, title: item.title, chartType: item.chart_type,
        sizeClass: 'full', area, rowIndex: 4, colIndex: 1,
      });
      rows[4] = rowAreaNames;
      heights[4] = '2.8fr';
      normal.splice(tableIdx, 1);
    }
  }

  // ─── 阶段 2：按行模板填入普通图表（KPI 行 + Hero 行有专门槽位逻辑） ───
  function takeBy(pred: (it: LayoutInputItem) => boolean): LayoutInputItem | undefined {
    const idx = normal.findIndex(pred);
    if (idx === -1) return undefined;
    const [item] = normal.splice(idx, 1);
    return item;
  }
  function takeNext(): LayoutInputItem | undefined {
    return normal.length > 0 ? normal.shift() : undefined;
  }

  for (const tpl of ROW_TEMPLATES) {
    if (tpl.row === 4) continue;
    if (normal.length === 0) break;

    const rowAreaNames: string[] = Array(COLS).fill('.');
    let colCursor = 1;

    if (tpl.row === 1) {
      for (let i = 0; i < tpl.template.length; i++) {
        const width = tpl.template[i];
        const area = COL_AREA(tpl.row, colCursor, width);
        for (let j = 0; j < width; j++) rowAreaNames[colCursor + j - 1] = area;
        const item = kpiQueue.shift();
        if (item) {
          assignments.push({ slot: item.slot, title: item.title, chartType: item.chart_type, sizeClass: tpl.sizeClass, area, rowIndex: tpl.row, colIndex: colCursor });
        }
        colCursor += width;
      }
      rows[tpl.row] = rowAreaNames;
      heights[tpl.row] = tpl.height;
      continue;
    }

    if (tpl.row === 2) {
      const [w0, w1, w2] = tpl.template;
      const a0 = COL_AREA(tpl.row, 1, w0);
      const a1 = COL_AREA(tpl.row, 1 + w0, w1);
      const a2 = COL_AREA(tpl.row, 1 + w0 + w1, w2);
      for (let j = 0; j < w0; j++) rowAreaNames[0 + j] = a0;
      for (let j = 0; j < w1; j++) rowAreaNames[w0 + j] = a1;
      for (let j = 0; j < w2; j++) rowAreaNames[w0 + w1 + j] = a2;

      const centerItem =
        takeBy((it) => isHero(it.chart_type) || isWide(it.chart_type)) ||
        takeNext();
      if (centerItem) {
        assignments.push({ slot: centerItem.slot, title: centerItem.title, chartType: centerItem.chart_type, sizeClass: tpl.sizeClass, area: a1, rowIndex: tpl.row, colIndex: 1 + w0 });
      }
      // ★ 蓝图要求：环形图两侧优先放排行图(ranking)，其次再退化到横条/柱状
      const leftItem = takeBy((it) => it.chart_type === 'ranking') || takeBy((it) => isSide(it.chart_type));
      if (leftItem) {
        assignments.push({ slot: leftItem.slot, title: leftItem.title, chartType: leftItem.chart_type, sizeClass: tpl.sizeClass, area: a0, rowIndex: tpl.row, colIndex: 1 });
      }
      const rightItem = takeBy((it) => it.chart_type === 'ranking') || takeBy((it) => isSide(it.chart_type));
      if (rightItem) {
        assignments.push({ slot: rightItem.slot, title: rightItem.title, chartType: rightItem.chart_type, sizeClass: tpl.sizeClass, area: a2, rowIndex: tpl.row, colIndex: 1 + w0 + w1 });
      }
      rows[tpl.row] = rowAreaNames;
      heights[tpl.row] = tpl.height;
      continue;
    }

    for (let i = 0; i < tpl.template.length; i++) {
      const width = tpl.template[i];
      const area = COL_AREA(tpl.row, colCursor, width);
      for (let j = 0; j < width; j++) rowAreaNames[colCursor + j - 1] = area;
      const item = takeNext();
      if (item) {
        assignments.push({ slot: item.slot, title: item.title, chartType: item.chart_type, sizeClass: tpl.sizeClass, area, rowIndex: tpl.row, colIndex: colCursor });
      }
      colCursor += width;
    }
    rows[tpl.row] = rowAreaNames;
    heights[tpl.row] = tpl.height;
  }

  // ─── 阶段 3：兜底处理剩余普通图表 ───
  let extraRow = Math.max(...ROW_TEMPLATES.map(r => r.row), 0) + 1;
  while (normal.length > 0) {
    const remaining = normal.length;
    const rowAreaNames: string[] = Array(COLS).fill('.');
    if (remaining >= 2) {
      const item1 = takeNext()!;
      const a1 = COL_AREA(extraRow, 1, 6);
      for (let j = 0; j < 6; j++) rowAreaNames[j] = a1;
      assignments.push({
        slot: item1.slot, title: item1.title, chartType: item1.chart_type,
        sizeClass: 'wide', area: a1, rowIndex: extraRow, colIndex: 1,
      });
      const item2 = takeNext();
      if (item2) {
        const a2 = COL_AREA(extraRow, 7, 6);
        for (let j = 6; j < 12; j++) rowAreaNames[j] = a2;
        assignments.push({
          slot: item2.slot, title: item2.title, chartType: item2.chart_type,
          sizeClass: 'wide', area: a2, rowIndex: extraRow, colIndex: 7,
        });
      }
      rows[extraRow] = rowAreaNames;
      heights[extraRow] = '1.8fr';
      extraRow++;
    } else {
      const item = takeNext()!;
      const a = COL_AREA(extraRow, 1, COLS);
      for (let j = 0; j < COLS; j++) rowAreaNames[j] = a;
      assignments.push({
        slot: item.slot, title: item.title, chartType: item.chart_type,
        sizeClass: 'full', area: a, rowIndex: extraRow, colIndex: 1,
      });
      rows[extraRow] = rowAreaNames;
      heights[extraRow] = '1.8fr';
      extraRow++;
    }
  }

  // ─── 阶段 4：强制全宽图放最底部，独占整行 ───
  for (const item of forcedFull) {
    const rowAreaNames: string[] = Array(COLS).fill('.');
    const a = COL_AREA(extraRow, 1, COLS);
    for (let j = 0; j < COLS; j++) rowAreaNames[j] = a;
    assignments.push({
      slot: item.slot, title: item.title, chartType: item.chart_type,
      sizeClass: 'full', area: a, rowIndex: extraRow, colIndex: 1,
    });
    rows[extraRow] = rowAreaNames;
    heights[extraRow] = isFullRank(item.chart_type) ? '2.8fr' : '2.4fr';
    extraRow++;
  }

  return assembleGrid(assignments, rows, heights);
}

// ============================================================
// 公共：组装 grid-template-areas / rowHeights
// ============================================================
function assembleGrid(
  assignments: LayoutAssignment[],
  rows: Record<number, string[]>,
  heights: Record<number, string>,
): ComputeLayoutResult {
  const sortedRowKeys = Object.keys(rows).map(Number).sort((a, b) => a - b);
  const filledAreas = new Set(assignments.map((a) => a.area));
  const gridTemplateAreas = sortedRowKeys
    .map(k => {
      const rowCells = rows[k];
      const hasAnyAssignment = rowCells.some((a) => filledAreas.has(a));
      const cells = hasAnyAssignment ? rowCells : Array(COLS).fill('.');
      return `"${cells.join(' ')}"`;
    })
    .join('\n');

  const rowHeights = sortedRowKeys.map(k => {
    const rowCells = rows[k];
    const hasAnyAssignment = rowCells.some((a) => filledAreas.has(a));
    if (!hasAnyAssignment) return '0';
    const h = heights[k] || '1fr';
    if (k === 1) return 'auto';
    if (h.endsWith('fr')) {
      const n = parseFloat(h);
      if (n <= 1.0) return 'minmax(220px, auto)';
      if (n >= 2.6) return 'minmax(360px, auto)';   // ★ 排行/全宽大图：更高高度修复半屏
      return 'minmax(280px, auto)';
    }
    return h;
  }).join(' ');

  return {
    gridTemplateAreas,
    rowHeights,
    assignments,
    rowCount: sortedRowKeys.length,
  };
}

// ─── 测试导出（仅 dev 使用，方便浏览器 console 单步调试） ───
export const __test__ = {
  ROW_TEMPLATES,
  COLS,
  isFullWidth,
  /**
   * 用 mock 数据跑一遍，模拟你理想大屏的 11 张图。
   * 在浏览器 console 调用：
   *   (await import('./layout/computeLayout')).__test__.demo(11)
   */
  demo: (n = 11) => {
    const types = ['metric', 'metric', 'metric', 'pie', 'ranking', 'funnel', 'bar', 'line', 'table', 'line', 'pie'];
    return computeLayout(
      Array.from({ length: n }, (_, i) => ({
        slot: `mock_${i}`,
        title: `Chart ${i + 1}`,
        chart_type: types[i] || 'bar',
        attention_weight: 1 - i * 0.05,
      })),
    );
  },
};