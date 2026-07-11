# DataMind AI 面试准备 — 项目 Bug 与 HR 问答

---

## 一、项目中遇到的核心 Bug 及解决方案

### Bug 1：省份/地区列画图时数据混乱（最核心）

**问题描述**：当用户选择"省份"或"地区"等分类列作为 X 轴画柱状图/折线图时，数据是按原始行数绘制的（如北京有 7 行数据就画 7 个柱子），而不是按省份分组聚合后绘制（应该是北京 1 个柱子 = 所有北京数据的销售额总和）。

**根本原因**：图表生成函数（`create_bar_chart`、`create_line_chart`、`create_waterfall` 等）直接使用原始 DataFrame，没有对分类列做 groupby 聚合。当同一省份出现多次时，ECharts 会按行数画多个柱子。

**解决方案**：
1. 新增 `_should_auto_group()` 判断函数 — 识别 X 轴列是否需要分组（基于列名关键词、值内容关键词、重复率 > 1.2）
2. 新增 `_auto_groupby()` 聚合函数 — 自动 groupby X 轴列 + sum 聚合 Y 轴列
3. 在 `create_bar_chart`、`create_line_chart`、`create_waterfall` 中调用 `_auto_groupby`
4. 修改 AI 数据计算 Prompt — 增加规则 8/9，强制要求对省份/地区列使用 groupby + transform

**HR 可能追问**：
- Q: 你怎么判断哪些列需要分组？
- A: 四层判断逻辑：① 列名含"省/市/区/地区/城市/部门/类别"等关键词；② 值内容含"省/市"等关键词；③ 行数/唯一值数 > 1.2（非唯一映射）；④ 数值型/datetime 列排除。这样既覆盖了语义判断，又覆盖了统计特征。

---

### Bug 2：CSV 文件编码问题导致中文乱码

**问题描述**：用户上传 GBK 编码的 CSV 文件时，Pandas 默认用 UTF-8 解析，导致中文内容全部变成乱码或报 UnicodeDecodeError。

**根本原因**：中国用户的数据文件大量使用 GBK/GB2312 编码，而 Python 默认 UTF-8。

**解决方案**：在 `data_loader.py` 的 `load_csv()` 中实现多编码自动检测：依次尝试 UTF-8 → GBK → GB2312 → UTF-16 → Latin-1，任何一种成功即返回。此外还增加了 xlsx 文件伪装成 csv 的检测（文件头 `PK\x03\x04`）。

**HR 可能追问**：
- Q: 为什么不用 chardet 库自动检测编码？
- A: chardet 需要额外依赖且对小文件检测不准确。我们的方案是依次尝试常见中文编码，覆盖率足够且零依赖，性能也更好。

---

### Bug 3：NaN 值导致 JSON 序列化失败

**问题描述**：DataFrame 中的 NaN/None 值在返回给前端时，JSON 序列化会报错或前端收到 `NaN` 字符串导致页面崩溃。

**根本原因**：JSON 标准不支持 NaN 值，而 Pandas DataFrame 的 `to_dict()` 会保留 NaN。

**解决方案**：所有返回给前端的 DataFrame 数据都经过 `.replace({np.nan: None})` 处理，将 NaN 转为 JSON 合法的 null。在 AI 清洗返回中还额外处理了 `np.inf` 和 `-np.inf`。

**HR 可能追问**：
- Q: 为什么不在前端处理 NaN？
- A: NaN 不是合法 JSON 值，传输层就会出错。必须在后端源头处理，确保 API 响应始终是合法 JSON。

---

### Bug 4：文件格式伪装（xlsx 伪装成 csv）

**问题描述**：用户将 Excel 文件改名扩展名为 .csv 后上传，Pandas 的 `read_csv` 会报错或解析出乱码。

**根本原因**：只根据文件扩展名判断格式，未检查实际文件内容。

**解决方案**：在 `load_csv()` 中检查文件头 magic bytes — xlsx 文件的文件头是 `PK\x03\x04`（ZIP 格式），检测到后直接抛出明确的错误提示："文件内容是 Excel 格式（.xlsx），但扩展名是 .csv。请将文件另存为 CSV 格式，或修改扩展名为 .xlsx"。

---

### Bug 5：AI 生成的代码包含非安全操作

**问题描述**：AI 数据计算功能允许 LLM 生成 Python 代码并在后端执行，可能生成 `os.system()`、文件删除等危险操作。

**根本原因**：LangChain 的 Python 执行工具没有安全沙箱。

**解决方案**：
1. 代码执行前做关键词黑名单检查（`import os`、`subprocess`、`eval`、`exec`、`__import__`、`open` 写模式等）
2. 限制只能对 DataFrame 操作，不能创建新 DataFrame
3. 执行结果做 NaN/Inf 过滤后再返回前端

**HR 可能追问**：
- Q: 这种方案能防止所有恶意代码吗？
- A: 不能 100% 防止，但覆盖了最常见的攻击路径。生产环境应使用 Docker 容器或 RestrictedPython 沙箱执行。我们当前是内部工具，黑名单方案是合理的折中。

---

### Bug 6：前后端跨域通信（CORS）

**问题描述**：前端 Vite Dev Server 在 localhost:5173，后端 FastAPI 在 localhost:8000，浏览器默认禁止跨域请求。

**根本原因**：前后端分离架构中，不同端口 = 不同源 = CORS 限制。

**解决方案**：
- 后端：FastAPI 中添加 `CORSMiddleware`，允许 `localhost:5173/3000` 跨域
- 前端：Vite 配置 `proxy`，将 `/api` 请求代理到 `localhost:8000`

**HR 可能追问**：
- Q: 为什么同时用了 CORS 和 proxy？是不是多余？
- A: 不多余。proxy 只在开发环境生效（Vite dev server），生产环境部署时前端和后端可能在不同域名，需要 CORS。两个机制服务不同场景。

---

### Bug 7：数据类型误识别（文本被当成数值，或反之）

**问题描述**：CSV 中的日期列、数值列常被 Pandas 误识别为 object（字符串），导致统计分析、图表生成出错。

**根本原因**：CSV 没有 schema，Pandas 只能猜测数据类型。

**解决方案**：
1. `detect_data_type_issues()` 自动扫描所有 object 列，检测 70%+ 的值可转为 datetime 或 numeric 的列
2. `convert_column_type()` 支持手动转换，并做安全检查 — 如果转换导致 > 0% 数据丢失，抛出明确的错误提示（含无法转换的具体值示例）
3. 均值/中位数填充只允许数值列，分类列强制用众数或填充 Unknown

**HR 可能追问**：
- Q: 为什么阈值是 70%？
- A: 太低（如 50%）会误判含少量数字的文本列，太高（如 90%）会漏掉含少量缺失的数值列。70% 是实际测试中在中文数据集上的最佳平衡点。

---

### Bug 8：会话管理 — 内存泄漏和并发安全

**问题描述**：多用户同时使用时，DataFrame 存在内存中可能导致内存溢出；并发请求可能导致数据竞争。

**根本原因**：内存级 Session 管理器没有容量限制和线程安全。

**解决方案**：
1. `SessionManager` 使用 `threading.Lock` 保证线程安全
2. 设置 `max_sessions=50` 和 `session_timeout=3600s` — 超时自动清理，超容量淘汰最久未访问的会话
3. 撤销栈限制 20 步，避免过多历史数据占用内存

**HR 可能追问**：
- Q: 如果用户量超过 50 怎么办？
- A: 当前是内部工具，50 会话足够。生产环境应改用 Redis + 对象存储（如 S3）存 DataFrame，内存只缓存热数据。

---

### Bug 9：AI 清洗结果 JSON 解析失败

**问题描述**：LLM 生成的清洗计划 JSON 可能格式不规范（多了注释、换行、非标准引号），导致 `json.loads()` 报错。

**根本原因**：LLM 输出不可控，不总是严格遵循 JSON 格式。

**解决方案**：
1. 先尝试 `json.loads()` 直接解析
2. 失败后用正则提取 JSON 部分（`{...}` 块）
3. 再失败则尝试 `json5` 或逐行修复常见问题（去注释、修引号）
4. 全部失败返回友好错误提示

---

### Bug 10：Plan 文件与技术栈不匹配

**问题描述**：项目开发过程中多次更换技术选型（Plotly → ECharts、shadcn/ui → DataV、React Router v6 → v7），但 plan.md 文件没有同步更新，导致文档与实际代码不一致。

**根本原因**：迭代开发中技术选型变化未及时更新文档。

**解决方案**：手动更新 plan.md，将所有过时内容替换为实际使用的技术栈和目录结构。

**HR 可能追问**：
- Q: 为什么从 Plotly 换成 ECharts？
- A: 三个原因：① ECharts 对中文地图（省份/城市）支持更好；② ECharts 深色主题和大屏模板更丰富；③ ECharts 的 option JSON 可以直接传给前端渲染，不需要 Python 端生成图片再传——前后端解耦更彻底。

---

## 二、HR 高频面试问题及参考回答

### 1. 项目整体介绍

**Q: 请简单介绍一下这个项目**

A: DataMind AI 是一个前后端分离的数据分析智能平台。前端用 React + TypeScript + ECharts，后端用 Python + FastAPI + Pandas + LangChain。核心功能包括：CSV 数据上传与预览、智能数据清洗（支持 AI 辅助）、统计分析与相关性分析、15+ 种 ECharts 图表可视化、4 种大屏仪表盘模板、AI 洞察与自然语言对话、HTML 报告导出。最大亮点是将 AI Agent（DeepSeek/通义千问等）深度集成到数据分析全流程中——从清洗建议到图表推荐到洞察生成。

---

### 2. 技术选型

**Q: 为什么选择 FastAPI 而不是 Django/Flask？**

A: 三个原因：① FastAPI 天然支持异步（async/await），AI 调用 LLM 是 IO 密集型，异步可以并发处理多用户请求；② FastAPI 自动生成 OpenAPI 文档，前端开发者可以直接看接口定义；③ Pydantic 数据验证和类型提示让代码更安全，减少手动校验。

**Q: 为什么前端用 Vite 而不是 webpack？**

A: Vite 开发启动速度极快（冷启动 < 1 秒），HMR 热更新几乎是即时刷新。webpack 配置复杂且启动慢。Vite 的 ESM 开发模式和 Rollup 生产构建也更适合现代前端。

**Q: 为什么用 ECharts 而不是 Plotly/D3？**

A: ① ECharts 对中国地理数据（省份/城市地图）有原生支持，这是项目的核心需求；② ECharts 的 option JSON 格式前后端完全解耦——后端只生成配置 JSON，前端渲染；③ ECharts 大屏/深色主题生态丰富，适合数据看板场景；④ ECharts 性能好，万级数据点流畅渲染。

---

### 3. 架构设计

**Q: 前后端是怎么通信的？**

A: 前端用 Axios 发 REST API 请求到 `/api/*`，开发环境通过 Vite proxy 转到 `localhost:8000`，生产环境需要 CORS 配置。数据传输格式是 JSON，DataFrame 通过 `to_dict(orient="records")` 序列化，NaN 值在后端替换为 null。

**Q: 会话是怎么管理的？**

A: 后端使用内存级 `SessionManager`，每个用户有 UUID session_id，DataFrame 存在 `SessionData` 对象中。支持撤销栈（最多 20 步）、图表收藏、AI Key 存储。线程安全通过 `threading.Lock` 保证，超时会话自动清理。

**Q: AI 功能是怎么实现的？**

A: 使用 LangChain + OpenAI SDK 兼容接口（支持 DeepSeek/通义千问/智谱/Moonshot/OpenAI 五家），通过统一 API 格式调用。三种 AI 场景：① 智能清洗 — LLM 分析数据后生成 JSON 清洗计划，后端解析并执行；② 数据计算 — LLM 生成 Python 代码，后端在受控环境执行；③ 洞察/对话 — LLM 直接生成文字分析。

---

### 4. Bug 和问题解决能力

**Q: 开发中遇到的最大问题是什么？怎么解决的？**

A: 最大问题是省份/地区列的图表分组聚合。原始数据中同一省份有多行记录，画图时按行绘制导致数据混乱。我设计了一个四层自动判断机制（列名关键词 → 值内容关键词 → 统计重复率 → 类型排除），然后在所有相关图表函数中统一调用 `_auto_groupby`，还修改了 AI Prompt 强制要求分组。这个方案兼顾了准确性和通用性——不需要用户手动选择是否分组，系统自动判断。

**Q: AI 代码执行的安全问题你怎么考虑的？**

A: 我做了三层防护：① Prompt 层面明确限制只能操作 DataFrame，不能创建新对象；② 代码审查层面做关键词黑名单过滤（import os、subprocess、eval 等）；③ 结果层面做 NaN/Inf 过滤。生产环境应该用 Docker 容器或 RestrictedPython 沙箱，当前方案对内部工具是合理的。

**Q: 编码问题怎么处理的？**

A: 实现了多编码自动检测链（UTF-8 → GBK → GB2312 → UTF-16 → Latin-1），覆盖了 99% 的中文数据文件。不用 chardet 是因为零依赖、速度快、小文件准确率高。

---

### 5. 性能和优化

**Q: 大数据文件的性能问题怎么处理？**

A: ① 上传限制 200MB，超过直接拒绝；② 前端预览只传前 100 行；③ 统计分析在 Pandas 端计算，只返回结果不传全量数据；④ 图表生成使用 ECharts option JSON（几 KB），不传图片；⑤ Session 超时清理避免内存堆积。

**Q: AI 调用会不会很慢？**

A: 会，LLM 调用通常 3-15 秒。优化方案：① 用 `asyncio + run_in_executor` 让 LLM 调用不阻塞其他请求；② 前端显示 loading 状态和进度提示；③ 设置 60 秒超时兜底；④ 清洗计划限制 `max_tokens=1024` 减少等待时间。

---

### 6. 项目亮点和自我评价

**Q: 这个项目最让你自豪的地方是什么？**

A: 三个方面：① AI 全流程集成 — 从上传、清洗、分析到仪表盘，每个环节都有 AI 辅助，不是简单的聊天框；② 自动分组聚合 — 用四层判断机制自动识别省份/地区列并 groupby，用户不需要手动配置；③ 多模型支持 — 5 家 LLM 厂商统一接口，用户可以自由切换，不绑定单一供应商。

**Q: 如果让你重新做这个项目，会改进什么？**

A: ① Session 管理改用 Redis + 对象存储，支持更大用户量；② AI 代码执行用 Docker 沙箱，彻底解决安全问题；③ 增加数据血缘追踪和版本管理；④ 图表配置支持更多自定义（颜色主题、字体等）；⑤ 增加单元测试和 CI/CD 流程。

---

### 7. 数据分析专业问题

**Q: 你用了哪些数据分析方法？**

A: ① 描述性统计（均值/中位数/标准差/分位数）；② 相关性分析（Pearson/Spearman/Kendall）；③ 分组统计（groupby + agg）；④ 异常值检测（IQR 四分位距法 + Z-score 法）；⑤ 缺失值分析（缺失率/分布模式）；⑥ KPI 环比计算（最新期 vs 上期变化率）。

**Q: IQR 和 Z-score 检测异常值有什么区别？**

A: IQR 基于数据分布的四分位数，对非正态分布数据更稳健（用 Q1-1.5*IQR 和 Q3+1.5*IQR 定义边界）；Z-score 假设数据近似正态分布，用均值 ± 3σ 定义边界。项目中两种都支持，默认用 IQR 因为真实数据很少是严格正态的。

**Q: 数据清洗的常见策略有哪些？**

A: ① 缺失值处理 — 删除/均值填充/中位数填充/众数填充/填充 0/填充 Unknown；② 类型转换 — 文本转数值/日期/分类；③ 异常值处理 — 删除/截断（clip）；④ 去重；⑤ AI 辅助清洗 — LLM 分析数据后自动生成清洗计划。

---

## 三、功能添加记录与我的选择决策

### 功能 1：省份/地区列自动分组聚合

**添加原因**：画图时 X 轴选择省份/地区列，数据按原始行绘制导致混乱，需要自动 groupby 聚合。

**我的选择**：
- ✅ 选择方案：四层自动判断机制（列名关键词 → 值内容关键词 → 统计重复率 → 类型排除），全自动无需用户手动选择
- ❌ 放弃方案：让用户手动勾选"是否分组" — 交互负担大，用户未必知道何时该分组

**怎么添加的**：
1. 在 `echart_generator.py` 中新增 `_should_auto_group()` + `_auto_groupby()` 两个私有函数
2. 修改 `create_bar_chart`、`create_line_chart`、`create_waterfall` 三个图表函数，在有 Y 轴时调用 `_auto_groupby`
3. `create_stacked_bar` 和 `create_area_chart` 内部调用 bar/line，间接生效
4. 修改 AI 数据计算 Prompt（`data.py`），增加规则 8/9 强制分组

**关键词表的选择**：
- 省份关键词表 `_GEO_KEYWORDS` 包含了中文（省/市/区/县/地区/城市/省份/部门/类别/类型/分类/分组）和英文（province/city/region/area/district/state/country）
- 列名关键词表 `_GEO_COL_KEYWORDS` 额外包含了地址/位置/名称等
- 重复率阈值选 1.2（行数/唯一值数 > 1.2 即判定需要分组）— 太低误判，太高漏判

---

### 功能 2：多 AI 模型支持（5 家 LLM 供应商）

**添加原因**：最初只支持 DeepSeek，但用户可能有其他 API Key，需要灵活切换。

**我的选择**：
- ✅ 选择方案：OpenAI SDK 兼容接口统一封装，前端下拉选择 Provider
- ❌ 放弃方案：每家 LLM 写独立 SDK 适配代码 — 维护成本高，各家兼容接口已趋标准化

**怎么添加的**：
1. `DataContext.tsx` 中定义 `AI_PROVIDERS` 配置数组（5 家：DeepSeek、通义千问、智谱GLM、Moonshot、OpenAI）
2. 每家配置包含 `id / name / baseUrl / model`，所有 LLM 调用都通过 `openai.OpenAI(api_key, base_url)` 统一入口
3. 前端 API 请求中携带 `api_key + base_url + model` 三个参数，后端路由层透传给 LLM

**为什么选择这 5 家**：
- DeepSeek — 性价比最高，中文能力强
- 通义千问（阿里云）— 国内合规，企业客户常用
- 智谱 GLM-4-flash — 免费/低成本，适合测试
- Moonshot/Kimi — 长文本能力强，适合大数据摘要
- OpenAI GPT-4o-mini — 国际标杆，外企/海外用户需求

---

### 功能 3：ECharts 图表引擎替换 Plotly

**添加原因**：Plotly 生成的是 Python 图片对象，需要序列化传前端再渲染，耦合严重；且不支持中文地图。

**我的选择**：
- ✅ 选择方案：完全替换为 ECharts，后端只生成 option JSON（几 KB），前端渲染
- ❌ 放弃方案：双引擎共存（Plotly + ECharts）— 维护两套图表函数成本太高

**怎么添加的**：
1. 新建 `src/echart_generator.py`，实现 15+ 种图表（柱状图/折线图/饼图/散点图/直方图/箱线图/雷达图/堆叠柱状图/面积图/瀑布图/气泡图/树状图/词云图/地图/热力图）
2. 前端新建 `EChartView.tsx` 组件，接收 option JSON + 渲染 ECharts 实例
3. 保留 `chart_generator.py`（Plotly 版）作为备份参考，但实际不再使用
4. 大屏仪表盘全面迁移到 ECharts — `getDashboardECharts` API 替代 `getDashboardCharts`

**为什么选 ECharts 而不是 D3**：
- D3 太底层，需要手写 SVG/Canvas 渲染逻辑；ECharts 是声明式配置（option JSON），开发效率高 10 倍
- ECharts 内置中文地图（省份/城市/区县），D3 需要额外加载 GeoJSON
- ECharts 大屏生态（DataV/深色主题）直接可用

---

### 功能 4：4 种大屏仪表盘模板

**添加原因**：用户对数据大屏有不同场景需求——指挥中心要 3D 地球，看板要 KPI + 趋势，网格要多图表并排。

**我的选择**：
- ✅ 选择方案：4 种可切换模板（指挥中心 / 数据看板 / 经典网格 / 分析报告）
- ❌ 放弃方案：单一大屏布局 — 无法适配不同业务场景

**怎么添加的**：
1. `frontend/src/components/BigScreen/` 下 6 个组件文件：
   - `CommandScreen.tsx` — 指挥中心（3D 地球 + 飞线 + 数据面板）
   - `MedicalDashboard.tsx` — 数据看板（KPI + 趋势图 + 雷达图 + 表格）
   - `EGridLayout.tsx` — 经典网格（KPI 条 + 2x3 图表 + 联动高亮）
   - `ClassicLayout.tsx`、`GridLayout.tsx`、`ImmersiveLayout.tsx` — 辅助布局
2. `DashboardPage.tsx` 中 `TEMPLATES` 数组定义 4 种模板选项卡
3. AI 推荐布局功能 — 调 `getEChartsAiLayout` 让 LLM 根据数据特征推荐最优模板和图表组合

---

### 功能 5：大屏导出为独立 HTML 文件

**添加原因**：用户需要将大屏分享给非技术人员，不能要求对方也运行本项目。

**我的选择**：
- ✅ 选择方案：前端生成自包含 HTML（内嵌 ECharts CDN + 数据 + 样式），可直接浏览器打开
- ❌ 放弃方案：只支持 PNG 截图 — 截图失去交互性（tooltip、联动）

**怎么添加的**：
1. `frontend/src/utils/exportEChartsDashboard.ts` — 6 个模板各自生成完整 HTML
2. HTML 内嵌：ECharts CDN script、COMMON_CSS 深色主题、KPI 卡片 HTML、所有图表 option JSON
3. 支持 PNG 截图导出（html2canvas）作为补充方案
4. 数据分析报告现由后端 `/report/ai-analyze` 端点驱动（`src.ai_agent` + `src.report_builder` 五阶段流水线 → HTML），不再依赖 Jinja2 模板模块

---

### 功能 6：图表收藏（分析页 → 仪表盘）

**添加原因**：用户在分析页精心调好的图表，希望直接推送到大屏展示，而不是在大屏重新配置。

**我的选择**：
- ✅ 选择方案：分析页"保存到仪表盘"按钮 → Session 中收藏 → 仪表盘页"加载收藏图表"
- ❌ 放弃方案：手动复制配置 — 用户体验差

**怎么添加的**：
1. `SessionManager` 中新增 `saved_charts` 列表字段 + `save_chart / get_saved_charts / delete_saved_chart / clear_saved_charts` 方法
2. 后端新增 `/api/dashboard/save-chart`、`/api/dashboard/saved-charts`、`/api/dashboard/delete-saved-chart` 三个 API
3. 前端分析页"保存图表"按钮调 `api.saveChart(sessionId, title, option)`
4. 前端仪表盘页"加载收藏图表"按钮调 `api.getSavedCharts(sessionId)` 并渲染

---

### 功能 7：AI 智能清洗

**添加原因**：用户不懂数据清洗技术术语（IQR/均值填充/众数），希望用自然语言描述需求即可。

**我的选择**：
- ✅ 选择方案：LLM 生成 JSON 清洗计划（结构化、可解析），后端解析后逐步执行
- ❌ 放弃方案：LLM 直接生成 Python 代码执行 — 太危险，清洗操作应该原子化可控

**怎么添加的**：
1. `backend/routers/clean.py` 中 `ai_clean` 路由 — 构建 Prompt（含数据信息、缺失值报告、重复行数、前 20 行预览），要求 LLM 返回 JSON 格式清洗计划
2. JSON 格式定义 4 种 action：`fill_missing / drop_duplicates / handle_outliers / convert_type`
3. 后端逐步执行每条清洗操作，记录每步成功/失败
4. JSON 解析容错：先 `json.loads()` → 失败则正则提取 → 修复注释/引号 → 最终兜底报错
5. 前端显示清洗解释、每步结果、行数变化

---

### 功能 8：AI 数据计算

**添加原因**：用户需要自定义计算列（同比/环比/排名/占比/累计等），但不会写 Pandas 代码。

**我的选择**：
- ✅ 选择方案：LLM 生成 Python 代码 → 后端受控执行（安全检查 + 20 秒超时）→ 新列加入 DataFrame
- ❌ 放弃方案：预定义计算模板下拉选择 — 灵活性不足，无法覆盖用户自定义需求

**怎么添加的**：
1. `backend/routers/data.py` 中 `compute_data` 路由
2. Prompt 强调：只能操作 df，不能创建新 DataFrame，新列名用中文
3. 规则 8/9：对省份/地区列必须 groupby + transform，不能逐行简单运算
4. 代码安全检查：关键词黑名单（import os / subprocess / eval / exec / __import__ / open 写模式）
5. 执行方式：`threading.Thread(daemon=True)` + `thread.join(timeout=20)` 防止死循环
6. 结果处理：NaN → None、Inf → None，确保 JSON 合法

---

### 功能 9：撤销栈（Undo）

**添加原因**：清洗操作可能出错（如误删数据），需要能回退。

**我的选择**：
- ✅ 选择方案：DataFrame 撤销栈（最多 20 步），每次清洗前 `push_undo_state` 保存副本
- ❌ 放弃方案：全量 diff 存储 — DataFrame diff 计算复杂且存储大；直接重做 — 用户会丢失中间步骤

**怎么添加的**：
1. `SessionData` 中新增 `df_undo_stack: List[pd.DataFrame]`
2. 每次清洗/类型转换/异常值处理前调用 `manager.push_undo_state(session_id)`
3. 撤销 API `/api/clean/undo` 调用 `manager.undo_last_action()` 弹栈恢复
4. 栈大小限制 20 步（`pop(0)` 淘汰最早的），避免内存膨胀

---

### 功能 10：Streamlit → FastAPI 前后端分离架构迁移

**添加原因**：原项目基于 Streamlit 单体应用（Python 渲染 HTML），无法做精美 UI 和交互大屏。

**我的选择**：
- ✅ 选择方案：完全重构为 React + FastAPI 前后端分离，保留核心数据处理引擎
- ❌ 放弃方案：继续用 Streamlit — UI 粗糙、无法自定义组件、大屏效果差

**怎么添加的**：
1. 后端：将 Streamlit 的 `st.session_state` 替换为 `SessionManager`（内存级，UUID 会话）
2. 后端：Streamlit 的 `st.cache` 替换为无缓存（每次从 session 取 DataFrame）
3. 后端：新增 9 组 REST API 路由（upload/data/clean/stats/chart/dashboard/insights/chat/report）
4. 前端：React SPA 4 页面路由（Upload → Clean → Analysis → Dashboard）
5. 前端：`DataContext` 全局状态管理替代 Streamlit 的隐式状态
6. 保留 `app.py / app_backup.py / app_simple.py` 作为 Streamlit 遗留参考

**迁移难点**：
- Streamlit 是同步阻塞模型，FastAPI 是异步模型 → 所有 LLM 调用需 `run_in_executor` 包装
- DataFrame 原来在 `st.session_state` 中自动持久化 → 现在需要手动 `SessionManager` 管理
- Streamlit 自动重渲染机制 → React 需要手动 `useEffect` + `useState` 触发更新

---

### 功能 11：深色主题大屏 UI 设计

**添加原因**：数据分析平台需要专业视觉风格，浅色主题不够酷炫，大屏场景必须是深色。

**我的选择**：
- ✅ 选择方案：全局深色主题（CSS 变量 + TailwindCSS dark mode），紫/青渐变科技感配色
- ❌ 放弃方案：浅色主题 + 深色切换 — 加倍 CSS 工作量，大屏场景深色是刚需不是选项

**怎么添加的**：
1. `frontend/src/static/index.css` — 全局 CSS 变量定义深色配色（`#050816` 背景、`#8b5cf6` 紫色、`#22d3ee` 青色）
2. TailwindCSS 自定义配色（`text-[#f8fafc]`、`bg-[#050816]`、`border-[#8b5cf6]`）
3. ECharts 深色主题 `DARK_THEME` 配置（`echart_generator.py` 中定义）
4. 标题/数字发光效果：`textShadow: '0 0 15px rgba(139,92,246,0.3)'`
5. KPI 卡片渐变边框 + 动画数字（`AnimatedNumber.tsx` 组件）
6. 脉冲指示灯（绿色圆点 `animation: pulse 2s infinite`）

---

### 功能 12：地图可视化（省份/城市热力地图）

**添加原因**：中国数据分析最常见的需求之一就是看各省/各城市的分布情况。

**我的选择**：
- ✅ 选择方案：ECharts 中国地图（内置省份/城市 GeoJSON），热力地图 + 3D 地球飞线
- ❌ 放弃方案：Plotly 地图 — 不支持中国省份地图；Leaflet — 需要额外加载地图瓦片，交互性弱

**怎么添加的**：
1. `echart_generator.py` 中 `create_map()` 函数 — 自动识别省份/城市列，groupby 聚合后生成 ECharts map option
2. 前端 `GLMapView.tsx` 组件 — 3D 地球 + 飞线效果（echarts-gl）
3. 省份名映射表（`_PROVINCE_MAP`）— 自动标准化省份名（"北京" → "北京市"、"广东" → "广东省"）
4. 指挥中心模板 `CommandScreen.tsx` 集成 3D 地球

---

### 功能 13：相关性热力图

**添加原因**：用户需要看各数值列之间的相关性（谁和谁强相关/弱相关）。

**我的选择**：
- ✅ 选择方案：ECharts 热力图渲染 Pearson/Spearman/Kendall 相关系数矩阵
- ❌ 放弃方案：表格展示相关系数 — 不直观；Plotly 热力图 — 已弃用 Plotly

**怎么添加的**：
1. `stats_analyzer.py` 中 `get_correlation_matrix(df, method)` — 支持 3 种相关系数计算方法
2. 前端分析页热力图 tab → 调 `api.createHeatmap(sessionId)` 获取 ECharts option
3. 热力图配色：正相关绿色、负相关红色、0 值灰色

---

### 功能 14：文件拖拽上传

**添加原因**：传统 `<input type="file">` 体验差，需要拖拽上传更直观。

**我的选择**：
- ✅ 选择方案：react-dropzone 库实现拖拽上传组件
- ❌ 放弃方案：原生 HTML input — 无拖拽、无预览

**怎么添加的**：
1. `frontend/src/components/FileUploader.tsx` — react-dropzone 包装，支持拖拽 + 点击选择
2. 文件类型限制：`accept: { 'text/csv': ['.csv'], 'application/vnd.ms-excel': ['.xlsx', '.xls'], ... }`
3. 上传进度提示 + 成功/失败 toast

---

### 功能 15：错误边界组件（ErrorBoundary）

**添加原因**：React 组件渲染崩溃会导致整个页面白屏，需要局部错误隔离。

**我的选择**：
- ✅ 选择方案：React ErrorBoundary 包装关键页面组件，崩溃时显示友好错误提示而非白屏
- ❌ 放弃方案：try-catch 在每个组件中 — 代码重复且无法捕获渲染期错误

**怎么添加的**：
1. `frontend/src/components/ErrorBoundary.tsx` — React class 组件，`componentDidCatch` 捕获渲染错误
2. `UploadPage.tsx` 外层 `<ErrorBoundary>` 包装
3. 错误时显示红色提示框 + 重试按钮

---

## 四、项目技术细节速查表

| 模块 | 文件 | 核心功能 |
|------|------|----------|
| 数据加载 | `src/data_loader.py` | CSV/Excel/JSON/SQLite 多格式加载，多编码自动检测 |
| 数据清洗 | `src/data_cleaner.py` | 缺失值处理、类型转换、异常值检测/处理、去重 |
| 统计分析 | `src/stats_analyzer.py` | 描述性统计、分组统计、相关性、快速洞察 |
| 图表生成 | `src/echart_generator.py` | 15+ 种 ECharts 图表，自动分组聚合 |
| 仪表盘 | `src/dashboard_builder.py` | KPI 计算、多模板大屏 |
| AI Agent | `src/ai_agent/` | LangChain 工具链 + 多模型支持 |
| 报告生成 | `src/ai_agent/` + `src/report_builder.py` | DataMind 五阶段流水线 → HTML 报告 |
| 会话管理 | `backend/services/session_manager.py` | UUID 会话、线程安全、撤销栈、超时清理 |
| 前端入口 | `frontend/src/App.tsx` | React Router 4 页面路由 |
| 状态管理 | `frontend/src/contexts/DataContext.tsx` | 全局数据流 + 5 家 AI Provider 配置 |
| API 客户端 | `frontend/src/api/client.ts` | Axios + 错误拦截 + 30+ API 方法 |
