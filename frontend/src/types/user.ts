/** 用户信息类型 */
export interface UserInfo {
  id: number
  username: string
  real_name: string
  email: string | null
  phone: string | null
  organization_id: number | null
  organization_name: string | null
  /** 角色列表，用于前端权限判断 */
  roles: string[]
}
