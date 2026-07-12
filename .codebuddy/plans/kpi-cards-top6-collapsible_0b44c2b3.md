---
name: kpi-cards-top6-collapsible
overview: 在 buildReportHTML 中实现 KPI 卡片"顶部精选 6 个 + 底部折叠更多指标"，并去重排序，解决卡片过多、重复、布局拥挤的问题。
todos:
  - id: add-kpi-helpers
    content: 在 parseNumVal 后面新增 _deduplicateByTitle、_scoreKPI、_splitKPIs 三个工具函数
    status: completed
  - id: refactor-kpi-html
    content: 重写 buildReportHTML 中 kpiHTML 生成逻辑：去重+排序分 top6/rest，top 正常渲染，rest 包裹在 details 折叠面板中
    status: completed
    dependencies:
      - add-kpi-helpers
  - id: add-collapse-css
    content: 在.metric-danger 后新增 .kpi-more / .kpi-more-summary 深空主题 CSS，含打印回退样式
    status: completed
---

## 用户需求

AI 分析报告（report 模板）中 KPI 指标卡片过多（当前 18 张全量平铺），5 列 flex 网格在卡片数不是 5 倍数时产生残行，且存在重复卡片。用户选择方案 A：顶部只展示最重要的 6 个 KPI，其余收进可展开/折叠的"更多指标"面板。

## 核心功能

- **KPI 去重**：同一 title 的指标只保留首次出现的那条，消除重复卡片
- **优先级排序**：按 color 质量分（excellent > good > warning > danger > 无）和关键业务词（增长率/集中度/复购率）加权排序，确保重要指标优先展示
- **顶部精选 6 个 + 折叠面板**：最重要的 6 个 KPI 在顶部以卡片网格展示，其余 KPI 收进 `<details>` 折叠面板，点击"更多指标 (N)"展开
- **深空主题适配**：折叠面板的 `<summary>`、边框、背景色与现有深空暗色体系一致
- **打印友好**：打印时折叠面板自动展开、颜色回退浅色
- **边界兜底**：当 KPI 总数 ≤ 6 时不显示折叠面板

## 技术方案

### 修改范围

仅修改一个文件：`d:\数据分析项目\frontend\src\utils\exportEChartsDashboard.ts`

### 实现策略

#### 1. 新增两个工具函数（插入在 `parseNumVal` 之后、`formatAbbreviatedCN` 之前，即 line 1525 附近）

**`_deduplicateByTitle(kpis: KPI[]): KPI[]`**

- 用 `Map<title, KPI>` 去重，保留首次出现的那条

**`_scoreKPI(k: KPI): number`**

- 基础分：excellent=4, good=3, warning=2, danger=1, 无=0
- 关键词加分：title 含"增长率/增速/涨幅/集中度/复购率/利润率/毛利率" → +2
- title 含"总/合计/总计/累计" → +1
- title 含"平均/均值" → +1
- 返回总分

**`_splitKPIs(kpis: KPI[]): { top: KPI[]; rest: KPI[] }`**

- 先去重，再按 score 降序排列，取前 6 为 top，其余为 rest

#### 2. 修改 `buildReportHTML` 中 kpiHTML 生成逻辑（lines 1642-1651）

将原来的全量 `.map()` 替换为：

```typescript
const { top, rest } = _splitKPIs(kpis);
const renderCard = (k: KPI) => `
  <div class="metric-card">
    <div class="metric-abbr ${k.color ? `metric-${k.color}` : ''}">${formatAbbreviatedCN(k.value)}${k.unit || ''}</div>
    <div class="metric-full">${formatFullNumber(k.value)}</div>
    <div class="metric-label">${k.title || "指标"}</div>
  </div>`;

const topHTML = top.length > 0 ? `<div class="metrics-row">${top.map(renderCard).join('\n  ')}</div>` : '';
const restHTML = rest.length > 0 ? `
<details class="kpi-more">
  <summary class="kpi-more-summary">📊 更多指标 (${rest.length})</summary>
  <div class="metrics-row">${rest.map(renderCard).join('\n  ')}</div>
</details>` : '';
const kpiHTML = topHTML + restHTML;
```

#### 3. 新增 CSS（插入在 `.metric-danger` 之后，即 line 1801 之后）

```css
.kpi-more {
  margin: 12px 0;
  border: 1px solid rgba(56,189,248,0.25);
  border-radius: 10px;
  background: rgba(15,23,42,0.6);
  overflow: hidden;
}
.kpi-more-summary {
  padding: 10px 16px;
  color: #94A3B8;
  font-size: 13px;
  cursor: pointer;
  user-select: none;
  list-style: none;
  display: flex;
  align-items: center;
  gap: 6px;
}
.kpi-more-summary::-webkit-details-marker { display: none; }
.kpi-more-summary::before {
  content: "▸";
  display: inline-block;
  transition: transform 0.2s;
  font-size: 10px;
  color: #38BDF8;
}
.kpi-more[open] .kpi-more-summary::before { transform: rotate(90deg); }
.kpi-more .metrics-row { padding: 4px 8px 12px; }
@media print {
  .kpi-more { border-color: #ccc; background: #fff; }
  .kpi-more-summary { color: #333; }
  .kpi-more[open] { page-break-inside: avoid; }
}
```

#### 4. 边界情况处理

- `kpis` 为空数组 → 不渲染任何 KPI HTML
- 去重后 KPI ≤ 6 → 只渲染 top，不渲染 `<details>`
- 去重后 KPI = 0 → 同空数组，跳过

### 性能分析

- 去重：O(n)，Map 遍历一次
- 排序：O(n log n)，n 通常 ≤ 30
- 对渲染无影响（纯字符串拼接，无 DOM 操作）
- `<details>/<summary>` 是浏览器原生组件，零 JS 开销