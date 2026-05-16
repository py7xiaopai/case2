"""初始化数据库表结构

Revision ID: c50e9b52a39b
Revises:
Create Date: 2025-01-01 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = "c50e9b52a39b"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 股票基础信息表
    op.create_table(
        "stocks",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(10), nullable=False, comment="股票代码"),
        sa.Column("name", sa.String(100), nullable=False, comment="股票名称"),
        sa.Column("market", sa.String(10), nullable=True, comment="市场: SH/SZ/BJ (deprecated, use exchange)"),
        sa.Column("exchange", sa.String(10), nullable=True, comment="交易所: SH/SZ/BJ"),
        sa.Column("board", sa.String(20), nullable=True, comment="板块: 主板/创业板/科创板/北交所"),
        sa.Column("industry", sa.String(100), nullable=True, comment="行业"),
        sa.Column("listing_date", sa.Date(), nullable=True, comment="上市日期"),
        sa.Column("status", sa.Integer(), nullable=True, default=1, comment="状态: 1正常 0暂停 -1退市"),
        sa.Column("total_market_cap", sa.DECIMAL(20, 4), nullable=True, comment="总市值(元)"),
        sa.Column("circulating_market_cap", sa.DECIMAL(20, 4), nullable=True, comment="流通市值(元)"),
        sa.Column("source_updated_at", sa.DateTime(), nullable=True, comment="数据来源最近更新时间"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("idx_stock_market", "stocks", ["market"])
    op.create_index("idx_stock_exchange", "stocks", ["exchange"])
    op.create_index("idx_stock_board", "stocks", ["board"])

    # 历史日线行情表
    op.create_table(
        "daily_prices",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("stock_id", sa.BigInteger(), sa.ForeignKey("stocks.id"), nullable=False, comment="股票ID"),
        sa.Column("trade_date", sa.Date(), nullable=False, comment="交易日期"),
        sa.Column("adjust_type", sa.Integer(), nullable=True, comment="复权类型: 0不复权 1前复权 2后复权"),
        sa.Column("open_price", sa.DECIMAL(18, 4), nullable=True, comment="开盘价"),
        sa.Column("close_price", sa.DECIMAL(18, 4), nullable=True, comment="收盘价"),
        sa.Column("high_price", sa.DECIMAL(18, 4), nullable=True, comment="最高价"),
        sa.Column("low_price", sa.DECIMAL(18, 4), nullable=True, comment="最低价"),
        sa.Column("volume", sa.BigInteger(), nullable=True, comment="成交量(股)"),
        sa.Column("amount", sa.DECIMAL(20, 2), nullable=True, comment="成交额(元)"),
        sa.Column("pct_change", sa.DECIMAL(10, 4), nullable=True, comment="涨跌幅(%)"),
        sa.Column("change_amount", sa.DECIMAL(10, 4), nullable=True, comment="涨跌额"),
        sa.Column("turnover_rate", sa.DECIMAL(10, 4), nullable=True, comment="换手率(%)"),
        sa.Column("source", sa.String(50), nullable=True, comment="数据来源"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), comment="创建时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stock_id", "trade_date", "adjust_type", name="uq_daily_price_unique"),
    )
    op.create_index("idx_daily_trade_date", "daily_prices", ["trade_date"])
    op.create_index("idx_daily_stock_date", "daily_prices", ["stock_id", "trade_date"])

    # 技术指标表
    op.create_table(
        "technical_indicators",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("stock_id", sa.BigInteger(), sa.ForeignKey("stocks.id"), nullable=True, comment="股票ID"),
        sa.Column("trade_date", sa.Date(), nullable=True, comment="交易日期"),
        sa.Column("ma5", sa.DECIMAL(10, 4), nullable=True, comment="5日均线"),
        sa.Column("ma10", sa.DECIMAL(10, 4), nullable=True, comment="10日均线"),
        sa.Column("ma20", sa.DECIMAL(10, 4), nullable=True, comment="20日均线"),
        sa.Column("ma30", sa.DECIMAL(10, 4), nullable=True, comment="30日均线"),
        sa.Column("ma60", sa.DECIMAL(10, 4), nullable=True, comment="60日均线"),
        sa.Column("macd_dif", sa.DECIMAL(10, 4), nullable=True, comment="DIF"),
        sa.Column("macd_dea", sa.DECIMAL(10, 4), nullable=True, comment="DEA"),
        sa.Column("macd_bar", sa.DECIMAL(10, 4), nullable=True, comment="MACD柱"),
        sa.Column("rsi_6", sa.DECIMAL(10, 4), nullable=True, comment="RSI6"),
        sa.Column("rsi_12", sa.DECIMAL(10, 4), nullable=True, comment="RSI12"),
        sa.Column("rsi_24", sa.DECIMAL(10, 4), nullable=True, comment="RSI24"),
        sa.Column("boll_up", sa.DECIMAL(10, 4), nullable=True, comment="布林上轨"),
        sa.Column("boll_mid", sa.DECIMAL(10, 4), nullable=True, comment="布林中轨"),
        sa.Column("boll_down", sa.DECIMAL(10, 4), nullable=True, comment="布林下轨"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), comment="创建时间"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_indicator_stock_date", "technical_indicators", ["stock_id", "trade_date"])

    # 交易日历表
    op.create_table(
        "trading_calendar",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False, comment="日期"),
        sa.Column("is_open", sa.Integer(), nullable=True, default=1, comment="是否交易日: 1是0否"),
        sa.Column("market", sa.String(10), nullable=True, comment="市场"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), comment="创建时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trade_date"),
    )
    op.create_index("idx_trade_date", "trading_calendar", ["trade_date"])

    # 爬虫任务记录表
    op.create_table(
        "crawl_tasks",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("task_type", sa.String(50), nullable=True, comment="任务类型"),
        sa.Column("status", sa.String(20), nullable=True, comment="状态"),
        sa.Column("start_time", sa.DateTime(), nullable=True, comment="开始时间"),
        sa.Column("end_time", sa.DateTime(), nullable=True, comment="结束时间"),
        sa.Column("total_items", sa.Integer(), nullable=True, comment="总条目数"),
        sa.Column("success_items", sa.Integer(), nullable=True, comment="成功条目数"),
        sa.Column("fail_items", sa.Integer(), nullable=True, comment="失败条目数"),
        sa.Column("error_message", sa.Text(), nullable=True, comment="错误信息"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), comment="创建时间"),
        sa.PrimaryKeyConstraint("id"),
    )

    # 爬虫日志表
    op.create_table(
        "crawl_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.BigInteger(), sa.ForeignKey("crawl_tasks.id"), nullable=True, comment="任务ID"),
        sa.Column("stock_code", sa.String(10), nullable=True, comment="股票代码"),
        sa.Column("url", sa.Text(), nullable=True, comment="请求URL"),
        sa.Column("status_code", sa.Integer(), nullable=True, comment="HTTP状态码"),
        sa.Column("response_time", sa.Float(), nullable=True, comment="响应时间(秒)"),
        sa.Column("error_message", sa.Text(), nullable=True, comment="错误信息"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), comment="创建时间"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("crawl_logs")
    op.drop_table("crawl_tasks")
    op.drop_table("trading_calendar")
    op.drop_table("technical_indicators")
    op.drop_table("daily_prices")
    op.drop_table("stocks")
