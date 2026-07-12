---
name: save-to-dashboard-feedback-and-medical-visibility
overview: 修复「智能绘图→手动绘图→保存到仪表盘」按钮无反馈（A，纯前端）以及保存后 medical 数据看板看不到手工图（B，后端只改 api_generate_cards 单路由）。两处改动爆炸半径可控，不波及其它代码。
todos:
  - id: add-save-feedback
    content: 前端 AnalysisPage 渲染 saveMsg 修复按钮无反馈
    status: completed
  - id: merge-v1-charts
    content: 后端 api_generate_cards 合并 V1 手工图到 medical 大屏
    status: completed
  - id: verify-fix
    content: 前端 lint 与后端导入验证并给出手动测试项
    status: completed
    dependencies:
      - add-save-feedback
      - merge-v1-charts
---

## 用户需求

在分析可视化 / 智能绘图（charts 标签）中，手动绘图后点击「保存到仪表盘」按钮无任何反馈，且保存后切换到「数据看板」(medical 模板) 点击「已制作图表」也看不到手工绘制的图表。需修复这两处问题。

## 产品概述

修复「智能绘图 → 手动绘图 → 保存到仪表盘」的完整闭环：点击保存按钮后给出明确的成功/失败提示；保存的手工图表随后能在「数据看板」大屏中正常展示。改动限定在现有功能的反馈与数据加载链路，不引入新界面、不改视觉风格、不改动其它模板（grid/command/report）与 V2 分析包逻辑。

## 核心特性

- A（按钮反馈）：点击「保存到仪表盘」后，页面即时显示「已保存」或「保存失败」文字提示（3 秒后自动消失），解决"按了没反应"的体感问题。
- B（仪表盘可见）：「数据看板」大屏加载已保存图表时，除现有 V2 分析包外，补读 V1 手工收藏图表（saved_charts），经字段归一化后并入卡片生成链路，使手工图出现在大屏。
- 不改动后端保存逻辑、不改动 get_saved_packages_full 共享函数、不改动 CardGenerator、不改动前端 MedicalDashboard 分类与渲染逻辑，控制爆炸半径。

## 技术栈

- 前端：React + TypeScript（沿用 AnalysisPage.tsx 现状，Tailwind 工具类）
- 后端：FastAPI + Python（沿用 dashboard.py / session_manager.py 现状）
- 纯逻辑修复，无新依赖、无新组件、无视觉变更

## 实现思路

采用「前端补渲染 + 后端单路由合并」两处最小改动，复用现有链路，不碰任何共享核心函数。

### A：前端补渲染 saveMsg（纯展示，零风险）

- `AnalysisPage.tsx` 中 `handleSaveChart`（约 L243）保存后已 `setSaveMsg(...)`（成功 L263 / 失败 L266），且 L264 已设 `setTimeout(() => setSaveMsg(''), 3000)` 自动清理。
- 全文件此前从未渲染 `saveMsg` 状态（搜索 0 处），导致保存成功/失败都无反馈。
- 修复：在旧版 charts 分支「保存到仪表盘」按钮（约 L822-825）之后，新增 `{saveMsg && <span>...{saveMsg}</span>}` 渲染。仅展示已有 state，不改任何保存/请求/后端逻辑，不影响 stats/chat 标签与 V2 分析包保存（后者走 alert）。

### B：后端在 api_generate_cards 单路由合并 V1 手工图（可控，低中风险）

- 根因：`api_generate_cards`（dashboard.py 约 L582）只调 `manager.get_saved_packages_full()`，该函数仅遍历 `session.saved_packages`（V2 分析包），完全忽略 `session.saved_charts`（V1 手工图，由 `save_chart` 写入）。medical 大屏的 `cards` 来自此路由，故手工图永远不显示。
- 修复原则（已在排查中确认安全边界）：只改 `api_generate_cards` 这一条路由，不改 `get_saved_packages_full`（否则波及 schema L331 / naming L501 / saved-packages 导出 L316 / api_dashboard_echarts L213），不改 `CardGenerator`，不改前端。
- 具体做法：在该路由读取 V2 包之后、遍历生成 cards 之前，读取 V1 `saved_charts`，将其扁平结构 `{title, option, type, table_data, saved_at}` 归一化为与 V2 `package.charts` 元素兼容的结构（重点把 `type` 映射到 `chart_type`），包装成一个 `analysis_type="manual_chart"` 的伪包，追加进 `packages` 列表，复用现有 `generator.generate(pkg)` 循环。
- V1 非表格图 `type=''`（saveChart 传空串），归一化后 `chart_type=''`，因 `option` 存在，CardGenerator 仍生成 chart card；前端 MedicalDashboard 现有分类逻辑对常规柱/线/饼图走 `else → chart card` 正常渲染。地图类手工图（gl_map）仍由前端 `isMap` 吸收分支吞掉不显示（符合"移除地图区块"要求）。

## 实现细节

- **A 渲染样式**：成功用翠绿 `text-emerald-400`、失败用玫红 `text-rose-400`，字号 `text-xs`，与现有「已保存」语义色一致；置于按钮下方、与图表同列容器内。
- **B 字段映射**：`title→title`、`type→chart_type`、`option→option`、`table_data→table_data`，`x/y` 透传（V1 可能缺，填空串兼容）。
- **B 性能**：`get_saved_charts` 为内存列表遍历，无额外 DB/IO；合并为 O(n) 内存操作，零新增计算开销；当 V1 为空时跳过合并分支，行为与原版完全一致。
- **B 健壮性**：用 `or []` 防御空值；`option or {}` 防御缺 option 的脏数据；不强制与 V2 去重（潜在同名重复属边缘情况，不破坏功能）。
- **向后兼容**：V2 分析包卡片质量/评分/排名逻辑完全不变；command/grid 模板（走 api_dashboard_echarts）维持原行为，本次按用户"数据看板看不到"的口径只修 medical。

## 架构设计

改动不涉及架构层级变化，维持现有数据流：

- 前端：`AnalysisPage`（保存+反馈）→ `api.saveChart` → 后端 `save_chart` 写 `saved_charts`
- 加载：`DashboardPage.loadCards` → `api.generateCards` → 后端 `api_generate_cards`（本次新增 V1 合并）→ `CardGenerator.generate` → `MedicalDashboard cards`

## 目录结构

```
frontend/src/pages/
└── AnalysisPage.tsx          # [MODIFY] A 修复。旧版 charts 分支「保存到仪表盘」按钮后新增 saveMsg 渲染，修复点击无反馈。
backend/routers/
└── dashboard.py              # [MODIFY] B 修复。api_generate_cards 路由内（约 L582 之后）读取 V1 saved_charts，归一化后追加为 manual_chart 伪包，并入卡片生成。
```

## 关键代码结构与改动点

B 的核心改动片段（插入于 `api_generate_cards` 中 `packages = manager.get_saved_packages_full(...)` 之后、`for pkg in packages` 之前）：

```python
# B 修复：把 V1 手工收藏图表并入 medical 大屏卡片生成
v1_charts = manager.get_saved_charts(req.session_id) or []
if v1_charts:
    pkg_charts = [{
        "title": c.get("title", ""),
        "chart_type": c.get("type", "") or "",   # V1 用 type，转成 chart_type
        "option": c.get("option") or {},
        "x": c.get("x", ""),
        "y": c.get("y", ""),
        "table_data": c.get("table_data"),
    } for c in v1_charts]
    packages.append({"analysis_type": "manual_chart", "charts": pkg_charts})
```