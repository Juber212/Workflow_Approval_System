/** 管理员 API —— 用户管理 / 组织管理 / 角色管理 / 系统配置 */
import request from './request'

// ==================== 用户管理 ====================

/** 用户列表查询参数 */
export interface UserListParams {
  page?: number
  page_size?: number
  keyword?: string
  organization_id?: number | null
  is_active?: boolean | null
}

/** 用户列表项 */
export interface UserItem {
  id: number
  username: string
  real_name: string
  email: string | null
  phone: string | null
  organization_id: number | null
  organization_name: string | null
  roles: string[]
  is_active: boolean
  created_at: string | null
}

/** 用户列表响应 */
export interface UserListData {
  items: UserItem[]
  total: number
  page: number
  page_size: number
}

/** 新增用户参数 */
export interface UserCreateData {
  username: string
  real_name: string
  password: string
  organization_id: number
  role_ids: number[]
  email?: string | null
  phone?: string | null
}

/** 编辑用户参数 */
export interface UserUpdateData {
  real_name: string
  organization_id: number
  role_ids: number[]
  email?: string | null
  phone?: string | null
}

/** 获取用户列表 */
export async function getUsers(params: UserListParams = {}): Promise<UserListData> {
  const res = await request.get('/users', { params })
  return res.data
}

/** 新增用户 */
export async function createUser(data: UserCreateData): Promise<void> {
  await request.post('/users', data)
}

/** 编辑用户 */
export async function updateUser(id: number, data: UserUpdateData): Promise<void> {
  await request.put(`/users/${id}`, data)
}

/** 启用/禁用用户 */
export async function toggleUserStatus(id: number, isActive: boolean): Promise<void> {
  await request.put(`/users/${id}/status`, { is_active: isActive })
}

/** 重置用户密码 */
export async function resetUserPassword(id: number, newPassword: string): Promise<void> {
  await request.put(`/users/${id}/reset-password`, { new_password: newPassword })
}

// ==================== 组织/角色选项 ====================

/** 组织选项 */
export interface OrgOption {
  id: number
  name: string
  is_active: boolean
}

/** 角色选项 */
export interface RoleOption {
  id: number
  code: string
  name: string
}

/** 获取组织列表（选项用） */
export async function getOrgOptions(): Promise<OrgOption[]> {
  const res = await request.get('/organizations/options')
  return res.data
}

/** 获取角色列表（选项用） */
export async function getRoleOptions(): Promise<RoleOption[]> {
  const res = await request.get('/roles/options')
  return res.data
}

// ==================== 用户搜索（人员选择器用） ====================

/** 用户搜索项 */
export interface UserSearchItem {
  id: number
  username: string
  real_name: string
  organization_id: number | null
  organization_name: string | null
}

/** 按关键词搜索用户（远程搜索） */
export async function searchUsers(keyword: string, limit = 20): Promise<UserSearchItem[]> {
  const res = await request.get('/users/search', { params: { keyword, limit } })
  return res.data
}

// ==================== 组织管理 ====================

/** 组织列表项 */
export interface OrgItem {
  id: number
  name: string
  description: string | null
  is_active: boolean
  user_count: number
  manager_name: string | null
  created_at: string | null
}

/** 组织列表参数 */
export interface OrgListParams {
  page?: number
  page_size?: number
  is_active?: boolean | null
}

/** 组织列表 */
export async function getOrganizations(params: OrgListParams = {}): Promise<{ items: OrgItem[]; total: number }> {
  const res = await request.get('/organizations', { params })
  return res.data
}

/** 新增组织 */
export async function createOrganization(data: { name: string; description?: string | null }): Promise<void> {
  await request.post('/organizations', data)
}

/** 编辑组织 */
export async function updateOrganization(id: number, data: { name: string; description?: string | null }): Promise<void> {
  await request.put(`/organizations/${id}`, data)
}

/** 启用/停用组织 */
export async function toggleOrgStatus(id: number, isActive: boolean): Promise<void> {
  await request.put(`/organizations/${id}/status`, { is_active: isActive })
}

// ==================== 角色管理（V1 只读） ====================

/** 角色列表项 */
export interface RoleItem {
  id: number
  name: string
  code: string
  description: string | null
  user_count: number
}

/** 获取角色列表 */
export async function getRoles(): Promise<RoleItem[]> {
  const res = await request.get('/roles')
  return res.data
}

// ==================== 系统配置 ====================

/** 配置项 */
export interface ConfigItem {
  id: number
  config_key: string
  config_value: string
  description: string | null
}

/** 获取配置列表 */
export async function getConfigs(): Promise<ConfigItem[]> {
  const res = await request.get('/configs')
  return res.data
}

/** 批量更新配置 */
export async function updateConfigs(items: { id: number; config_value: string }[]): Promise<void> {
  await request.put('/configs', { items })
}
