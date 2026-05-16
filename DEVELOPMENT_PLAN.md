# A 股行情数据平台 — 开发方案 v2.0

## 一、系统架构

```
┌─────────────────────────────────────────────────────┐
│                   展示层 (Dashboard)                   │
│   搜索面板 | 详情卡片 | K线图 | MACD | 行情表 | 概览    │
├─────────────────────────────────────────────────────┤
│                   服务层 (API)                        │
│   搜索 | 详情 | 行情(表格) | 行情(图表) | 指标 | 排行   │
├─────────────────────────────────────────────────────┤
│                 采集清洗层 (ETL)                       │
│   采集 → 清洗 → 指标计算 → 缺失回填 → 标准化 → 质量检查 │
├─────────────────────────────────────────────────────┤
│                   数据层 (DB)                         │
│   stocks | daily_prices | technical_indicators |     │
│   trading_calendar | crawl_tasks | crawl_logs        │
└─────────────────────────────────────────────────────┘
```

---

## 二、字段定义表

### 2.1 Stock 模型（核心变更）

| 字段 | 类型 | 单位 | 说明 | 现状 |
|------|------|------|------|------|
| `code` | VARCHAR(10) | — | 股票代码 | ✅ 已存 |
| `name` | VARCHAR(100) | — | 股票名称 | ✅ 已存 |
| `exchange` | VARCHAR(10) | — | 交易所：SH / SZ / BJ | 🔄 由 market 字段改名 |
| `industry` | VARCHAR(100) | — | 行业分类（如：白酒、半导体） | ⚠️ 全为 NULL |
| `board` | VARCHAR(20) | — | 板块：主板 / 创业板 / 科创板 / 北交所 | ➕ 新增 |
| `listing_date` | DATE | — | 上市日期 | ⚠️ 全为 NULL |
| `total_market_cap` | DECIMAL(20,4) | **元** | 总市值（前端展示自动转 亿/万亿） | ➕ 新增 |
| `circulating_market_cap` | DECIMAL(20,4) | **元** | 流通市值 | ➕ 新增 |
| `status` | INTEGER | — | 1 正常 / 0 暂停 / -1 退市 | ✅ 已存 |
| `source_updated_at` | DATETIME | — | 数据来源最近更新时间 | ➕ 新增 |

> **说明**：
> - `exchange` 是原 `market` 字段的改名，值域统一为 `SH/SZ/BJ`
> - 市值在数据库以**元**存储，前端按值自动换算为亿/万亿，避免后续计算歧义
> - 后续废弃原 `market` 字段（兼容期内保留）

### 2.2 其他模型

`daily_prices`、`technical_indicators`、`trading_calendar` 维持现有结构不变。

---

## 三、接口清单表

### 3.1 统一返回结构

所有接口统一返回格式，两层语义分离：

```
HTTP 状态码：请求层成功/失败
业务 code：   业务层结果
```

**正常响应**
```json
HTTP 200
{
  "code": 0,
  "data": { ... },
  "message": "ok"
}
```

**业务错误**
```json
HTTP 404
{
  "code": 1001,
  "data": null,
  "message": "股票不存在"
}
```

**服务异常**
```json
HTTP 500
{
  "code": 2000,
  "data": null,
  "message": "内部服务异常"
}
```

### 3.2 接口详情

| 方法 | 路径 | 参数 | 说明 | 变更类型 |
|------|------|------|------|---------|
| GET | `/` | — | 服务状态 | 统一返回结构 |
| GET | `/health` | — | 健康检查 | 统一返回结构 |
| GET | `/stocks/search` | `q`, `exchange`, `limit` | 股票搜索 | 参数扩展 + 统一返回 |
| GET | `/stocks/{code}` | — | 股票详情（含市值/板块等） | 返回字段扩展 |
| GET | `/stocks/{code}/prices` | `page`, `page_size` | 行情列表（表格用） | 新增分页接口 |
| GET | `/stocks/{code}/chart` | `start`, `end` | 行情序列（K线图用） | ➕ 新增 |
| GET | `/stocks/{code}/indicators` | `start`, `end` | 技术指标 | 时间区间参数 |
| GET | `/stocks/{code}/export` | `start`, `end` | CSV 导出 | 统一返回结构 |
| GET | `/rankings/changes` | `date`, `direction`, `limit` | 涨跌幅排行 | 统一返回结构 |
| GET | `/rankings/volume` | `date`, `limit` | 成交量排行 | 统一返回结构 |
| GET | `/quality` | — | 数据质量报告 | 返回字段扩展 |

> 关键变更：行情接口拆分为 `/prices`（分页表格）和 `/chart`（时间区间图表）。

### 3.3 分页结构

```json
{
  "code": 0,
  "data": {
    "items": [...],
    "total": 500,
    "page": 1,
    "page_size": 50,
    "total_pages": 10
  },
  "message": "ok"
}
```

---

## 四、执行阶段与验收标准

### Phase 1：服务层加固

**目标**：API 返回结构定型，参数校验完善，OpenAPI 文档可读。

| 任务 | 文件 | 说明 |
|------|------|------|
| 统一返回结构 | `api/main.py` | BaseResponse / ErrorResponse Pydantic model |
| 全局异常处理 | `api/main.py` | `@app.exception_handler` 捕获未预期异常 |
| 参数校验 | `api/main.py` | 日期格式、code 格式 validator |
| OpenAPI 示例 | `api/main.py` | response_model + examples |
| 日志中间件 | `api/main.py` | 请求方法/路径/耗时/状态码 |
| 限流 | `api/main.py` | slowapi 全局限流 60/min |

**验收标准**：
- [ ] 所有接口返回 `{"code", "data", "message"}` 统一结构
- [ ] 404/500 正确映射业务错误码
- [ ] Swagger UI 可直接查看请求示例和响应模型
- [ ] 非法参数（如日期格式错误）返回明确错误信息
- [ ] 日志中有请求耗时和状态码记录

---

### Phase 2：采集清洗层重构

**目标**：从源头补齐缺失字段，建立可回填机制。

| 任务 | 文件 | 说明 |
|------|------|------|
| Stock 模型扩表 | `db/models.py` | 新增 exchange/board/total_market_cap/circulating_market_cap/source_updated_at |
| Alembic 迁移 | `alembic/versions/` | 生成迁移脚本 |
| 爬虫增强 | `crawler/stock_list.py` | 采集行业、上市日期、市值、板块 |
| 历史回填任务 | `scripts/backfill_stock_info.py` | 对已有 5516 条缺失数据逐条补采（指数退避重试） |
| 清洗层 | `data/cleaning.py` | ➕ 新建：缺失值标记 / 类型标准化 / 空值策略 |
| 定时回填 | `scheduler/tasks.py` | 日频检查缺失字段并回填 |

**验收标准**：
- [ ] 迁移脚本可正常 `alembic upgrade head`
- [ ] 新增字段成功写入且类型正确
- [ ] `industry` 回填率达到 95%+
- [ ] `listing_date` 回填率达到 95%+
- [ ] 回填任务失败自动重试，不阻塞主流程
- [ ] 新采集任务可独立执行：`python scripts/backfill_stock_info.py`

---

### Phase 3：展示层重构

**目标**：详情页完整、图表可用、表格可读。

#### 3a. 数据概览 + 详情卡片

| 任务 | 说明 |
|------|------|
| 侧边栏概览 | 数字千分位 + 单位说明（"家"、"条"） |
| 更新时间展示 | `/quality` 增加 `checked_at` 字段 |
| 详情卡片 | 5 字段 3 列布局，空值显示 "暂无" |
| 市值自动换算 | 元 → 亿元 / 万亿元 |

#### 3b. K 线图优化

| 任务 | 说明 |
|------|------|
| 均线叠加 | MA5(橙) / MA10(蓝) / MA20(紫)，来自 `technical_indicators` |
| 缩放交互 | `rangeslider=True`, `hovermode="x unified"` |
| 成交量着色 | 涨红跌绿，与 K 线颜色联动 |
| 子图间距 | `vertical_spacing=0.08` |

#### 3c. MACD 图优化

| 任务 | 说明 |
|------|------|
| MACD 柱颜色 | 正红负绿 |
| 图例位置 | 右上角 `legend=dict(x=0.98, y=0.98)` |
| 子图重构 | 价格均线移到 K 线图，MACD 专注显示指标 |

#### 3d. 近期行情表优化

| 任务 | 说明 |
|------|------|
| 数字千分位 | `f"{v:,.2f}"` |
| 成交量格式 | 股 → 万手 |
| 涨跌颜色 | 正红负绿 |
| 最近交易日高亮 | 行背景浅黄 |
| 滚动 | 限制高度 `height=400`，内部滚动 |

**验收标准**：
- [ ] 详情页完整显示股票基础信息，无空白字段
- [ ] K 线图可缩放、悬浮提示显示完整
- [ ] MA5/MA10/MA20 线正常叠加
- [ ] MACD 柱红绿分明，图例在右上角
- [ ] 表格数字千分位，涨跌红绿正确
- [ ] 最近交易行高亮
- [ ] 市值自动换算：123456789 → 1.23 亿

---

### Phase 4：性能与稳定性

**目标**：接口响应可控，无明显性能瓶颈。

| 任务 | 说明 |
|------|------|
| 热门股票详情缓存 | `cachetools.TTLCache` 5 分钟缓存 |
| 搜索限长 | 查询词长度 ≥ 2 |
| 图表接口裁剪 | 默认取最近 1 年，最大 5 年 |
| 指标按需计算 | 读库 → 缺失时按需重算 → 回写 |
| Dashboard 超时 | `requests.get(timeout=5)` |
| 爬虫退避 | 指数退避 + jitter（已有配置） |

**验收标准**：
- [ ] 热门股票详情接口响应 < 500ms
- [ ] 搜索接口对短查询（< 2 字符）直接返回空
- [ ] 行情接口大时间范围（> 3 年）响应 < 2s
- [ ] Dashboard 后端宕机时显示友好提示而非白屏

---

## 五、数据回填策略

当前 `stocks` 表 5516 条记录中 `industry` 和 `listing_date` 全部为 NULL。
回填机制分两层：

### 5.1 一次性回填脚本

```bash
python scripts/backfill_stock_info.py
```

- 遍历 `stocks` 表中 `industry IS NULL` 的记录
- 逐个请求东财 API 补充基础信息
- 指数退避：0.1s → 0.2s → 0.4s → 0.8s → 1.6s
- 失败记录到 `crawl_logs` 表，不阻塞后续

### 5.2 定时增量回填

在 `scheduler/tasks.py` 中增加日频任务：

- 每天检查最近新加入的股票是否有缺失字段
- 有则补采，无则跳过

---

## 六、市值自动换算规则

```
值域              显示
< 1 亿            x.xx 万
1 亿 ~ 1 万亿     x.xx 亿
>= 1 万亿         x.xx 万亿
```

实现位置：`dashboard/app.py` 中定义 `format_market_cap(value: float) -> str` 工具函数。
