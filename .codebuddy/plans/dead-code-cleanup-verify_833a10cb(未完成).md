---
name: dead-code-cleanup-verify
overview: 复核并清理已识别死代码：删除真正的死文件（DashboardV2Page.tsx、3 个 .bak、ai_agent/tools.py），部分清理 CardGrid.tsx（仅保留类型）与 helpers.py（仅删 infer_datetime_columns 单函数），并纠正上一轮误判的 chart_renderer.py（实为活代码，保留）。
todos:
  - id: delete-frontend-dead
    content: 删除 DashboardV2Page.tsx 与 3 个 .bak 备份文件
    status: pending
  - id: delete-tools-py
    content: 删除 src/ai_agent/tools.py 空壳模块
    status: pending
  - id: strip-cardgrid
    content: 清理 CardGrid.tsx 死组件代码，仅保留 CardItem/CardMeta 类型
    status: pending
  - id: remove-dead-fn
    content: 删除 utils/helpers.py 中 infer_datetime_columns 死函数
    status: pending
  - id: verify-cleanup
    content: 运行 tsc 与后端导入校验，确认无残留引用
    status: pending
    dependencies:
      - delete-frontend-dead
      - delete-tools-py
      - strip-cardgrid
      - remove-dead-fn
---

## 用户需求

对上一轮「明确死代码（建议删除）」清单逐条复核，确认是否真的可以删除，并执行安全清理（不主动 commit/push，改动后需重新读取验证并完整验证）。

## 复核结论（逐项裁定）

- **可整删**：`frontend/src/pages/DashboardV2Page.tsx`（仅文件内自引用，未接入 App.tsx 路由，无动态 import）、`frontend/src/pages/DashboardPage.tsx.bak` 与 `frontend/src/components/BigScreen/MedicalDashboard.tsx.bak`、`.bak_v2`（纯备份）、`src/ai_agent/tools.py`（空壳 `pass`，全仓 0 引用，`__init__.py` 未导入）。
- **仅清组件、保留类型**：`frontend/src/components/CardGrid.tsx`。其 `CardItem`/`CardMeta` 接口被 `DashboardPage.tsx`、`MedicalDashboard.tsx`、`exportEChartsDashboard.ts` 共 3 处 `import type` 使用（活依赖）；默认导出 `CardGrid` 及其内部 `KPICard`/`ChartCard`/`TableCard`/`InsightCard`/`WarningCard`/`FallbackCard`/`CardRenderer`/`getColumns`/`calcSpan`/`formatCellValue`/`getChartHeight` 全仓无 JSX 渲染引用，均为死代码。
- **仅删单函数**：`utils/helpers.py::infer_datetime_columns`（全仓仅定义、无调用方）。同模块 `get_datetime_columns`/`get_numeric_columns`/`get_categorical_columns`/`detect_outliers_*` 均被 `data.py`/`stats.py`/`data_cleaner.py` 使用，模块整体保留。
- **不可删（上一轮误判，已纠正）**：`src/chart_renderer.py` 被 `analysis.py` 实际引用并调用（`_RENDERER.render_all(...)` 生成图表），属 analysis 路由活代码，不在本次清理范围。

## 清理范围（核心特性）

1. 删除 1 个废弃页面 + 3 个备份文件 + 1 个空壳模块；
2. 将 `CardGrid.tsx` 瘦身为由类型定义组成的纯模块（消除约 280 行死组件代码）；
3. 删除 `helpers.py` 中单条死函数；
4. 保留 `chart_renderer.py` 及模块其余活代码不变。

## Tech Stack

- 前端：React + TypeScript（Vite 工程，tsc 类型校验）
- 后端：Python（FastAPI，仅删文件/删函数，无逻辑改动）

## Implementation Approach

采用「最小爆破半径」的清理策略：核对每个目标的运行时引用（含 `importlib`/字符串动态 import 等隐式引用）后，仅移除确无引用者，对「文件有用但内含死代码」的目标只删局部、保留活部分。

- **CardGrid.tsx**：因 3 处引用均为 `import type { CardItem, CardMeta } from '../components/CardGrid'`（扩展名省略、仅取类型），故**仅删除文件内全部组件实现代码，保留两个接口定义**，import 语句无需任何改动，爆破半径为零。文件不再含 JSX，可顺手将 `CardGrid.tsx` 重命名为 `CardGrid.ts`（可选，非必需）。
- **helpers.py**：仅删除 `infer_datetime_columns`（约 :54-66）单函数，保持其前后函数完整，不影响 `get_datetime_columns` 等活函数。
- **整删文件**：`DashboardV2Page.tsx`、3 个 `.bak`、`ai_agent/tools.py` 无任何引用，直接删除。
- **chart_renderer.py**：经确认被 `analysis.py` 调用，本次不改动，纠正上一轮「冗余可删」的误判。

## Implementation Notes

- 删除/裁剪后必须 `npx tsc --noEmit` 验证，确认无「找不到模块/未解析导入」错误（重点：`DashboardPage.tsx`、`MedicalDashboard.tsx`、`exportEChartsDashboard.ts` 的 `CardItem/CardMeta` 导入在 CardGrid.tsx 瘦身后仍可解析）。
- 后端侧：确认 `analysis` 路由 `from src.chart_renderer import ChartRenderer` 仍成立、启动无 `ImportError`；`grep infer_datetime_columns` 与 `grep ai_agent.tools` 全仓应无残留。
- 不动 `exportEChartsDashboard.ts` 的导出 HTML 逻辑（用户曾明确拒绝改动其主题），本次仅调整其类型 import 的来源模块内部实现，import 路径不变。
- 严禁将 `chart_renderer.py` 列入删除范围。

## Architecture Design

本次为纯删除型清理，不改变任何架构、调用链与数据流。前端页面路由（`App.tsx` 的 `/upload|/clean|/analysis|/dashboard`）与后端路由注册（`main.py` 的 11 个 router）均保持不变。

## Directory Structure

```
frontend/src/
├── pages/
│   ├── DashboardV2Page.tsx          # [DELETE] 废弃页面，未接入路由
│   └── DashboardPage.tsx.bak        # [DELETE] 备份文件
├── components/
│   ├── CardGrid.tsx                 # [MODIFY] 删除全部组件实现，仅保留 CardItem/CardMeta 接口（import 站点无需改动）；可顺手重命名为 CardGrid.ts
│   └── BigScreen/
│       ├── MedicalDashboard.tsx.bak    # [DELETE] 备份文件
│       └── MedicalDashboard.tsx.bak_v2 # [DELETE] 备份文件
src/
├── ai_agent/
│   └── tools.py                     # [DELETE] 空壳 pass 占位，全仓 0 引用
└── chart_renderer.py                # [KEEP] 活代码（analysis.py 调用），不改动
utils/
└── helpers.py                       # [MODIFY] 删除 infer_datetime_columns 函数(:54-66)，保留其余活函数
```