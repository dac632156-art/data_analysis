---
name: categorical-palette-10color
overview: "将前端图表数据色板从「蓝→青冷色 ramp」扩展为 10 色有序分类色板（含暖色节奏），银河紫 #8B5CF6 仍专属 AI、由浅靛蓝 #A5B4FC 替补第二数据位；同步更新 Palette.ts（SSOT）、ChartStyle.ts、后端 echart_generator.py 的 GALAXY/BLUE_PALETTE 镜像，并更新相关约束注释。预览页先更新验证、定稿后清理。"
todos:
  - id: add-palette-tokens
    content: 在 Palette.ts 新增 8 个分类色 token（catIndigo/catLightPurple/catSkyBlue/catLake/catGold/catRose/catCoral/catLime），ai 紫保持 AI 专用
    status: completed
  - id: update-chartstyle
    content: 更新 ChartStyle.ts 的 series 与 pie 为 10 色有序数组，移除饼图紫，同步注释
    status: completed
    dependencies:
      - add-palette-tokens
  - id: update-backend-palette
    content: 更新 src/echart_generator.py 的 BLUE_PALETTE 为新 10 色顺序，保持与前端一致
    status: completed
    dependencies:
      - update-chartstyle
  - id: sweep-old-palette
    content: 使用 [subagent:code-explorer] 全局核查是否仍有旧冷色 ramp 硬编码残留
    status: completed
    dependencies:
      - add-palette-tokens
      - update-chartstyle
      - update-backend-palette
  - id: verify-preview-cleanup
    content: 更新 palette_preview.html 用最终顺序，浏览器复核观感，确认后删除文件并关闭 :8899 服务
    status: completed
    dependencies:
      - add-palette-tokens
      - update-chartstyle
      - update-backend-palette
  - id: final-verify
    content: 重新读取三处改动做一致性校验，标注未做动态服务端测试的「请手动测试」项
    status: completed
    dependencies:
      - sweep-old-palette
      - verify-preview-cleanup
---

## 用户需求

为 AI 数据分析平台建立「品牌色 + 数据色板（Categorical Palette）」体系：在保留深空背景、卡片、银河紫（AI 专用）等品牌语义不变的前提下，把普通图表从「仅蓝→青冷色 ramp」扩展为 10 色有序分类色板，解决数十张图同色导致的单调问题。

## 核心特性

- 10 色有序分类色板（低饱和、偏冷、专业 BI 风）：星光蓝 #38BDF8、浅靛蓝 #A5B4FC、极光青 #22D3EE、淡紫 #C084FC、天空蓝 #60A5FA、湖水绿 #2DD4BF、金色 #FBBF24、玫瑰粉 #F472B6、珊瑚橙 #FB923C、青柠绿 #84CC16。
- 出现顺序按「前 3 色保留冷色品牌调（蓝→靛→青），相邻色拉开对比，暖色作节奏点缀」原则做两处最小交换（天空蓝↔淡紫、珊瑚橙↔玫瑰粉）。
- 银河紫 #8B5CF6 仍只用于 AI / Glow / 按钮等品牌语义，**不进入普通图表**；图表第二数据位用浅靛蓝 #A5B4FC 替补，保持 10 色且不破约束。
- 仍是固定有序分类色板（按顺序取色），非每图随机 / 彩虹配色。
- 后端 SSOT 与前端 SSOT 同步更新；临时预览页复核效果后清理。

## 技术栈

- 前端：React + TypeScript + ECharts（主题来自 frontend/src/theme）
- 后端：Python（FastAPI）+ ECharts option 生成器 `src/echart_generator.py`
- 预览：独立 `palette_preview.html`（真实 ECharts 渲染，深空背景，仅评估用）

## 实现方案

本次改动本质是「配置/常量层」升级，不动图表渲染逻辑，仅替换分类色板数组并同步前后端 SSOT。

关键决策与依据：

1. **真实图表颜色来自后端 option**：`echart_generator.py` 用 `WARM_COLORS`（= `BLUE_PALETTE`）为 bar/line/area/scatter/pie/histogram/boxplot 逐系列/逐点赋色。因此**首要改动是后端 `BLUE_PALETTE` 数组**，前端组件（EChartView）直接渲染后端 option，会自动生效。
2. **前端 SSOT 同步**：`frontend/src/theme/Palette.ts` 是唯一 HEX 来源，`ChartStyle.series`/`pie` 是文档化 SSOT（Theme.ts 将其聚合进 `theme.chart`），须与后端数组完全一致，否则违反既有纪律（记忆 SSOT）。
3. **紫禁图表**：当前 `ChartStyle.pie` 含 `Palette.ai`（紫），属既有不一致，本次一并移除；`emphasisGlow`/hover 紫色边框属 VDS 允许的「AI 辉光」，保留不动。
4. **爆炸半径控制**：后端仅改 `BLUE_PALETTE` 常量定义与其注释，`WARM_COLORS` 别名及全部调用点（8 处 `WARM_COLORS[i % len(...)]`）保持不变，避免无关重构。
5. **导出文件不改**：`exportEChartsDashboard.ts` 用户此前明确拒绝改动；其图表色来自传入的 option（后端已生效），且环形图配色数组为独立 5 色报告主题，不在本次范围。

## 实现注意

- 新增 8 个分类 token 全部落到 `Palette.ts`，禁止在其它文件写死 HEX。
- 金色 `#FBBF24` 与现有 `Palette.warning` 同值，新增独立 `catGold` token 以避免语义混淆（数据色 vs 预警语义）。
- 地图/热力图渐变（correlation heatmap 的蓝色 ramp、大屏地图紫色调）属专用美学，不在 VDS 改造范围，保持原样。
- 验证：前端 `tsc`/构建通过；后端无需构建；用预览页肉眼确认「单/双/三/五折线仍高级冷调、10 折线/堆叠柱暖色拉节奏且不花」。

## 架构与数据流

```
Palette.ts(SSOT HEX) ──► ChartStyle.series/pie ──► Theme.ts(theme.chart) ──► 组件按需取用
echart_generator.py: BLUE_PALETTE/WARM_COLORS ──► 生成的 ECharts option.color/itemStyle
                                                  │
                                                  ▼
                                          EChartView.tsx 渲染（option 自带颜色）
```

前后端两处数组必须顺序、取值完全一致，是本次一致性核心。

## 目录结构与文件

```
src/echart_generator.py              # [MODIFY] 替换 BLUE_PALETTE(8色) 为新 10 色有序数组；更新 WARM_COLORS 注释；保留所有调用点不变（最小爆炸半径）
frontend/src/theme/Palette.ts        # [MODIFY] 新增分类色区：catIndigo/catLightPurple/catSkyBlue/catLake/catGold/catRose/catCoral/catLime；ai(#8B5CF6) 保持 AI 专用不进图表
frontend/src/theme/ChartStyle.ts     # [MODIFY] series 改为 10 色有序数组(引用新 token)；pie 移除 Palette.ai 改用分类色；更新注释(解除红绿禁, 保留紫禁图表/禁彩虹)
palette_preview.html                 # [MODIFY→DELETE] 临时评估页：先用最终顺序(紫→浅靛蓝)复核视觉，确认后删除并关闭 :8899 服务
frontend/src/utils/exportEChartsDashboard.ts  # [不改] 按用户意愿保留现状，计划中标注
```