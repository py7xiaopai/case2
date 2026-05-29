from sqlalchemy import (
    DECIMAL,
    BigInteger,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from stock_platform.db.engine import Base


class Stock(Base):
    """股票基础信息"""
    __tablename__ = "stocks"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    code = Column(String(10), nullable=False, unique=True, comment="股票代码")
    name = Column(String(100), nullable=False, comment="股票名称")
    market = Column(String(10), nullable=True, comment="市场: SH/SZ/BJ (deprecated, use exchange)")
    exchange = Column(String(10), nullable=True, comment="交易所: SH/SZ/BJ")
    board = Column(String(20), nullable=True, comment="板块: 主板/创业板/科创板/北交所")
    industry = Column(String(100), nullable=True, comment="行业")
    listing_date = Column(Date, nullable=True, comment="上市日期")
    status = Column(Integer, default=1, comment="状态: 1正常 0暂停 -1退市")
    total_market_cap = Column(DECIMAL(20, 4), nullable=True, comment="总市值(元)")
    circulating_market_cap = Column(DECIMAL(20, 4), nullable=True, comment="流通市值(元)")
    source_updated_at = Column(DateTime, nullable=True, comment="数据来源最近更新时间")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        Index("idx_stock_market", "market"),
        Index("idx_stock_exchange", "exchange"),
        Index("idx_stock_board", "board"),
    )


class DailyPrice(Base):
    """历史日线行情"""
    __tablename__ = "daily_prices"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_id = Column(BigInteger, ForeignKey("stocks.id"), nullable=False, comment="股票ID")
    trade_date = Column(Date, nullable=False, comment="交易日期")
    adjust_type = Column(Integer, nullable=True, comment="复权类型: 0不复权 1前复权 2后复权")
    open_price = Column(DECIMAL(18, 4), nullable=True, comment="开盘价")
    close_price = Column(DECIMAL(18, 4), nullable=True, comment="收盘价")
    high_price = Column(DECIMAL(18, 4), nullable=True, comment="最高价")
    low_price = Column(DECIMAL(18, 4), nullable=True, comment="最低价")
    volume = Column(BigInteger, nullable=True, comment="成交量(股)")
    amount = Column(DECIMAL(20, 2), nullable=True, comment="成交额(元)")
    pct_change = Column(DECIMAL(10, 4), nullable=True, comment="涨跌幅(%)")
    change_amount = Column(DECIMAL(10, 4), nullable=True, comment="涨跌额")
    turnover_rate = Column(DECIMAL(10, 4), nullable=True, comment="换手率(%)")
    source = Column(String(50), nullable=True, comment="数据来源")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    __table_args__ = (
        UniqueConstraint("stock_id", "trade_date", "adjust_type", name="uq_daily_price_unique"),
        Index("idx_daily_trade_date", "trade_date"),
        Index("idx_daily_stock_date", "stock_id", "trade_date"),
    )


class TechnicalIndicator(Base):
    """技术指标"""
    __tablename__ = "technical_indicators"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_id = Column(BigInteger, ForeignKey("stocks.id"), nullable=True, comment="股票ID")
    trade_date = Column(Date, nullable=True, comment="交易日期")

    ma5 = Column(DECIMAL(10, 4), nullable=True, comment="5日均线")
    ma10 = Column(DECIMAL(10, 4), nullable=True, comment="10日均线")
    ma20 = Column(DECIMAL(10, 4), nullable=True, comment="20日均线")
    ma30 = Column(DECIMAL(10, 4), nullable=True, comment="30日均线")
    ma60 = Column(DECIMAL(10, 4), nullable=True, comment="60日均线")

    macd_dif = Column(DECIMAL(10, 4), nullable=True, comment="DIF")
    macd_dea = Column(DECIMAL(10, 4), nullable=True, comment="DEA")
    macd_bar = Column(DECIMAL(10, 4), nullable=True, comment="MACD柱")

    rsi_6 = Column(DECIMAL(10, 4), nullable=True, comment="RSI6")
    rsi_12 = Column(DECIMAL(10, 4), nullable=True, comment="RSI12")
    rsi_24 = Column(DECIMAL(10, 4), nullable=True, comment="RSI24")

    boll_up = Column(DECIMAL(10, 4), nullable=True, comment="布林上轨")
    boll_mid = Column(DECIMAL(10, 4), nullable=True, comment="布林中轨")
    boll_down = Column(DECIMAL(10, 4), nullable=True, comment="布林下轨")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    __table_args__ = (
        Index("idx_indicator_stock_date", "stock_id", "trade_date"),
    )


class TradingCalendar(Base):
    """交易日历"""
    __tablename__ = "trading_calendar"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    trade_date = Column(Date, nullable=False, unique=True, index=True, comment="日期")
    is_open = Column(Integer, default=1, comment="是否交易日: 1是0否")
    market = Column(String(10), nullable=True, comment="市场")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")


class CrawlTask(Base):
    """爬虫任务记录"""
    __tablename__ = "crawl_tasks"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_type = Column(String(50), nullable=True, comment="任务类型")
    status = Column(String(20), nullable=True, comment="状态")
    start_time = Column(DateTime, nullable=True, comment="开始时间")
    end_time = Column(DateTime, nullable=True, comment="结束时间")
    total_items = Column(Integer, nullable=True, comment="总条目数")
    success_items = Column(Integer, nullable=True, comment="成功条目数")
    fail_items = Column(Integer, nullable=True, comment="失败条目数")
    error_message = Column(Text, nullable=True, comment="错误信息")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")


class CrawlLog(Base):
    """爬虫日志"""
    __tablename__ = "crawl_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_id = Column(BigInteger, ForeignKey("crawl_tasks.id"), nullable=True, comment="任务ID")
    stock_code = Column(String(10), nullable=True, comment="股票代码")
    url = Column(Text, nullable=True, comment="请求URL")
    status_code = Column(Integer, nullable=True, comment="HTTP状态码")
    response_time = Column(Float, nullable=True, comment="响应时间(秒)")
    error_message = Column(Text, nullable=True, comment="错误信息")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
