export type AccountStatus =
  | 'WAIT_LOGIN'
  | 'ACTIVE'
  | 'IN_USE'
  | 'LOGIN_EXPIRED'
  | 'DISABLED'
  | 'ERROR'

export type TaskStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED'

export type SessionStatus =
  | 'CREATING'
  | 'READY'
  | 'LOGIN'
  | 'RUNNING'
  | 'COMPLETED'
  | 'FAILED'
  | 'CLOSED'

export type GridStatus = 'ONLINE' | 'OFFLINE' | 'ERROR' | 'UNKNOWN'

// ── Pagination ──

export interface PaginatedResponse<T> {
  page: number
  page_size: number
  total: number
  total_pages: number
}

export interface AccountListResponse extends PaginatedResponse<Account> {
  accounts: Account[]
}

export interface TaskListResponse extends PaginatedResponse<Task> {
  tasks: Task[]
}

export interface ScheduleListResponse extends PaginatedResponse<Schedule> {
  schedules: Schedule[]
}

export interface PaginationParams {
  page?: number
  page_size?: number
}

export interface AccountListParams extends PaginationParams {
  status?: string
  platform?: string
}

export interface TaskListParams extends PaginationParams {
  status?: string
  type?: string
  account_id?: number
}

export interface ScheduleListParams extends PaginationParams {
  enabled?: boolean
  task_type?: string
  account_id?: number
}

export interface GridInstance {
  id: number
  name: string
  hub_url: string
  novnc_base_url: string | null
  status: GridStatus
  max_sessions: number
  notes: string
  created_at: string | null
  updated_at: string | null
}

export interface Account {
  id: number
  name: string
  platform: string
  profile_path: string
  status: AccountStatus
  notes: string
  login_indicator: string | null
  grid_id: number | null
  grid?: GridInstance
  last_login_at: string | null
  last_check_at: string | null
  last_used_at: string | null
  created_at: string | null
  updated_at: string | null
}

export interface BrowserSession {
  id: number
  account_id: number
  grid_session_id: string | null
  novnc_url: string | null
  status: SessionStatus
  created_at: string | null
  closed_at: string | null
}

export interface Task {
  id: number
  account_id: number
  type: string
  params: string
  status: TaskStatus
  result: string | null
  error: string | null
  retry_count: number
  max_retries: number
  retry_delay_seconds: number
  artifact_paths: string[]
  created_at: string | null
  started_at: string | null
  completed_at: string | null
}

export interface Schedule {
  id: number
  name: string
  cron: string
  task_type: string
  params: string
  account_id: number | null
  enabled: boolean
  last_run_at: string | null
  next_run_at: string | null
  created_at: string | null
  updated_at: string | null
}

export interface TaskTypeMeta {
  type: string
  description: string
  params_template: Record<string, unknown>
}

export interface LoginStartResponse {
  session: BrowserSession
  novnc_url: string
  instructions: string
}

export interface LoginCompleteResponse {
  status: 'ok' | 'retry'
  message: string
}

export interface GridCheckResult {
  grid_id: number
  name: string
  hub_url: string
  status: GridStatus
  nodes: number
  ready: boolean
}

// ── Session v2 ──

export interface SessionV2Account {
  id: number
  session_id: number
  account_id: number
  platform: string
  bound_at: string | null
  account: Account
}

export type SessionV2Status = 'IDLE' | 'CREATING' | 'READY' | 'LOGIN' | 'ACTIVE' | 'CLOSED' | 'FAILED'

export interface SessionV2 {
  id: number
  name: string
  node_id: number
  grid_session_id: string | null
  status: SessionV2Status
  profile_path: string
  novnc_url: string | null
  created_at: string | null
  closed_at: string | null
  accounts: SessionV2Account[]
}

export interface SessionHealth {
  session_id: number
  status: string
  alive: boolean
  driver_exists: boolean
  grid_session_id: string | null
}
