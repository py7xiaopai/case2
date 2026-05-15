# A 股历史行情数据平台开发计划（Linux 版）

## 一、项目目标

开发一个面向 A 股历史行情的完整数据平台，覆盖从数据采集、清洗、入库、分析，到 API 服务、可视化展示、定时更新和容器化部署的全流程。

### 核心目标
- 抓取股票基础信息
- 抓取历史日线行情
- 计算常用技术指标
- 提供数据质量检查
- 提供 REST API
- 提供 Streamlit 可视化看板
- 支持定时增量更新
- 支持数据库迁移
- 支持 Docker 部署

---

## 二、开发环境

### 1. 系统环境
推荐使用 Linux 发行版，例如：
- Ubuntu 22.04+
- Debian 12+
- Rocky Linux 9+
- Arch Linux

### 2. 基础依赖
以 Ubuntu / Debian 为例：

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git mysql-client

如使用 MariaDB 客户端：

sudo apt install -y mariadb-client

如需 Docker：

sudo apt install -y docker.io docker-compose-plugin

3. Python 环境

建议使用 Python 3.10 及以上版本。

创建虚拟环境：

python3 -m venv .venv
source .venv/bin/activate

升级 pip：

python3 -m pip install -U pip

三、项目初始化
1. 创建项目目录

mkdir stock-market-platform
cd stock-market-platform

2. 推荐目录结构

stock-market-platform/
├── pyproject.toml
├── README.md
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/
├── src/
│   └── stock_platform/
│       ├── __init__.py
│       ├── api/
│       ├── crawler/
│       ├── data/
│       ├── db/
│       ├── dashboard/
│       └── scheduler/
├── scripts/
└── tests/

3. 安装项目依赖

开发模式：

python3 -m pip install -e .

如果还未写入 pyproject.toml，可先安装基础依赖：

python3 -m pip install fastapi uvicorn streamlit pandas numpy sqlalchemy alembic requests plotly apscheduler pymysql pytest httpx

四、阶段性开发计划
阶段 1：数据库与基础模型
目标

完成数据库初始化、表结构设计和 ORM 模型定义，为后续抓取和分析打基础。
主要任务

    设计股票基础信息表
    设计历史日线行情表
    设计技术指标表
    设计交易日历表
    配置 SQLAlchemy
    配置 Alembic 迁移

Linux 执行步骤
1）创建数据库

mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS stock_market CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

2）复制环境变量模板

cp .env.example .env

3）设置 Python 路径

export PYTHONPATH=src

4）生成迁移文件

alembic revision --autogenerate -m "init tables"

5）执行数据库迁移

alembic upgrade head

阶段输出

    数据库可用
    表结构已创建
    ORM 模型可正常操作

阶段 2：股票基础信息抓取
目标

抓取沪深 A 股股票基础信息并入库。
主要任务

    抓取股票列表
    统一股票代码格式
    处理重复数据
    补全市场字段
    写入数据库

Linux 执行方式

PYTHONPATH=src python3 -c "
from stock_platform.db.engine import SessionLocal
from stock_platform.crawler.stock_list import crawl_stock_list

session = SessionLocal()
count = crawl_stock_list(session)
session.close()
print(f'成功获取 {count} 只股票')
"

阶段输出

    股票基础信息表有数据
    可按股票代码或名称查询
    支持市场分类

阶段 3：历史日线行情抓取
目标

抓取股票历史日线行情并批量入库。
主要任务

    按股票代码抓取历史行情
    控制请求频率
    实现失败重试
    支持前复权 / 后复权 / 不复权
    批量入库与去重

Linux 执行方式

PYTHONPATH=src python3 -c "
from stock_platform.db.engine import SessionLocal
from stock_platform.crawler.daily_price import crawl_all_stocks_daily_prices

session = SessionLocal()
count = crawl_all_stocks_daily_prices(session, years_back=3)
session.close()
print(f'成功抓取 {count} 条日线数据')
"

阶段输出

    历史行情表有数据
    支持按日期区间查询
    可用于指标计算和图表展示

阶段 4：技术指标计算
目标

基于历史行情计算常用技术指标。
主要任务

    计算 MA
    计算 MACD
    计算 RSI
    计算 Bollinger Bands
    保存指标结果
    支持全量和增量计算

Linux 执行方式

PYTHONPATH=src python3 -c "
from stock_platform.db.engine import SessionLocal
from stock_platform.data.indicators import calculate_all_indicators

session = SessionLocal()
count = calculate_all_indicators(session)
session.close()
print(f'成功计算 {count} 条技术指标')
"

阶段输出

    指标表有数据
    可用于 API 和 Dashboard 展示
    为后续分析提供计算结果

阶段 5：数据质量检查
目标

建立数据质量机制，确保数据可信。
主要任务

    空值检查
    重复检查
    异常值检查
    交易日缺口检查
    生成质量报告

Linux 执行方式

PYTHONPATH=src python3 -c "
from stock_platform.db.engine import SessionLocal
from stock_platform.data.etl import data_quality_check

session = SessionLocal()
result = data_quality_check(session)
session.close()
print(result)
"

阶段输出

    可发现数据异常
    可生成质量报告
    可用于后续告警和修复

阶段 6：FastAPI 接口开发
目标

提供稳定的 REST API 服务。
主要任务

    股票搜索接口
    股票详情接口
    涨跌幅排行接口
    成交量排行接口
    数据质量接口
    数据导出接口

Linux 启动方式

PYTHONPATH=src uvicorn stock_platform.api.main:app --host 0.0.0.0 --port 8000 --reload

访问方式

    Swagger UI：http://127.0.0.1:8000/docs
    ReDoc：http://127.0.0.1:8000/redoc

阶段输出

    API 可访问
    接口返回正常
    文档可用

阶段 7：Streamlit Dashboard
目标

实现一个可交互的数据可视化页面。
主要任务

    股票搜索
    个股详情页
    K 线图
    成交量图
    MACD 图
    市场总览
    多股对比

Linux 启动方式

PYTHONPATH=src streamlit run src/stock_platform/dashboard/app.py --server.port 8501 --server.address 0.0.0.0

访问方式

    Dashboard：http://127.0.0.1:8501

阶段输出

    页面可访问
    图表正常渲染
    交互功能可用

阶段 8：定时任务与增量更新
目标

让平台具备自动更新能力。
主要任务

    每日增量更新行情
    每月更新股票列表
    每周重算技术指标
    记录执行日志

Linux 启动方式

PYTHONPATH=src python3 -m stock_platform.scheduler.tasks

阶段输出

    定时任务可运行
    数据可自动更新
    具备持续维护能力

阶段 9：测试与验证
目标

保证核心逻辑稳定可靠。
主要任务

    技术指标测试
    API 接口测试
    数据处理测试
    边界条件测试

Linux 执行方式

PYTHONPATH=src pytest -v

阶段输出

    单元测试可通过
    核心模块稳定
    可用于后续回归验证

阶段 10：Docker 容器化部署
目标

实现一键启动和环境隔离。
主要任务

    编写 Dockerfile
    编写 docker-compose.yml
    启动 MySQL
    启动 API
    启动 Dashboard
    启动 Scheduler

Linux 启动方式

docker compose up -d --build

查看状态：

docker compose ps

查看日志：

docker compose logs -f api
docker compose logs -f dashboard
docker compose logs -f scheduler
docker compose logs -f mysql

停止服务：

docker compose down

如需连数据卷一起删除：

docker compose down -v

阶段输出

    容器化运行正常
    可迁移到服务器部署
    便于演示和维护

五、推荐开发顺序

建议按下面顺序推进：

# 1. 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 2. 安装依赖
python3 -m pip install -U pip
python3 -m pip install -e .

# 3. 配置环境变量
cp .env.example .env

# 4. 创建数据库
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS stock_market CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 5. 设置路径
export PYTHONPATH=src

# 6. 数据库迁移
alembic revision --autogenerate -m "init tables"
alembic upgrade head

# 7. 初始化交易日历
python3 scripts/seed_trading_calendar.py

# 8. 抓取股票列表
python3 -c "..."

# 9. 抓取历史行情
python3 -c "..."

# 10. 计算技术指标
python3 -c "..."

# 11. 启动 API
uvicorn stock_platform.api.main:app --host 0.0.0.0 --port 8000 --reload

# 12. 启动 Dashboard
streamlit run src/stock_platform/dashboard/app.py --server.port 8501 --server.address 0.0.0.0

# 13. 启动调度器
python3 -m stock_platform.scheduler.tasks

# 14. 运行测试
pytest -v

六、里程碑规划
Milestone 1：基础环境完成

    Linux 环境配置完成
    Python 虚拟环境可用
    数据库可连接
    项目结构建立完成

Milestone 2：数据层完成

    股票列表抓取完成
    历史行情抓取完成
    技术指标计算完成
    数据质量检查完成

Milestone 3：服务层完成

    FastAPI 接口可用
    Dashboard 可用
    查询与展示流程打通

Milestone 4：工程化完成

    Alembic 迁移可用
    定时任务可用
    测试可用
    Docker 可用

七、Linux 开发注意事项
1. 统一使用 python3

建议不要混用 python 和 python3，统一使用：

python3
python3 -m pip

2. 激活虚拟环境

Linux 下使用：

source .venv/bin/activate

3. 设置 PYTHONPATH

由于项目采用 src 布局，建议每次运行命令前设置：

export PYTHONPATH=src

或者直接单条命令指定：

PYTHONPATH=src python3 ...

4. 服务监听地址

如果需要局域网访问，请使用：

--host 0.0.0.0

和：

--server.address 0.0.0.0

5. 数据库客户端

如果 mysql 命令不可用，先安装客户端：

sudo apt install -y mysql-client

八、建议开发节奏

如果按一周推进，可以这样安排：

    第 1 天：环境准备 + 数据库 + 项目结构
    第 2 天：股票列表抓取
    第 3 天：历史行情抓取
    第 4 天：技术指标 + 数据质量
    第 5 天：FastAPI 接口
    第 6 天：Streamlit Dashboard
    第 7 天：定时任务 + 测试 + Docker

九、后续优化方向

    接入更完整的交易日历源
    支持分钟级行情
    增加财务数据模块
    增加因子分析
    增加 Redis 缓存
    增加异步抓取
    增加 CI/CD 自动化流程
    增加数据告警与监控

十、总结

该项目的 Linux 版开发流程建议按以下思路推进：

    搭建开发环境
    建立数据库和模型
    完成数据抓取
    完成技术指标和质量检查
    完成 API 和 Dashboard
    加入定时更新
    加入测试和 Docker 部署

