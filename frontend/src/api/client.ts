/* DataMind AI - Axios API 客户端 */

import axios from 'axios';
import type {
  UploadResponse, PreviewResponse, StatsResponse,
  InsightsResponse, ChatResponse,
  ReportResponse, AIReportResponse, KPIResponse, EChartResponse, EChartItem,
} from '../types/api';
import type { ChartConfig } from '../types';

// 部署时通过环境变量指定后端地址，本地开发走 Vite proxy
const API_BASE = import.meta.env.VITE_API_BASE || '/api';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 60000,
  // 不设置全局 Content-Type，让 axios 自动处理：
  // JSON 请求会自动设为 application/json，FormData 上传会自动设为 multipart/form-data
});

// Render 后端休眠时的自动唤醒 + 重试
let _wakePromise: Promise<void> | null = null;

async function wakeUpBackend(): Promise<void> {
  if (_wakePromise) return _wakePromise;
  _wakePromise = (async () => {
    console.warn('🔧 Render 后端可能已休眠，正在唤醒（冷启动约 35 秒）...');
    // 发一个轻量 ping 触发冷启动（不限时的 GET，让 Render 收到请求并开始启动）
    try { await axios.get(`${API_BASE}/health`, { timeout: 5000 }); } catch { /* 预期可能失败 */ }
    // 等待冷启动完成
    await new Promise(r => setTimeout(r, 35000));
    console.log('✅ 唤醒等待结束，即将重试请求');
  })();
  await _wakePromise;
  _wakePromise = null;
}

api.interceptors.response.use(
  (res) => res,
  async (err) => {
    // 检测网络/超时错误（Render 休眠的典型症状）
    const isNetworkError = !err.response &&
      (err.code === 'ECONNABORTED' || err.code === 'ERR_NETWORK' ||
       err.message?.includes('timeout') || err.message?.includes('Network Error'));

    if (isNetworkError && err.config && !err.config._retried) {
      err.config._retried = true;
      await wakeUpBackend();
      return api(err.config);  // 重试
    }

    let msg = err.response?.data?.detail || err.message || '请求失败';
    // FastAPI 422 验证错误时 detail 是数组，需要提取第一条信息
    if (Array.isArray(msg)) {
      msg = msg.map((d: { msg?: string }) => d.msg || JSON.stringify(d)).join('; ');
    }
    if (typeof msg !== 'string') msg = String(msg);
    console.error('[API Error]', msg);
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

export const getDashboardCharts = async (sessionId: string, chartConfigs?: Record<string, unknown>[]) => {
  const { data } = await api.post('/dashboard/charts', { session_id: sessionId, charts: chartConfigs });
  return data;
};

/** 获取仪表盘图表（ECharts 格式） */
export const getDashboardECharts = async (sessionId: string, chartConfigs?: Record<string, unknown>[]): Promise<{ success: boolean; charts: EChartItem[] }> => {
  const { data } = await api.post('/dashboard/echarts', { session_id: sessionId, charts: chartConfigs });
  return data;
};

export const getDashboardRecommend = async (sessionId: string, apiKey: string, baseUrl?: string, model?: string) => {
  const { data } = await api.post('/dashboard/recommend', {
    session_id: sessionId, api_key: apiKey, base_url: baseUrl, model,
  });
  return data;
};

export const getAiLayout = async (sessionId: string, apiKey: string, baseUrl?: string, model?: string) => {
  const { data } = await api.post('/dashboard/ai-layout', {
    session_id: sessionId, api_key: apiKey, base_url: baseUrl, model,
  });
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

export const chatAnalyze = async (sessionId: string, question: string, apiKey: string, baseUrl?: string, model?: string) => {
  const { data } = await api.post<ChatResponse>('/chat/analyze', {
    session_id: sessionId, question, api_key: apiKey, base_url: baseUrl, model,
  });
  return data;
};

/* ===== 报告 ===== */
export const generateReport = async (sessionId: string, title = '数据分析报告') => {
  const { data } = await api.post<ReportResponse>('/report/generate', { session_id: sessionId, title });
  return data;
};


/** V3: 从 AnalysisPackage 提取扁平指标列表 */
export const generateCards = async (sessionId: string): Promise<{
  success: boolean;
  cards: Array<Record<string, unknown>>;
  meta?: Record<string, unknown>;
  
}> => {
  const { data } = await api.post('/dashboard/cards', { session_id: sessionId });
  return data;
};
/** AI 分析报告 — 提交异步任务（立即返回 task_id） */
export const submitAIReport = async (
  sessionId: string,
  apiKey: string,
  baseUrl?: string,
  model?: string,
): Promise<{ task_id: string; status: string }> => {
  const { data } = await api.post('/report/ai-analyze', {
    session_id: sessionId,
    api_key: apiKey,
    base_url: baseUrl,
    model,
  });
  return data;
};

/** 轮询任务状态 */
export const getAIReportStatus = async (
  taskId: string,
): Promise<{
  task_id: string;
  status: 'pending' | 'processing' | 'done' | 'failed';
  progress: number;
  message: string;
  error?: string;
}> => {
  const { data } = await api.get(`/report/ai-analyze/status/${taskId}`);
  return data;
};

/** 获取任务结果 */
export const getAIReportResult = async (
  taskId: string,
): Promise<AIReportResponse> => {
  const { data } = await api.get(`/report/ai-analyze/result/${taskId}`);
  return data;
};

/** @deprecated 旧同步接口（已废弃，改为 submitAIReport + 轮询模式） */
export const generateAIReport = async (
  sessionId: string,
  apiKey: string,
  baseUrl?: string,
  model?: string,
): Promise<AIReportResponse> => {
  const { data } = await api.post<AIReportResponse>('/report/ai-analyze', {
    session_id: sessionId,
    api_key: apiKey,
    base_url: baseUrl,
    model,
  }, {
    timeout: 300000,
  });
  return data;
};

export default api;

