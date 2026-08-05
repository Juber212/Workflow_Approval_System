# 首页「发起/归档趋势」图 设计文档

> 日期：2026-08-05
> 状态：已获用户批准，待实现
> 关联：性能优化主线（2026-08-05）——新图表必须保证大数据量下不拖慢首页

---

## 一、背景与目标

首页现有 4 张统计卡片 + 各所饼图/柱状图 + 卡点追踪 + 我的待办，均为**当前快照**，没有时间维度。管理者无法看到业务量随时间的增长与结案趋势。

目标：新增一张「发起量 vs 归档量」双折线趋势图，按月/年粒度对比，直观反映「进（新增）与出（归档）」，定位业务积压信号。

## 二、功能形态

首页统计卡片下方新增**全宽卡片**「发起/归档趋势」：

- **双折线**：发起量（蓝 #409EFF 实线）+ 归档量（绿 #67C23A 虚线）
- **粒度切换**：月度 / 年度（卡片头部 Tab）
- **月度**：默认近 12 个月；头部「年份」下拉可切任意历史年份（选年份 → 该年 12 个月）
- **年度**：全部年份，无年份选择
- **跟随现有 项目/方案 Tab**：切 Tab 重新拉取，两套数据独立
- 空态：无数据时显示「暂无数据」

## 三、后端设计

### 3.1 新接口（独立，不塞进现有 /dashboard 大接口）

```
GET /api/v1/dashboard/trends
参数：
  granularity: "month" | "year"     必填
  category:    "project" | "proposal"  必填
  year:        number | null         仅 month 粒度；省略 = 近 12 个月，指定 = 该年 12 个月
```

响应：

```json
{
  "granularity": "month",
  "periods": [
    { "period": "2026-08", "label": "2026年8月", "initiated": 5, "completed": 3 }
  ]
}
```

- `period`：month 粒度 `"YYYY-MM"`；year 粒度 `"YYYY"`
- `label`：中文化标签（"2026年8月" / "2026年"）
- 无数据时间段补 0，保证折线连续

### 3.2 实现位置

- `app/services/dashboard_service.py` 新增 `get_flow_trends(db, granularity, category, year)` + 私有辅助
- `app/schemas/dashboard.py` 新增 `TrendPoint` / `TrendData`
- `app/api/dashboard.py` 新增 `GET /dashboard/trends` 端点

### 3.3 SQL 实现

两个聚合查询，Python 层合并补零：

- 发起量：`SELECT DATE_FORMAT(initiated_at, 粒度) m, COUNT(*) FROM flow_instances WHERE 口径过滤 [AND initiated_at >= 范围] GROUP BY m`
- 归档量：`SELECT DATE_FORMAT(completed_at, 粒度) m, COUNT(*) FROM flow_instances WHERE 口径过滤 AND completed_at IS NOT NULL [AND completed_at >= 范围] GROUP BY m`
- 口径过滤：**沿用现有 proposal_tpl_ids 集合逻辑**（template_id 判断，与统计卡片完全一致，保证数字对得上）
- month 范围：近 12 个月 = `>= 当月首日 - 11 个月`；指定年份 = `>= 该年1月1日 AND < 次年1月1日`

## 四、性能方案

| 场景 | 策略 |
|------|------|
| 月度近 12 个月 / 指定年份 | `initiated_at`/`completed_at` 范围过滤，走新增单列索引，扫描行数可控 |
| 年度全历史 | 全表 GROUP BY 两列，几十万级数百毫秒可接受 |
| 百万级年度 | **观察项**：函数包裹的 GROUP BY 无法用索引分组，届时再评估（如缓存/物化） |

### 4.1 新增索引（预防项，已获用户批准）

`app/models/flow_instance.py` 的 `__table_args__` 追加：

- `Index("idx_initiated_at", "initiated_at")`
- `Index("idx_completed_at", "completed_at")`

配套 Alembic 迁移（在 `b1c2d3e4f5a6` 之后，新 revision），upgrade 建索引、downgrade 删索引。索引名与既有 `idx_status` / `idx_initiator_status` 等不冲突。

## 五、前端设计

### 5.1 新组件 `frontend/src/views/dashboard/components/TrendChart.vue`

- 纯 SVG 手绘双折线，**不引 ECharts**，与现有 PieChart/BarChart 风格统一
- props：`points: TrendPoint[]`（含 label/initiated/completed）
- 复用 BarChart 的 `niceMax` 思路做 Y 轴刻度；图例复用 `vbar-legend` 样式
- 双线：发起量实线圆点 + 归档量虚线圆点，点上方标数值
- 空态「暂无数据」

### 5.2 API 与挂载

- `frontend/src/api/dashboard.ts`：新增 `TrendPoint`/`TrendData` 类型 + `getDashboardTrends(params)`
- `frontend/src/views/dashboard/index.vue`：统计卡片下方新增全宽卡片，头部含粒度 Tab + 月度年份下拉；跟随 catTab 切换拉取

## 六、测试

- 后端单元测试（`tests/unit/test_dashboard_service.py` 扩展）：
  - 近 12 个月补零（无数据月返回 0）
  - 指定年份返回该年 12 个月
  - 年度聚合返回全部年份
  - 项目/方案口径正确（沿用 proposal_tpl_ids）
- 前端：`vue-tsc` 0 错误 + `build` 通过

## 七、影响范围

| 层 | 文件 | 类型 |
|----|------|------|
| 后端 | `app/api/dashboard.py` | 修改（+1 端点） |
| 后端 | `app/services/dashboard_service.py` | 修改（+趋势查询） |
| 后端 | `app/schemas/dashboard.py` | 修改（+类型） |
| 后端 | `app/models/flow_instance.py` | 修改（+2 索引） |
| 后端 | `alembic/versions/*.py` | 新增（1 迁移） |
| 后端 | `tests/unit/test_dashboard_service.py` | 修改（+测试） |
| 前端 | `frontend/src/api/dashboard.ts` | 修改 |
| 前端 | `frontend/src/views/dashboard/components/TrendChart.vue` | 新增 |
| 前端 | `frontend/src/views/dashboard/index.vue` | 修改 |

**旧功能影响：无。** 纯新增卡片 + 新接口，不动现有查询与 UI。
