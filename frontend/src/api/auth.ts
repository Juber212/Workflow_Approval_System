/** 认证 API —— 登录 / 获取当前用户 / 退出 */
import request from './request'
import type { UserInfo } from '@/types/user'

/** 登录请求参数 */
export interface LoginParams {
  username: string
  password: string
}

/** 登录响应（后端 data 字段） */
interface LoginData {
  token: string
  user_id: number
  username: string
  real_name: string
  roles: string[]
  organization_id: number | null
  organization_name: string | null
  must_change_password: boolean  // 首次登录是否强制改密码
}

/** 用户登录 */
export async function loginApi(params: LoginParams): Promise<LoginData> {
  const res = await request.post('/auth/login', params)
  return res.data
}

/** 获取当前用户信息 */
export async function getMeApi(): Promise<{
  user_id: number
  username: string
  real_name: string
  email: string | null
  phone: string | null
  roles: string[]
  organization_id: number | null
  organization_name: string | null
  has_signature: boolean
  must_change_password: boolean
}> {
  const res = await request.get('/auth/me')
  return res.data
}

/** 退出登录 */
export async function logoutApi(): Promise<void> {
  await request.post('/auth/logout')
}

/** 修改自己的密码（强制改密场景可省略旧密码） */
export async function changePasswordApi(data: { old_password?: string; new_password: string }): Promise<void> {
  await request.put('/auth/password', data)
}

/** 更新个人资料（邮箱/手机号） */
export async function updateProfileApi(data: { email?: string; phone?: string }): Promise<void> {
  await request.put('/auth/profile', data)
}

/** 上传签名图片（multipart/form-data） */
export async function uploadSignatureApi(file: File): Promise<{ signature_url: string }> {
  const form = new FormData()
  form.append('file', file)
  const res = await request.post('/auth/signature', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return res.data
}

/** 将后端返回的用户数据转为前端 UserInfo 格式 */
export function toUserInfo(data: {
  user_id: number
  username: string
  real_name: string
  email?: string | null
  phone?: string | null
  roles: string[]
  organization_id: number | null
  organization_name: string | null
  must_change_password?: boolean
  has_signature?: boolean
}): UserInfo {
  return {
    id: data.user_id,
    username: data.username,
    real_name: data.real_name,
    email: data.email ?? null,
    phone: data.phone ?? null,
    organization_id: data.organization_id,
    organization_name: data.organization_name,
    roles: data.roles,
    must_change_password: data.must_change_password ?? false,
    has_signature: data.has_signature ?? false,
  }
}
