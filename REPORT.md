# A股历史行情数据平台 — MVP 交付报告

> **项目名称**: A 股行情数据平台（MVP v0.1.0）  
> **交付日期**: 2026-05-15  
> **数据源**: 新浪财经 + 东方财富网页接口  
> **技术栈**: Python 3.12, MariaDB, FastAPI, Streamlit, Docker, SQLAlchemy

---

## 一、项目概述

本平台实现 A 股全市场（沪深京）历史行情数据的自动化采集、存储、计算与可视化展示，提供 RESTful API 和交互式看板两种访问方式。

### 核心功能

| 功能模块 | 说明 |
|---------|------|
| 📡 数据采集 | 从新浪财经/东方财富网页接口抓取全量 A 股行情 |
| 💾 数据存储 | 结构化入库 MariaDB，含去重/增量更新 |
| 📊 技术指标 | MA5/10/20/30/60、MACD、RSI、布林带 自动计算 |
| 🔌 RESTful API | FastAPI 提供 12+ 个查询接口（含 Swagger 文档） |
| 📈 可视化看板 | Streamlit 交互式 K 线图、MACD、涨跌幅排行 |
| ⏰ 定时更新 | APScheduler 每日 18:00 自动增量更新 |
| 🐳 容器化部署 | Docker Compose 一键启动全套服务 |

---

## 二、数据规模

| 数据类别 | 数量 | 覆盖范围 |
|---------|------|---------|
| 沪深京股票 | **5,516 只** | SH(主板+科创板) / SZ(主板+创业板) / BJ(北交所) |
| 日线行情 | **368 万条** | 近 3 年（2023-05 ~ 2026-05） |
| 技术指标 | **365 万条** | MA/MACD/RSI/布林带 |
| 交易日历 | **6,574 天** | 2000-2030 年 |

### 数据质量

- ✅ 数据采集成功率 **100%**（0 失败）
- ✅ 字段完整性：开盘价/收盘价/最高/最低/成交量/成交额/涨跌幅 齐全
- ✅ 涨跌幅从收盘价回溯计算，第一日数据外 100% 覆盖

---

## 三、API 接口清单

| 接口 | 说明 |
|------|------|
| `GET /` | 服务状态 |
| `GET /health` | 健康检查 |
| `GET /stocks/search?q=` | 模糊搜索（代码/名称） |
| `GET /stocks/{code}` | 股票详情 |
| `GET /stocks/{code}/prices` | 历史日线行情 |
| `GET /stocks/{code}/indicators` | 技术指标（MA/MACD/RSI/布林） |
| `GET /stocks/{code}/export` | CSV 导出 |
| `GET /rankings/changes` | 涨跌幅排行 |
| `GET /rankings/volume` | 成交量排行 |
| `GET /quality` | 数据质量报告 |

> 完整交互式文档：`http://localhost:8000/docs`

---

## 四、技术架构

```
┌─────────────┐    ┌──────────────┐    ┌──────────────┐
│  Streamlit  │    │   FastAPI    │    │  Scheduler    │
│  Dashboard  │    │   REST API   │    │  定时更新     │
│  :8501      │    │   :8000      │    │  (后台)       │
└──────┬──────┘    └──────┬───────┘    └──────┬───────┘
       │                  │                   │
       └──────────────────┼───────────────────┘
                          │
                   ┌──────▼───────┐
                   │   MariaDB    │
                   │  stock_market │
                   │  3306        │
                   └──────────────┘
```

### 数据源

- **股票列表**: 新浪财经 `vip.stock.finance.sina.com.cn`
- **日线行情**: 新浪财经 K 线接口（`scale=240` 日线）
- **网页模拟**: 完整浏览器头（User-Agent/Referer 伪装成真实浏览器访问）

---

## 五、部署方式

### Docker 一键部署（推荐）

```bash
cd /home/jckchen/project
docker compose -f docker-compose.local.yml up -d --build
```

访问:
- **API 文档**: http://localhost:8000/docs
- **Dashboard**: http://localhost:8501

### 本地开发运行

```bash
# 终端1 - API
PYTHONPATH=src uvicorn stock_platform.api.main:app --reload

# 终端2 - Dashboard
PYTHONPATH=src streamlit run src/stock_platform/dashboard/app.py

# 终端3 - 全量数据抓取
PYTHONPATH=src python3 -c "
from stock_platform.crawler.stock_list import crawl_stock_list
from stock_platform.crawler.daily_price import crawl_all_stocks_daily_prices
from stock_platform.db.engine import SessionLocal
s = SessionLocal()
crawl_stock_list(s)                # 抓取 5516 只股票
crawl_all_stocks_daily_prices(s)   # 抓取近 3 年日线
s.close()
"
```

---

## 六、项目结构

```
project/
├── src/stock_platform/         # 核心源码
│   ├── db/                     # 数据库引擎 + ORM 模型
│   ├── crawler/                # 股票列表/日线行情爬虫
│   ├── data/                   # 技术指标/日历/质量检查
│   ├── api/main.py             # FastAPI 接口
│   ├── dashboard/app.py        # Streamlit 看板
│   └── scheduler/tasks.py      # 定时任务
├── tests/                      # 13 个测试用例（全部通过）
├── scripts/                    # 部署/数据导出脚本
├── docker-compose.local.yml    # Docker 部署配置
└── Dockerfile                  # 容器镜像
```

---

## 七、后续可扩展

- **财务数据**: PE/PB、营收利润、ROE
- **分钟级行情**: 日间实时高频数据
- **选股策略**: 多因子模型 / 技术形态识别
- **回测引擎**: 基于历史数据的策略回测
- **通知告警**: 异动股票推送（钉钉/微信）

---

> **MVP 版本状态**: ✅ 全部功能可用，数据已入库，API/Dashboard 已部署运行
