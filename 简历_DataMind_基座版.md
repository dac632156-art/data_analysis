## 项目经历

### DataMind —— 数据分析平台 · 2026.06 – 2026.07

**数据分析平台**：[https://data-analysis-teal-eight.vercel.app/upload](https://data-analysis-teal-eight.vercel.app/upload)

**项目简介**：面向非技术用户的 Web 数据分析平台，上传表格即自动完成「上传解析 → AI 智能清洗 → 分析洞察 → 可视化仪表盘 / AI 报告」四步闭环。LLM 在三阶段分工协作：清洗阶段分析原始数据生成清洗方案、分析阶段复核确定性引擎结果并补充遗漏角度、报告阶段基于分析包撰写叙述。平台已部署上线（Vercel + Render）。

- **三阶段 LLM 协同架构**：清洗阶段，LLM 分析原始数据统计特征，生成清洗计划后按列套用执行；分析阶段，确定性引擎先按列名匹配执行 12 个内置模型（RFM、同期群、CLV、K-Means、漏斗、关联规则等），再将结果交由 LLM 复核——若 LLM 发现引擎未覆盖的分析角度，则生成新模型执行并并入最终分析包；报告阶段，LLM 基于完整分析包撰写结构化报告。三层分工使 LLM 在发挥判断与灵活性的同时，核心计算始终由确定性代码兜底。
- **可靠性设计**：所有 LLM 调用点均设降级机制——AI 不可达时，清洗回退手动模式、分析回退纯规则引擎、报告回退纯统计摘要；仪表盘智能排版 LLM 失败时回退规则布局。异步 task_id 轮询规避部署平台 50 秒 HTTP 超时；Semaphore(5) 控制 LLM 并发；关闭 SDK 自动重试（`max_retries=0`）使超时后立即降级。
- **前端 React + TypeScript + ECharts 6，后端 FastAPI + Python**，分析结果自动渲染为可交互图表，通过多模板仪表盘自由排版导出；LLM 通过 OpenAI 兼容 API 接入（默认 DeepSeek，支持自定义 Key）。
- **工程交付**：以 AI 编程工具驱动全栈开发，通过项目规则文件约束输出质量、结构化开发计划管理迭代；平台已部署至 Vercel + Render，可独立运行完整分析链路。

---

## 技能

- **技术栈**：React / TypeScript / ECharts（前端）；FastAPI / Python（后端）；Pandas / NumPy（数据处理与模型实现）
- **分析模型**：RFM 用户分层、同期群分析、CLV 生命周期、K-Means 聚类、转化漏斗、关联规则——理解模型原理、适用场景与输入输出
- **LLM 工程**：OpenAI 兼容 API 集成、Prompt 工程设计、LLM 降级与可靠性设计（超时/并发/兜底）
- **工程工具**：AI 编程工具（CodeBuddy）驱动全栈开发、Git 版本管理、Vercel + Render 部署
