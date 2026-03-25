// 类型定义 (必须先定义)
export interface Screener {
  id: number;
  name: string;
  display_name: string;
  description: string;
  category: string;
  file_path: string;
  schedule: string;
  created_at: string;
  updated_at: string;
}

export interface Modules {
  screeners: {
    items: string[];
    displayNames: Record<string, string>;
    title: string;
  };
  cron: {
    items: string[];
    displayNames: Record<string, string>;
    schedules: Record<string, string>;
    title: string;
  };
}

export interface CheckResult {
  match: boolean;
  code: string;
  name: string;
  date: string;
  reasons: string[];
  details?: Record<string, any>;
  risk_management?: Record<string, string>;
}

// API 配置
const API_BASE = import.meta.env.VITE_API_BASE || '';

// 认证信息
const AUTH_HEADER = 'Basic ' + btoa('user:neo123');

// 通用请求函数
export async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': AUTH_HEADER,
      ...options.headers,
    },
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }

  return response.json();
}

// API 函数
export const api = {
  // 获取筛选器列表
  getScreeners: () => apiRequest<{ screeners: Screener[]; modules: Modules }>('/api/screeners'),
  
  // 运行筛选器
  runScreener: (name: string, date?: string) => 
    apiRequest<{ success: boolean; stocks_found: number }>(`/api/screeners/${name}/run`, {
      method: 'POST',
      body: JSON.stringify({ date }),
    }),
  
  // 检查单个股票
  checkStock: (screener: string, code: string, date?: string) =>
    apiRequest<CheckResult>('/api/check-stock', {
      method: 'POST',
      body: JSON.stringify({ screener, code, date }),
    }),
  
  // 获取结果
  getResults: (name: string, date: string) =>
    apiRequest<{ results: any[] }>(`/api/screeners/${name}/results?date=${date}`),
  
  // 健康检查
  health: () => apiRequest<{ status: string }>('/api/health'),
};
