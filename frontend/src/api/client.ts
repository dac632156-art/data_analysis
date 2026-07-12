/* DataMind AI - Axios API 客户端 */

import axios from 'axios';
import type {
  UploadResponse, PreviewResponse, StatsResponse,
  InsightsResponse, ChatResponse,
  AIReportResponse, KPIResponse, EChartResponse, EChartItem,
} from '../types/api';
import type { ChartConfig } from '../types';

// 部署时通过环境变量指定后端地址，本地开发走 Vite proxy
const API_BASE = import.meta.env.VITE_API_BASE || '/api';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 300000,  // 5 分钟，AI 清洗/报告生成需要更长时间
  // 不设置全局 Content-Type，让 axios 自动处理：
  // JSON 请求会自动设为 application/json，FormData 上传会自动设为 multipart/form-data
});

// 统一将 AI 模型名转为小写，避免大小写不匹配导致 model_not_found
// （阿里云百炼 / DeepSeek / OpenAI 等 API 的模型 ID 均为小写格式，如 qwen3.7-plus、deepseek-chat）
api.interceptors.request.use((config) => {
  if (
    config.data &&
    typeof config.data === 'object' &&
    typeof config.data.model === 'string'
  ) {
    config.data.model = config.data.model.toLowerCase();
  }
  return config;
});

// 后端休眠/无响应时的自动重试（同时支持 Render 部署版和本地 dev）
let _wakePromise: Promise<void> | null = null;

async function wakeUpBackend(reason: string): Promise<void> {
  if (_wakePromise) return _wakePromise;
  _wakePromise = (async () => {
    console.warn(`🔧 检测到后端无响应（${reason}），等待 5 秒后重试...`);
    // 等待一段时间让后端恢复（本地 vite proxy / Render 冷启动都适用）
    await new Promise(r => setTimeout(r, 5000));
    console.log('✅ 等待结束，即将重试请求');
  })();
  await _wakePromise;
  _wakePromise = null;
}

api.interceptors.response.use(
  (res) => res,
  async (err) => {
    // 检测网络/超时错误
    const isNetworkError = !err.response &&
      (err.code === 'ECONNABORTED' || err.code === 'ERR_NETWORK' ||
       err.message?.includes('timeout') || err.message?.includes('Network Error'));

    if (isNetworkError && err.config && !err.config._retried) {
      err.config._retried = true;
      await wakeUpBackend(err.message || err.code || 'unknown');
      return api(err.config);  // 重试
    }

    let msg = err.response?.data?.detail || err.message || '请求失败';
    // FastAPI 422 验证错误时 detail 是数组，需要提取第一条信息
    if (Array.isArray(msg)) {
      msg = msg.map((d: { msg?: string }) => d.msg || JSON.stringify(d)).join('; ');
    }
    if (typeof msg !== 'string') msg = String(msg);
    // 详细诊断日志：url + status + code
    const url = err.config?.url || '?';
    const status = err.response?.status ?? 'N/A';
    const code = err.code || 'N/A';
    console.error(`[API Error] ${url} → ${status} (${code}):`, msg);
    return Promise.reject(new Error(msg));
  }
);

/* ===== 会话 ===== */
export const createSession = async (): Promise<string> => {
  const { data } = await api.get('/session/new');
  return data.session_id;
};

/* ===== 文件上传 ===== */
export const uploadFile = async (
  file: File,
  sessionId: string
): Promise<UploadResponse> => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('session_id', sessionId);
  // 不手动设置 Content-Type，让浏览器/axios 自动添加正确的 boundary
  const { data } = await api.post('/upload', formData, {
    timeout: 600000,  // 10 分钟，大文件上传需要更长时间
  });
  return data;
};

/* ===== 数据操作 ===== */
export const getDataPreview = async (sessionId: string, rows = 100) => {
  const { data } = await api.post<PreviewResponse>('/data/preview', { session_id: sessionId, rows });
  return data;
};

export const getDataInfo = async (sessionId: string) => {
  const { data } = await api.post('/data/info', { session_id: sessionId });
  return data;
};

export const getColumnInfo = async (sessionId: string) => {
  const { data } = await api.post('/data/columns', { session_id: sessionId });
  return data;
};

export const getColumnTypes = async (sessionId: string) => {
  const { data } = await api.post('/data/column-types', { session_id: sessionId });
  return data;
};

/** 获取数据摘要统计（describe 全量指标） */
export const getDataSummary = async (sessionId: string): Promise<{ success: boolean; summary: Record<string, unknown> }> => {
  const { data } = await api.post('/data/summary', { session_id: sessionId });
  return data;
};

/* ===== 数据清洗 ===== */
export const getMissingReport = async (sessionId: string) => {
  const { data } = await api.post('/clean/missing-report', { session_id: sessionId });
  return data;
};

export const handleMissing = async (sessionId: string, column: string, method: string) => {
  const { data } = await api.post('/clean/handle-missing', { session_id: sessionId }, {
    params: { column, method },
  });
  return data;
};

export const detectTypeIssues = async (sessionId: string) => {
  const { data } = await api.post('/clean/detect-types', { session_id: sessionId });
  return data;
};

export const convertColumnType = async (sessionId: string, column: string, targetType: string) => {
  const { data } = await api.post('/clean/convert-type', { session_id: sessionId }, {
    params: { column, target_type: targetType },
  });
  return data;
};

export const detectOutliers = async (sessionId: string, method = 'iqr') => {
  const { data } = await api.post('/clean/detect-outliers', { session_id: sessionId }, {
    params: { method },
  });
  return data;
};

export const handleOutliers = async (sessionId: string, column: string, method = 'iqr', action = 'remove') => {
  const { data } = await api.post('/clean/handle-outliers', { session_id: sessionId }, {
    params: { column, method, action },
  });
  return data;
};

export const dropDuplicates = async (sessionId: string) => {
  const { data } = await api.post('/clean/drop-duplicates', { session_id: sessionId });
  return data;
};

export const resetData = async (sessionId: string) => {
  const { data } = await api.post('/clean/reset', { session_id: sessionId });
  return data;
};

export const undoLastAction = async (sessionId: string) => {
  const { data } = await api.post('/clean/undo', { session_id: sessionId });
  return data;
};

/* ===== AI 智能清洗 ===== */
export const aiClean = async (
  sessionId: string,
  request: string,
  apiKey: string,
  baseUrl?: string,
  model?: string,
): Promise<{
  success: boolean;
  explanation: string;
  steps_applied: Array<{ step: string; reason: string; success: boolean }>;
  preview: Record<string, unknown>[];
  rows: number;
  rows_change: number;
  columns: string[];
  note?: string;
}> => {
  const { data } = await api.post('/clean/ai-clean', {
    session_id: sessionId, request, api_key: apiKey, base_url: baseUrl, model,
  });
  return data;
};

export const getCleaningHistory = async (sessionId: string) => {
  const { data } = await api.post('/clean/history', { session_id: sessionId });
  return data;
};

/* ===== 数据导出 ===== */
export const downloadData = async (sessionId: string, original = false): Promise<Blob> => {
  const { data } = await api.post('/data/download', { session_id: sessionId, export_original: original }, { responseType: 'blob' });
  return data;
};

/** 触发 CSV 下载 */
export async function downloadCSV(sessionId: string, original = false) {
  const blob = await downloadData(sessionId, original);
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${original ? '原始' : '清洗后'}数据_${sessionId.slice(0, 8)}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

export const getCleanCompare = async (sessionId: string) => {
  const { data } = await api.post('/clean/compare', { session_id: sessionId });
  return data;
};

/* ===== 统计分析 ===== */
export const getDescriptiveStats = async (sessionId: string) => {
  const { data } = await api.post('/stats/descriptive', { session_id: sessionId });
  return data;
};

export const getGroupStats = async (sessionId: string, groupCol: string, aggCols?: string[]) => {
  const { data } = await api.post('/stats/group', { session_id: sessionId, group_col: groupCol, agg_cols: aggCols });
  return data;
};

export const getCorrelation = async (sessionId: string, method = 'pearson') => {
  const { data } = await api.post('/stats/correlation', { session_id: sessionId, method });
  return data;
};

export const getQuickInsights = async (sessionId: string) => {
  const { data } = await api.post('/stats/quick-insights', { session_id: sessionId });
  return data;
};

export const getNumericColumns = async (sessionId: string) => {
  const { data } = await api.post('/stats/numeric-columns', { session_id: sessionId });
  return data;
};

/* ===== AI 数据计算 ===== */
export const computeData = async (sessionId: string, query: string, apiKey: string, baseUrl?: string, model?: string) => {
  const { data } = await api.post('/data/compute', {
    session_id: sessionId, query, api_key: apiKey, base_url: baseUrl, model,
  });
  return data;
};

/* ===== 同环比专用 ===== */
export interface TbHbRow {
  month?: number;
  period: string;
  '上年值': number | null;
  '本年值': number | null;
  '同比增长率': number | null;
  '环比增长率': number | null;
}

export const getTongHuanBi = async (
  sessionId: string,
  valueColumn: string,
  dateColumn: string = '日期'
): Promise<{
  success: boolean;
  value_column: string;
  current_year: string;
  previous_year: string | null;
  rows: TbHbRow[];
  has_yoy: boolean;
  chart_option?: Record<string, unknown>;
}> => {
  const { data } = await api.post('/data/tonghuanbi', {
    session_id: sessionId,
    value_column: valueColumn,
    date_column: dateColumn,
  });
  return data;
};

/* ===== ECharts 图表 ===== */
export const createEChart = async (sessionId: string, config: ChartConfig) => {
  const { data } = await api.post<EChartResponse>('/chart/echart-create', { session_id: sessionId, ...config });
  return data;
};

/* ===== 仪表盘 ===== */
export const getDashboardKPIs = async (sessionId: string) => {
  const { data } = await api.post<KPIResponse>('/dashboard/kpis', { session_id: sessionId });
  return data;
};

/** 获取仪表盘图表（ECharts 格式） */
export const getDashboardECharts = async (sessionId: string, chartConfigs?: Record<string, unknown>[]): Promise<{ success: boolean; charts: EChartItem[] }> => {
  const { data } = await api.post('/dashboard/echarts', { session_id: sessionId, charts: chartConfigs });
  return data;
};

/* ===== 图表收藏（分析页 → 仪表盘） ===== */
export const saveChart = async (
  sessionId: string,
  title: string,
  option: Record<string, unknown>,
  chartType = '',
  tableData?: Record<string, unknown> | null,
) => {
  const { data } = await api.post('/dashboard/save-chart', {
    session_id: sessionId, title, option,
    chart_type: chartType,
    table_data: tableData || null,
  });
  return data;
};

export const getSavedCharts = async (sessionId: string): Promise<{
  success: boolean;
  charts: Array<{ title: string; option: Record<string, unknown>; saved_at: number }>;
  
}> => {
  const { data } = await api.post('/dashboard/saved-charts', { session_id: sessionId });
  return data;
};

export const deleteSavedCharts = async (sessionId: string) => {
  const { data } = await api.post('/dashboard/delete-saved-chart', { session_id: sessionId });
  return data;
};

/* ===== V2 分析包读取 ===== */
export const getSavedPackages = async (sessionId: string): Promise<{
  success: boolean;
  packages: Array<Record<string, unknown>>;
  
}> => {
  const { data } = await api.post('/dashboard/saved-packages', { session_id: sessionId });
  return data;
};

/* ===== Dashboard Schema (V2 Generator) ===== */
export const getDashboardSchema = async (
  sessionId: string,
  title?: string,
  layoutName?: string,
): Promise<{ success: boolean; schema: Record<string, unknown> }> => {
  const { data } = await api.post('/dashboard/schema', {
    session_id: sessionId,
    title: title || '',
    layout_name: layoutName || undefined,
  });
  return data;
};

/* ===== V7: Dashboard 标题 AI 命名 + 持久化 ===== */
export const generateDashboardTitle = async (
  sessionId: string,
  apiKey: string,
  baseUrl?: string,
  model?: string,
): Promise<{ success: boolean; title: string; source: 'ai' | 'fallback' }> => {
  const { data } = await api.post('/dashboard/schema/naming', {
    session_id: sessionId,
    api_key: apiKey,
    base_url: baseUrl || '',
    model: model || '',
  });
  return data;
};

export const saveDashboardTitle = async (
  sessionId: string,
  title: string,
  action: 'get' | 'set' = 'set',
): Promise<{ success: boolean; title: string; has_custom: boolean }> => {
  const { data } = await api.post('/dashboard/schema/title', {
    session_id: sessionId,
    title,
    action,
  });
  return data;
};

/* ===== AI ===== */
export const generateInsights = async (sessionId: string, apiKey: string, baseUrl?: string, model?: string) => {
  const { data } = await api.post<InsightsResponse>('/insights/generate', {
    session_id: sessionId, api_key: apiKey, base_url: baseUrl, model,
  });
  return data;
};

/* ===== 分析执行（V2）===== */
export const runAnalysis = async (sessionId: string, intents: Array<{
  business_question: string; analysis_goal: string; priority: string; reason: string;
}>) => {
  const { data } = await api.post('/analysis/run', { session_id: sessionId, intents });
  return data;
};

export const saveAnalysis = async (sessionId: string, packageIds: string[]) => {
  const { data } = await api.post('/analysis/save', { session_id: sessionId, package_ids: packageIds });
  return data;
};

/* ===== 业务推理（V3，无需 LLM）===== */
export const runReasoning = async (
  sessionId: string,
  title?: string,
): Promise<{ success: boolean; data: Record<string, unknown> }> => {
  const { data } = await api.post('/reasoning/run', {
    session_id: sessionId,
    title: title || '',
  });
  return data;
};

export const chatAnalyze = async (sessionId: string, question: string, apiKey: string, baseUrl?: string, model?: string) => {
  const { data } = await api.post<ChatResponse>('/chat/analyze', {
    session_id: sessionId, question, api_key: apiKey, base_url: baseUrl, model,
  });
  return data;
};

/* ===== 报告 ===== */




/** V3: 从 AnalysisPackage 提取扁平指标列表 */
export const generateCards = async (sessionId: string): Promise<{
  success: boolean;
  cards: Array<Record<string, unknown>>;
  meta?: Record<string, unknown>;
  
}> => {
  const { data } = await api.post('/dashboard/cards', { session_id: sessionId });
  return data;
};

// 报告生成专用 axios 实例：不挂全局 wakeUp 重试拦截器，
// 轮询节奏与冷启动重试完全由 generateAIReport 自控，避免相互干扰。
const reportApi = axios.create({ baseURL: API_BASE, timeout: 30000 });
reportApi.interceptors.request.use((config) => {
  if (
    config.data &&
    typeof config.data === 'object' &&
    typeof (config.data as { model?: unknown }).model === 'string'
  ) {
    (config.data as { model: string }).model = (config.data as { model: string }).model.toLowerCase();
  }
  return config;
});

/**
 * 生成 AI 分析报告（异步无状态）
 *
 * 流程：提交任务（拿 task_id）→ 轮询状态 → 返回结果。
 * - 规避 Render 免费实例约 50s HTTP 超时（ERR_CONNECTION_CLOSED）。
 * - packages：前端 localStorage 中的分析包副本，后端优先使用（无状态）。
 * - 提交阶段对网络错误（冷启动）有限重试；轮询阶段对网络抖动容错继续。
 */
export const generateAIReport = async (
  sessionId: string,
  apiKey: string,
  baseUrl?: string,
  model?: string,
  packages?: Array<Record<string, unknown>>,
): Promise<AIReportResponse> => {
  // 1. 提交任务（冷启动容错：最多 3 次）
  let taskId = '';
  let lastErr: unknown = null;
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const { data } = await reportApi.post('/report/ai-analyze', {
        session_id: sessionId,
        api_key: apiKey,
        base_url: baseUrl,
        model,
        packages,
      });
      taskId = data.task_id;
      break;
    } catch (e: unknown) {
      lastErr = e;
      const status = (e as { response?: { status?: number } })?.response?.status;
      // 业务错误（400 无分析结果 / 缺 Key 等）不重试，直接抛出
      if (status && status >= 400 && status < 500) {
        const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
        throw new Error(detail || '报告生成提交失败');
      }
      // 网络错误（可能是冷启动）→ 等待后重试
      await new Promise(r => setTimeout(r, 5000));
    }
  }
  if (!taskId) {
    const detail = (lastErr as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    throw new Error(detail || '后端暂时无响应（可能正在冷启动），请稍后重试。');
  }

  // 2. 轮询状态（最长 5 分钟，间隔 3 秒；单次网络抖动容错继续）
  const maxWait = 300000;
  const interval = 3000;
  const start = Date.now();
  while (Date.now() - start < maxWait) {
    await new Promise(r => setTimeout(r, interval));
    let data: { status?: string; detail?: string } & Partial<AIReportResponse>;
    try {
      const resp = await reportApi.get(`/report/ai-analyze/status/${taskId}`);
      data = resp.data;
    } catch (e: unknown) {
      // 404：任务过期/进程重启 → 明确失败，提示重新生成
      if ((e as { response?: { status?: number } })?.response?.status === 404) {
        throw new Error('报告任务已过期或后端已重启，请重新生成。');
      }
      // 其它网络抖动 → 继续下一轮轮询（容错）
      continue;
    }
    if (data.status === 'done') return data as AIReportResponse;
    if (data.status === 'error') throw new Error(data.detail || '报告生成失败');
    // running → 继续轮询
  }
  throw new Error('报告生成超时（5 分钟），请重试或减少分析项后再生成。');
};

export default api;

