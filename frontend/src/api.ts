import axios, { AxiosError } from 'axios'

const API_BASE_URL = 'http://localhost:8000'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

export interface QueryRequest {
  question: string
}

export interface QueryResponse {
  success: boolean
  user_question?: string
  sql_query?: string
  results?: Record<string, unknown>[]
  row_count?: number
  relevant_tables?: string[]
  error?: string
}

export interface AnalyzeResponse {
  success: boolean
  question: string
  relevant_tables: Array<{
    table_name: string
    similarity_score: number
    columns: string
  }>
  error?: string
}

export interface TableInfo {
  table_name: string
  schema: Record<string, string>
  sample_data: Record<string, unknown>[]
  row_count: number
}

export interface ColumnDef {
  name: string
  type: string
  nullable?: boolean
  primary_key?: boolean
}

export interface CreateTableRequest {
  database?: string
  table_name: string
  columns: ColumnDef[]
}

export interface CreateTableResponse {
  success: boolean
  message: string
  table_name: string
  database: string
  error?: string
}

export interface TableProfile {
  table_name: string
  database: string
  schema: Record<string, string>
  row_count: number
  column_count: number
  size_mb: number
  columns_detail: Array<{
    name: string
    type: string
    nullable: boolean
    max_length?: number
    precision?: number
  }>
  indexes: Array<{
    name: string
    type: string
  }>
  constraints: Array<{
    name: string
    type: string
  }>
}

export const queryApi = {
  async submitQuery(question: string): Promise<QueryResponse> {
    try {
      const response = await api.post<QueryResponse>('/query', { question })
      return response.data
    } catch (error) {
      const axiosError = error as AxiosError<{ detail: string }>
      throw new Error(axiosError.response?.data?.detail || 'Query failed')
    }
  },

  async analyzeQuery(question: string): Promise<AnalyzeResponse> {
    try {
      const response = await api.post<AnalyzeResponse>('/analyze', { question })
      return response.data
    } catch (error) {
      const axiosError = error as AxiosError<{ detail: string }>
      throw new Error(axiosError.response?.data?.detail || 'Analysis failed')
    }
  },

  async listTables(): Promise<string[]> {
    try {
      const response = await api.get<{ tables: string[] }>('/tables')
      return response.data.tables
    } catch (error) {
      throw new Error('Failed to fetch tables')
    }
  },

  async getTableInfo(tableName: string): Promise<TableInfo> {
    try {
      const response = await api.get<TableInfo>(`/tables/${tableName}`)
      return response.data
    } catch (error) {
      const axiosError = error as AxiosError<{ detail: string }>
      throw new Error(axiosError.response?.data?.detail || 'Failed to fetch table info')
    }
  },

  async refreshEmbeddings(): Promise<{ status: string; message: string }> {
    try {
      const response = await api.post<{ status: string; message: string }>('/refresh-embeddings')
      return response.data
    } catch (error) {
      throw new Error('Failed to refresh embeddings')
    }
  },

  async checkHealth(): Promise<{ status: string }> {
    try {
      const response = await api.get<{ status: string }>('/health')
      return response.data
    } catch (error) {
      throw new Error('Health check failed')
    }
  },

  async createTable(request: CreateTableRequest): Promise<CreateTableResponse> {
    try {
      const response = await api.post<CreateTableResponse>('/create-table', request)
      return response.data
    } catch (error) {
      const axiosError = error as AxiosError<{ detail: string }>
      throw new Error(axiosError.response?.data?.detail || 'Failed to create table')
    }
  },

  async profileTable(tableName: string, database?: string): Promise<{ success: boolean; profile: TableProfile }> {
    try {
      const url = `/profile/${tableName}${database ? `?database=${database}` : ''}`
      const response = await api.get<{ success: boolean; profile: TableProfile }>(url)
      return response.data
    } catch (error) {
      const axiosError = error as AxiosError<{ detail: string }>
      throw new Error(axiosError.response?.data?.detail || 'Failed to profile table')
    }
  },
}
