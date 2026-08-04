/* DataMind AI - 全局数据状态管理 */
import React, { createContext, useContext, useReducer, useEffect, useCallback, ReactNode } from 'react';
import { createSession, listDatasets } from '../api/client';
import type { ColumnInfo, DataInfo, CleaningStep } from '../types';

export interface AiProviderConfig {
  id: string;
  name: string;
  baseUrl: string;
  model: string;
}

export const AI_PROVIDERS: AiProviderConfig[] = [
  { id: 'ppio', name: 'PPIO 派欧云', baseUrl: 'https://api.ppio.ai/v1', model: 'deepseek-chat' },
  { id: 'deepseek', name: 'DeepSeek', baseUrl: 'https://api.deepseek.com', model: 'deepseek-chat' },
  { id: 'qwen', name: '阿里云通义千问', baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1', model: 'qwen3.7-plus' },
  { id: 'zhipu', name: '智谱 GLM', baseUrl: 'https://open.bigmodel.cn/api/paas/v4', model: 'glm-4-flash' },
  { id: 'moonshot', name: 'Moonshot / Kimi', baseUrl: 'https://api.moonshot.cn/v1', model: 'moonshot-v1-8k' },
  { id: 'openai', name: 'OpenAI', baseUrl: 'https://api.openai.com/v1', model: 'gpt-4o-mini' },
  { id: 'agnes', name: 'Agnes AI', baseUrl: 'https://apihub.agnes-ai.com/v1', model: 'agnes-2.0-flash' },
];

export interface DatasetInfo {
  dataset_id: string;
  file_name: string;
  file_size_bytes: number;
  rows: number;
  columns: string[];
  column_info: ColumnInfo[];
  preview: Record<string, unknown>[];
  uploaded_at: number;
  is_active?: boolean;
  // 多表合并宽表标记
  is_merged?: boolean;
  sources?: string[];
  merge_keys?: string[];
}

interface AnalysisState {
  tab: string;
  stats: Record<string, unknown>[] | null;
  heatmap: Record<string, unknown> | null;
  chartFigure: Record<string, unknown> | null;
  chartType: string;
  chartX: string;
  chartY: string;
  chatHistory: { role: string; content: string }[];
  insights: string;
  quickInsights: string[];
  computeResult: string;
  savedCount: number;
}

interface DataState {
  sessionId: string;
  fileName: string;
  rows: number;
  columns: number;
  preview: Record<string, unknown>[];
  columnInfo: ColumnInfo[];
  dataInfo: DataInfo | null;
  cleaningHistory: CleaningStep[];
  apiKey: string;
  aiProvider: string;  // ID of selected AI provider
  customModel: string;  // 用户自定义模型名（为空则用服务商预设默认值，如 qwen-plus → qwen-max）
  customBaseUrl: string;  // 用户自定义 API 地址（为空则用服务商预设 baseUrl，用于百炼新版等需要 WorkspaceId 的场景）
  loading: boolean;
  error: string | null;
  analysis: AnalysisState;
  // ===== 多数据集管理（顶层 fileName/rows/columns/preview/columnInfo 始终代表 active 数据集，下游零改）=====
  datasets: DatasetInfo[];
  activeDatasetId: string | null;
  usedBytes: number;
  quotaBytes: number;
}

type Action =
  | { type: 'SET_SESSION'; sessionId: string }
  | { type: 'SET_DATA'; payload: Partial<DataState> }
  | { type: 'SET_PREVIEW'; preview: Record<string, unknown>[] }
  | { type: 'SET_CLEANING_HISTORY'; history: CleaningStep[] }
  | { type: 'SET_API_KEY'; apiKey: string }
  | { type: 'SET_AI_PROVIDER'; aiProvider: string }
  | { type: 'SET_CUSTOM_MODEL'; customModel: string }
  | { type: 'SET_CUSTOM_BASE_URL'; customBaseUrl: string }
  | { type: 'SET_LOADING'; loading: boolean }
  | { type: 'SET_ERROR'; error: string | null }
  | { type: 'SET_ANALYSIS'; payload: Partial<AnalysisState> }
  | { type: 'CLEAR_DATA' }
  | { type: 'ADD_DATASET'; payload: DatasetInfo }
  | { type: 'SELECT_DATASET'; datasetId: string }
  | { type: 'REMOVE_DATASET'; datasetId: string }
  | { type: 'SET_DATASETS'; datasets: DatasetInfo[] }
  | { type: 'SET_QUOTA'; usedBytes: number; quotaBytes: number };

const initialAnalysis: AnalysisState = {
  tab: 'stats',
  stats: null,
  heatmap: null,
  chartFigure: null,
  chartType: 'bar',
  chartX: '',
  chartY: '',
  chatHistory: [],
  insights: '',
  quickInsights: [],
  computeResult: '',
  savedCount: 0,
};

const initialState: DataState = {
  sessionId: '',
  fileName: '',
  rows: 0,
  columns: 0,
  preview: [],
  columnInfo: [],
  dataInfo: null,
  cleaningHistory: [],
  apiKey: 'sk-SXzLmQOotBHW63Pk6kApIuP2xuw3YBCCqc24nfgLofssxuhE',
  aiProvider: 'ppio',
  customModel: '',
  customBaseUrl: '',
  loading: false,
  error: null,
  analysis: initialAnalysis,
  datasets: [],
  activeDatasetId: null,
  usedBytes: 0,
  quotaBytes: 0,
};

// 把某个数据集的字段回放到顶层（fileName/rows/columns/preview/columnInfo）
// 无 active 数据集时清空顶层，避免删除/刷新后残留旧数据
function replayToTop(state: DataState, ds: DatasetInfo | undefined): Partial<DataState> {
  if (!ds) return { fileName: '', rows: 0, columns: 0, preview: [], columnInfo: [] };
  return {
    fileName: ds.file_name,
    rows: ds.rows,
    columns: ds.columns.length,
    preview: ds.preview,
    columnInfo: ds.column_info,
  };
}

function dataReducer(state: DataState, action: Action): DataState {
  switch (action.type) {
    case 'SET_SESSION':
      return { ...state, sessionId: action.sessionId };
    case 'SET_DATA':
      return { ...state, ...action.payload };
    case 'SET_PREVIEW':
      return { ...state, preview: action.preview };
    case 'SET_CLEANING_HISTORY':
      return { ...state, cleaningHistory: action.history };
    case 'SET_API_KEY':
      return { ...state, apiKey: action.apiKey };
    case 'SET_AI_PROVIDER':
      return { ...state, aiProvider: action.aiProvider, customModel: '', customBaseUrl: '' };  // 切换服务商时清空自定义配置
    case 'SET_CUSTOM_MODEL':
      return { ...state, customModel: action.customModel };
    case 'SET_CUSTOM_BASE_URL':
      return { ...state, customBaseUrl: action.customBaseUrl };
    case 'SET_LOADING':
      return { ...state, loading: action.loading };
    case 'SET_ERROR':
      return { ...state, error: action.error };
    case 'SET_ANALYSIS':
      return { ...state, analysis: { ...state.analysis, ...action.payload } };
    case 'ADD_DATASET': {
      const datasets = [...state.datasets, action.payload];
      // 仅当该数据集显式 is_active（多 sheet 拆分的首个 sheet）或列表原本为空时才切换 active，
      // 避免批量上传多 sheet 时 active 被逐个覆盖为最后一个
      const makeActive = action.payload.is_active === true || state.datasets.length === 0;
      const activeDatasetId = makeActive ? action.payload.dataset_id : state.activeDatasetId;
      const activeDs = makeActive ? action.payload : (datasets.find(d => d.dataset_id === activeDatasetId) || null);
      return {
        ...state,
        datasets,
        activeDatasetId,
        ...replayToTop(state, activeDs),
      };
    }
    case 'SELECT_DATASET': {
      const ds = state.datasets.find(d => d.dataset_id === action.datasetId);
      return {
        ...state,
        activeDatasetId: action.datasetId,
        ...replayToTop(state, ds),
      };
    }
    case 'REMOVE_DATASET': {
      const datasets = state.datasets.filter(d => d.dataset_id !== action.datasetId);
      let next = { ...state, datasets, activeDatasetId: state.activeDatasetId };
      if (state.activeDatasetId === action.datasetId) {
        const nextActive = datasets[0];
        next = {
          ...next,
          activeDatasetId: nextActive ? nextActive.dataset_id : null,
          ...replayToTop(state, nextActive),
        };
      }
      return next;
    }
    case 'SET_DATASETS': {
      // 刷新拉回：替换列表。优先用后端标记的 is_active 挑 active；
      // 若本地已知 activeDatasetId 且它仍在列表里，则以本地为准（兼容多 sheet 切换场景）。
      const localActive = state.activeDatasetId
        ? action.datasets.find(d => d.dataset_id === state.activeDatasetId)
        : undefined;
      const ds = localActive || action.datasets.find(d => d.is_active) || undefined;
      const activeDatasetId = ds ? ds.dataset_id : state.activeDatasetId;
      return {
        ...state,
        datasets: action.datasets,
        activeDatasetId,
        ...replayToTop(state, ds),
      };
    }
    case 'SET_QUOTA':
      return { ...state, usedBytes: action.usedBytes, quotaBytes: action.quotaBytes };
    case 'CLEAR_DATA':
      // 结束会话：清掉 localStorage 里的旧 sessionId，让 ensureValidSession 自然创建全新会话，
      // 避免沿用「已被后端 clear_data 删除」的旧 id（否则 ensureValidSession 直接返回旧 id、新会话语义失效）。
      // 本地 AI 配置（apiKey/aiProvider/customModel/customBaseUrl）跨会话保留，不在此清空。
      localStorage.removeItem('sessionId');
      return { ...initialState, apiKey: state.apiKey, aiProvider: state.aiProvider, customModel: state.customModel, customBaseUrl: state.customBaseUrl };
    default:
      return state;
  }
}

interface DataContextType {
  state: DataState;
  dispatch: React.Dispatch<Action>;
  /** 确保当前有有效 sessionId：有则保留，无则创建新会话并写入 localStorage。
   *  不在初始化 effect 中盲目换新，避免死守旧 id 或误换新 id。 */
  ensureValidSession: () => Promise<string>;
}

const DataContext = createContext<DataContextType | undefined>(undefined);

export function DataProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(dataReducer, initialState);

  // 确保当前有有效 sessionId：有则保留，无则创建新会话并写入 localStorage。
  // 注意：不在挂载时盲目换新 id，仅当 localStorage 无记录时才创建（避免误丢数据）。
  const ensureValidSession = useCallback(async (): Promise<string> => {
    const existing = state.sessionId || localStorage.getItem('sessionId');
    if (existing) {
      if (!state.sessionId) dispatch({ type: 'SET_SESSION', sessionId: existing });
      return existing;
    }
    const sid = await createSession();
    dispatch({ type: 'SET_SESSION', sessionId: sid });
    localStorage.setItem('sessionId', sid);
    return sid;
  }, [state.sessionId, dispatch]);

  // 初始化：从 localStorage 恢复 session 或创建新 session，并全局拉回已上传数据集，
  // 使任意页面（仪表盘/分析/清洗/AI报告）刷新后无需先进入上传页即可拿到 hasData 所需数据。
  useEffect(() => {
    let alive = true;
    (async () => {
      const sid = await ensureValidSession();
      if (!alive || !sid) return;
      try {
        const res = await listDatasets(sid);
        if (!alive) return;
        dispatch({ type: 'SET_DATASETS', datasets: res.datasets });
        const active = res.datasets.find((d) => d.is_active);
        if (active) dispatch({ type: 'SELECT_DATASET', datasetId: active.dataset_id });
      } catch {
        // 会话暂无数据集，忽略；任由页面展示空态
      }
    })();
    return () => { alive = false; };
  }, [ensureValidSession, dispatch]);

  return (
    <DataContext.Provider value={{ state, dispatch, ensureValidSession }}>
      {children}
    </DataContext.Provider>
  );
}

export function useData(): DataContextType {
  const ctx = useContext(DataContext);
  if (!ctx) throw new Error('useData must be used within DataProvider');
  return ctx;
}
