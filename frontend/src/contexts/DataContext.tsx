/* DataMind AI - 全局数据状态管理 */
import React, { createContext, useContext, useReducer, useEffect, ReactNode } from 'react';
import { createSession } from '../api/client';
import type { ColumnInfo, DataInfo, CleaningStep } from '../types';

export interface AiProviderConfig {
  id: string;
  name: string;
  baseUrl: string;
  model: string;
}

export const AI_PROVIDERS: AiProviderConfig[] = [
  { id: 'deepseek', name: 'DeepSeek', baseUrl: 'https://api.deepseek.com', model: 'deepseek-chat' },
  { id: 'qwen', name: '阿里云通义千问', baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1', model: 'qwen3.7-plus' },
  { id: 'zhipu', name: '智谱 GLM', baseUrl: 'https://open.bigmodel.cn/api/paas/v4', model: 'glm-4-flash' },
  { id: 'moonshot', name: 'Moonshot / Kimi', baseUrl: 'https://api.moonshot.cn/v1', model: 'moonshot-v1-8k' },
  { id: 'openai', name: 'OpenAI', baseUrl: 'https://api.openai.com/v1', model: 'gpt-4o-mini' },
  { id: 'agnes', name: 'Agnes AI', baseUrl: 'https://apihub.agnes-ai.com/v1', model: 'agnes-2.0-flash' },
];

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
  | { type: 'CLEAR_DATA' };

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
  apiKey: '',
  aiProvider: 'deepseek',
  customModel: '',
  customBaseUrl: '',
  loading: false,
  error: null,
  analysis: initialAnalysis,
};

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
    case 'CLEAR_DATA':
      return { ...initialState, sessionId: state.sessionId, apiKey: state.apiKey, aiProvider: state.aiProvider, customModel: state.customModel, customBaseUrl: state.customBaseUrl };
    default:
      return state;
  }
}

interface DataContextType {
  state: DataState;
  dispatch: React.Dispatch<Action>;
}

const DataContext = createContext<DataContextType | undefined>(undefined);

export function DataProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(dataReducer, initialState);

  // 初始化：从 localStorage 恢复 session 或创建新 session
  useEffect(() => {
    const savedSession = localStorage.getItem('sessionId');
    if (savedSession) {
      dispatch({ type: 'SET_SESSION', sessionId: savedSession });
    } else {
      createSession().then((sid) => {
        dispatch({ type: 'SET_SESSION', sessionId: sid });
        localStorage.setItem('sessionId', sid);
      });
    }
  }, []);

  return (
    <DataContext.Provider value={{ state, dispatch }}>
      {children}
    </DataContext.Provider>
  );
}

export function useData(): DataContextType {
  const ctx = useContext(DataContext);
  if (!ctx) throw new Error('useData must be used within DataProvider');
  return ctx;
}
