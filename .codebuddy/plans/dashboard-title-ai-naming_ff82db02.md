---
name: dashboard-title-ai-naming
overview: 为 ai 模板（智能驾驶舱）的 Dashboard 顶部标题实现 AI 智能命名 + 手动编辑功能。后端新增命名端点（LLM 取 content → 标题）和持久化端点；前端 DashboardRenderer 增加可编辑标题 + "重新生成"按钮。
todos:
  - id: add-session-custom-title
    content: 在 session_manager.py 的 SessionData 中新增 custom_title 字段，添加 set_custom_title/get_custom_title 方法
    status: completed
  - id: add-naming-endpoint
    content: 在 backend/routers/dashboard.py 新增 POST /dashboard/schema/naming 端点，调用 LLM 生成标题并兜底关键词匹配
    status: completed
    dependencies:
      - add-session-custom-title
  - id: add-title-persistence-endpoint
    content: 在 backend/routers/dashboard.py 新增 POST /dashboard/schema/title 端点，支持 get/set 操作持久化手动编辑的标题
    status: completed
    dependencies:
      - add-session-custom-title
  - id: add-frontend-apis
    content: 在 frontend/src/api/client.ts 新增 generateDashboardTitle 和 saveDashboardTitle 两个 API 函数
    status: completed
  - id: modify-dashboard-page-title-flow
    content: 修改 DashboardPage.tsx 的 loadAiSchema 流程：sessionStorage 缓存 AI 标题 → 检查手动标题 → 传入 /dashboard/schema；新增"重新生成标题"按钮
    status: completed
    dependencies:
      - add-frontend-apis
  - id: make-title-editable
    content: 修改 DashboardRenderer.tsx 标题区域：支持双击进入编辑模式（input），Enter 保存/Esc 取消，调用 onTitleChange 回调持久化
    status: completed
  - id: add-on-title-change-prop
    content: 在 dashboard.ts 类型文件中为 DashboardRendererProps 新增 onTitleChange 回调类型，并确保 DashboardPage 传入该回调
    status: completed
---

## 用户需求

ai 模板（智能驾驶舱）顶部标题当前显示为上传的文件名（如"业务数据.csv"），需要改为 AI 智能命名，并支持手动编辑。

## 核心功能

- **AI 智能命名**：提供"重新生成"按钮手动触发，后端根据当前 session 的数据摘要（列名、数值统计、图表类型和数量等）调用 LLM 生成不超过 24 字的中文标题（如"销售增长趋势与区域分析驾驶舱"）。无 API Key 时兜底回退到关键词匹配（列名推断行业）。
- **手动编辑标题**：在标题区域双击进入编辑模式（替换为 input），Enter 保存、Esc 取消。保存后按 sessionId 持久化到后端 session_manager，跨刷新保留。
- **标题优先级**：手动编辑的标题 > AI 生成的标题 > 文件名。首次加载 ai 模板时自动生成一次 AI 标题并缓存到 sessionStorage，之后可通过"重新生成"按钮手动重新生成。

## 技术栈

- 后端：Python FastAPI + session_manager（内存存储）+ OpenAI-compatible LLM（复用 DataContext 的 apiKey/baseUrl/model）
- 前端：React + TypeScript，sessionStorage 缓存

## 实现方案

### 整体策略

在 ai 模板（智能驾驶舱）的标题全链路中植入三层能力：后端 AI 命名端点 → 前端 sessionStorage 缓存 + "重新生成"按钮 → 标题区域双击内联编辑。

### 后端新增端点

#### 1. `POST /dashboard/schema/naming` — AI 智能命名

- 输入：`{ session_id, api_key, base_url, model }`
- 逻辑：

1. 从 `session_manager.get_saved_packages(session_id)` 获取已保存分析包
2. 构建上下文：数据列名列表、指标列/维度列分类、图表类型汇总（如"含 2 个折线图、1 个饼图、3 个柱状图"）、行数
3. 调 LLM（OpenAI SDK）请求生成 ≤24 字中文标题
4. LLM 失败或无 apiKey → 兜底：按 column names 关键词匹配（复用 `DashboardPage.inferIndustryTitle` 的同款列名词表）

- 返回：`{ "title": "...", "source": "ai" | "fallback" }`

#### 2. `POST /dashboard/schema/title` — 标题持久化

- 输入：`{ session_id, title, action: "get" | "set" }`
- `action="set"`：写入 `SessionData.custom_title`
- `action="get"`：返回当前 `SessionData.custom_title`（若有）
- 返回：`{ "success": true, "title": "...", "has_custom": bool }`

### 前端修改

#### DashboardPage.tsx — 标题获取流程改造

- `loadAiSchema` 改为：

1. 先检查 sessionStorage 缓存 `ai_title_${sessionId}`
2. 若无缓存，调 `POST /dashboard/schema/naming` 生成 AI 标题，写入缓存
3. 再调 `POST /dashboard/schema/title?action=get` 检查是否有手动编辑过的标题
4. 优先级：手动标题 > AI 标题 > fileName
5. 用最终标题调 `POST /dashboard/schema` 加载 schema

- 新增按钮：ai 模板区域显示"重新生成标题"按钮，点击清除缓存 → 重新调 naming 端点 → 刷新 schema
- 回调：`handleTitleChange` 调 `POST /dashboard/schema/title?action=set` 保存

#### DashboardRenderer.tsx — 标题内联编辑

- `<h1>` 区域改为：正常状态显示标题 + 右侧铅笔图标（hover 可见），双击替换为 `<input>`（autoFocus）
- Enter 保存 → 调 `onTitleChange(newTitle)` → 更新 `schema.title` 本地状态
- Esc 取消 → 恢复原标题
- 样式：编辑状态 input 带黄色边框和背景，与暗色主题协调

#### API client.ts

- 新增 `generateDashboardTitle(sessionId, apiKey, baseUrl?, model?)` → `POST /dashboard/schema/naming`
- 新增 `saveDashboardTitle(sessionId, title, action)` → `POST /dashboard/schema/title`

### 关键决策

- **LLM prompt 设计**：标题 ≤24 字，需体现代数据主题/分析维度/图表类型。prompt 格式参考 `_build_insights_data_summary()` 已有的数据摘要构建模式。
- **sessionStorage 缓存键**：`ai_title_${sessionId}`，避免同一 session 重复调 LLM。
- **兜底命名词表**：从 `inferIndustryTitle` 的 `industryPatterns` 提取列名关键词 → 匹配标题（如含"销售/收入"→"销售数据分析驾驶舱"）。

### 性能与可靠性

- AI 命名仅在首次加载或手动点击"重新生成"时触发，不影响普通切换模板性能
- sessionStorage 缓存避免同一 session 重复调 LLM（节省 token）
- LLM 超时 30s，失败回退到列名关键词匹配，不阻塞 schema 加载
- 所有后端返回路径经 `sanitize_json()` 处理