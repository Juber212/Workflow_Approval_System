export { default as request } from './request'

/** 通用分页响应结构 —— 与后端 PaginatedData 对应 */
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}
