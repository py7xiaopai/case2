"""FastAPI 主应用 — 统一响应结构、全局异常处理、日志中间件、限流"""
import logging
import re
import time
from datetime import date, datetime, timedelta
from typing import Any, Optional

from cachetools import TTLCache
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from stock_platform.data.etl import data_quality_check
from stock_platform.db.engine import get_db
from stock_platform.db.models import DailyPrice, Stock, TechnicalIndicator

# ── 日志配置 ────────────────────────────────────────────

logger = logging.getLogger("stock_platform.api")
logger.setLevel(logging.INFO)
_ch = logging.StreamHandler()
_ch.setFormatter(logging.Formatter(
    "%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
))
logger.addHandler(_ch)

# ── 速率限制器 ──────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

# ── Pydantic 响应模型 ────────────────────────────────────


class BaseResponse(BaseModel):
    """统一成功响应"""
    code: int = Field(0, description="状态码，0 表示成功")
    data: Any = Field(None, description="响应数据")
    message: str = Field("ok", description="状态消息")


class ErrorResponse(BaseModel):
    """统一错误响应"""
    code: int = Field(..., description="错误码：1001 股票不存在 / 1002 参数错误 / 2000 内部服务异常")
    data: Any = Field(None, json_schema_extra={"nullable": True})
    message: str = Field(..., description="错误描述")


class StockItem(BaseModel):
    """股票搜索 / 详情条目"""
    id: int
    code: str
    name: str
    market: Optional[str] = None
    industry: Optional[str] = None
    listing_date: Optional[str] = None
    status: int


class PriceItem(BaseModel):
    """日线行情条目"""
    date: str
    open: Optional[float] = None
    close: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    volume: int = 0
    amount: float = 0
    pct_change: Optional[float] = None
    turnover_rate: Optional[float] = None


class PaginatedPrices(BaseModel):
    """分页行情数据"""
    items: list[PriceItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class IndicatorItem(BaseModel):
    """技术指标条目"""
    date: str
    ma5: Optional[float] = None
    ma10: Optional[float] = None
    ma20: Optional[float] = None
    ma60: Optional[float] = None
    macd_dif: Optional[float] = None
    macd_dea: Optional[float] = None
    macd_bar: Optional[float] = None
    rsi_6: Optional[float] = None
    rsi_12: Optional[float] = None
    rsi_24: Optional[float] = None
    boll_up: Optional[float] = None
    boll_mid: Optional[float] = None
    boll_down: Optional[float] = None


class RankingItem(BaseModel):
    """排行榜条目"""
    code: str
    name: str
    close: Optional[float] = None
    pct_change: Optional[float] = None
    volume: int = 0
    amount: Optional[float] = None


# ── FastAPI 应用 ───────────────────────────────────────

app = FastAPI(
    title="A 股历史行情数据平台 API",
    description="提供股票信息查询、历史行情、技术指标、数据质量等服务",
    version="0.2.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── 辅助函数 ────────────────────────────────────────────

CODE_PATTERN = re.compile(r"^\d{6}$")

# 热门股票详情缓存（5 分钟）
_detail_cache: TTLCache = TTLCache(maxsize=256, ttl=300)


def _validate_date(val: Optional[str], name: str) -> Optional[str]:
    """校验日期格式 YYYY-MM-DD，返回规范化后的字符串"""
    if val is None:
        return None
    try:
        d = date.fromisoformat(val)
        return d.isoformat()
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=422,
            detail={"code": 1002, "message": f"参数 {name} 格式无效，需为 YYYY-MM-DD"},
        )


def _validate_code(code: str) -> None:
    """校验股票代码为 6 位数字"""
    if not CODE_PATTERN.match(code):
        raise HTTPException(
            status_code=422,
            detail={"code": 1002, "message": "股票代码格式无效，需为 6 位数字"},
        )


def _get_stock_or_404(code: str, db: Session) -> Stock:
    """获取股票，不存在则抛 1001"""
    stock = db.query(Stock).filter(Stock.code == code).first()
    if not stock:
        raise HTTPException(
            status_code=404,
            detail={"code": 1001, "message": "股票不存在"},
        )
    return stock


def _stock_to_dict(stock: Stock) -> dict:
    return {
        "id": stock.id,
        "code": stock.code,
        "name": stock.name,
        "market": stock.market,
        "exchange": stock.exchange,
        "industry": stock.industry,
        "board": stock.board,
        "listing_date": str(stock.listing_date) if stock.listing_date else None,
        "status": stock.status,
        "total_market_cap": float(stock.total_market_cap) if stock.total_market_cap is not None else None,
        "circulating_market_cap": float(stock.circulating_market_cap) if stock.circulating_market_cap is not None else None,
        "source_updated_at": stock.source_updated_at.isoformat() if stock.source_updated_at else None,
    }


def _price_to_dict(p: DailyPrice) -> dict:
    return {
        "date": str(p.trade_date),
        "open": float(p.open_price) if p.open_price is not None else None,
        "close": float(p.close_price) if p.close_price is not None else None,
        "high": float(p.high_price) if p.high_price is not None else None,
        "low": float(p.low_price) if p.low_price is not None else None,
        "volume": int(p.volume) if p.volume is not None else 0,
        "amount": float(p.amount) if p.amount is not None else 0,
        "pct_change": float(p.pct_change) if p.pct_change is not None else None,
        "turnover_rate": float(p.turnover_rate) if p.turnover_rate is not None else None,
    }


# ── 中间件 ──────────────────────────────────────────────


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """记录请求方法 / 路径 / 耗时 / 状态码"""
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    logger.info(
        "%s %s → %s (%.3fs)",
        request.method,
        request.url.path,
        response.status_code,
        elapsed,
    )
    return response


# ── 全局异常处理 ────────────────────────────────────────


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """兜底异常处理，返回统一错误格式"""
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"code": 2000, "data": None, "message": "内部服务异常"},
    )


# ── 统一响应包装 ────────────────────────────────────────


def ok(data: Any = None) -> dict:
    return {"code": 0, "data": data, "message": "ok"}


# ── 端点 ────────────────────────────────────────────────


@app.get("/", response_model=BaseResponse)
async def root():
    """服务根路径"""
    return ok({"service": "A 股行情数据平台", "status": "running", "version": "0.2.0"})


@app.get("/health", response_model=BaseResponse)
async def health():
    """健康检查"""
    return ok({"status": "ok", "timestamp": datetime.now().isoformat()})


@app.get(
    "/stocks/search",
    response_model=BaseResponse,
    summary="股票搜索",
    description="按股票代码或名称模糊搜索，可按市场筛选",
)
def search_stocks(
    q: str = Query("", description="股票代码或名称"),
    market: Optional[str] = Query(None, description="市场: SH/SZ/BJ"),
    limit: int = Query(20, le=100, description="返回条数上限"),
    db: Session = Depends(get_db),
):
    # 搜索限长：查询词长度 ≥ 2
    if q and len(q.strip()) < 2:
        return ok([])
    query = db.query(Stock)
    if q:
        query = query.filter(
            Stock.code.like(f"%{q}%") | Stock.name.like(f"%{q}%")
        )
    if market:
        query = query.filter(Stock.market == market)
    stocks = query.limit(limit).all()
    return ok(
        [_stock_to_dict(s) for s in stocks],
    )


@app.get(
    "/stocks/{code}",
    response_model=BaseResponse,
    summary="股票详情",
    description="获取单只股票的详细信息",
    responses={
        404: {"description": "股票不存在", "model": ErrorResponse},
        422: {"description": "参数错误", "model": ErrorResponse},
    },
)
def stock_detail(code: str, db: Session = Depends(get_db)):
    _validate_code(code)
    # 缓存命中直接返回
    cache_key = f"detail:{code}"
    if cache_key in _detail_cache:
        return ok(_detail_cache[cache_key])
    stock = _get_stock_or_404(code, db)
    result = _stock_to_dict(stock)
    _detail_cache[cache_key] = result
    return ok(result)


# ─── 行情（分页）─────────────────────────────────


@app.get(
    "/stocks/{code}/prices",
    response_model=BaseResponse,
    summary="日线行情（分页）",
    description="获取股票日线行情数据，支持分页和日期范围筛选",
)
def stock_prices(
    code: str,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(100, ge=1, le=500, description="每页条数"),
    start: Optional[str] = Query(None, description="起始日期 YYYY-MM-DD"),
    end: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    _validate_code(code)
    stock = _get_stock_or_404(code, db)
    start = _validate_date(start, "start")
    end = _validate_date(end, "end")

    query = db.query(DailyPrice).filter(DailyPrice.stock_id == stock.id)
    if start:
        query = query.filter(DailyPrice.trade_date >= date.fromisoformat(start))
    if end:
        query = query.filter(DailyPrice.trade_date <= date.fromisoformat(end))

    total = query.count()
    total_pages = max(1, (total + page_size - 1) // page_size)
    offset = (page - 1) * page_size

    prices = (
        query.order_by(desc(DailyPrice.trade_date))
        .offset(offset)
        .limit(page_size)
        .all()
    )

    return ok({
        "items": [_price_to_dict(p) for p in prices],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    })


# ─── K 线图（完整时间序列）──────────────────────


@app.get(
    "/stocks/{code}/chart",
    response_model=BaseResponse,
    summary="K 线图数据",
    description="获取股票完整的日线行情时间序列（用于 K 线图），按日期升序排列",
)
def stock_chart(
    code: str,
    start: Optional[str] = Query(None, description="起始日期 YYYY-MM-DD（默认最近 1 年）"),
    end: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    _validate_code(code)
    stock = _get_stock_or_404(code, db)
    start = _validate_date(start, "start")
    end = _validate_date(end, "end")

    # 默认取最近 1 年，最大 5 年
    end_date = date.fromisoformat(end) if end else date.today()
    if start:
        start_date = date.fromisoformat(start)
        if (end_date - start_date).days > 365 * 5:
            start_date = end_date - timedelta(days=365 * 5)
    else:
        start_date = end_date - timedelta(days=365)

    query = db.query(DailyPrice).filter(
        DailyPrice.stock_id == stock.id,
        DailyPrice.trade_date >= start_date,
        DailyPrice.trade_date <= end_date,
    )
    prices = query.order_by(DailyPrice.trade_date.asc()).all()
    return ok([_price_to_dict(p) for p in prices])


# ─── 技术指标 ─────────────────────────────────


@app.get(
    "/stocks/{code}/indicators",
    response_model=BaseResponse,
    summary="技术指标",
    description="获取股票技术指标数据（MA、MACD、RSI、布林带）",
)
def stock_indicators(
    code: str,
    limit: int = Query(200, le=1000, description="返回条数上限"),
    db: Session = Depends(get_db),
):
    _validate_code(code)
    stock = _get_stock_or_404(code, db)
    indicators = (
        db.query(TechnicalIndicator)
        .filter(TechnicalIndicator.stock_id == stock.id)
        .order_by(desc(TechnicalIndicator.trade_date))
        .limit(limit)
        .all()
    )
    return ok([
        {
            "date": str(i.trade_date),
            "ma5": float(i.ma5) if i.ma5 is not None else None,
            "ma10": float(i.ma10) if i.ma10 is not None else None,
            "ma20": float(i.ma20) if i.ma20 is not None else None,
            "ma60": float(i.ma60) if i.ma60 is not None else None,
            "macd_dif": float(i.macd_dif) if i.macd_dif is not None else None,
            "macd_dea": float(i.macd_dea) if i.macd_dea is not None else None,
            "macd_bar": float(i.macd_bar) if i.macd_bar is not None else None,
            "rsi_6": float(i.rsi_6) if i.rsi_6 is not None else None,
            "rsi_12": float(i.rsi_12) if i.rsi_12 is not None else None,
            "rsi_24": float(i.rsi_24) if i.rsi_24 is not None else None,
            "boll_up": float(i.boll_up) if i.boll_up is not None else None,
            "boll_mid": float(i.boll_mid) if i.boll_mid is not None else None,
            "boll_down": float(i.boll_down) if i.boll_down is not None else None,
        }
        for i in indicators
    ])


# ─── 排行榜 ─────────────────────────────────


@app.get(
    "/rankings/changes",
    response_model=BaseResponse,
    summary="涨跌幅排行",
    description="获取指定日期涨跌幅排行榜，支持升序/降序",
)
def ranking_changes(
    date_str: Optional[str] = Query(None, description="日期 YYYY-MM-DD"),
    direction: str = Query("desc", pattern="^(asc|desc)$", description="排序方向 asc 升序 / desc 降序"),
    limit: int = Query(20, le=100, description="返回条数上限"),
    db: Session = Depends(get_db),
):
    target_date = date.fromisoformat(date_str) if date_str else date.today()
    prices = (
        db.query(DailyPrice, Stock.code, Stock.name)
        .join(Stock, DailyPrice.stock_id == Stock.id)
        .filter(
            DailyPrice.trade_date == target_date,
            DailyPrice.pct_change.isnot(None),
        )
        .order_by(
            DailyPrice.pct_change.desc() if direction == "desc"
            else DailyPrice.pct_change.asc()
        )
        .limit(limit)
        .all()
    )
    return ok([
        {
            "code": code,
            "name": name,
            "close": float(p.close_price) if p.close_price is not None else None,
            "pct_change": float(p.pct_change),
            "volume": int(p.volume) if p.volume is not None else 0,
        }
        for p, code, name in prices
    ])


@app.get(
    "/rankings/volume",
    response_model=BaseResponse,
    summary="成交量排行",
    description="获取指定日期成交量排行榜",
)
def ranking_volume(
    date_str: Optional[str] = Query(None, description="日期 YYYY-MM-DD"),
    limit: int = Query(20, le=100, description="返回条数上限"),
    db: Session = Depends(get_db),
):
    target_date = date.fromisoformat(date_str) if date_str else date.today()
    prices = (
        db.query(DailyPrice, Stock.code, Stock.name)
        .join(Stock, DailyPrice.stock_id == Stock.id)
        .filter(
            DailyPrice.trade_date == target_date,
            DailyPrice.volume.isnot(None),
        )
        .order_by(desc(DailyPrice.volume))
        .limit(limit)
        .all()
    )
    return ok([
        {
            "code": code,
            "name": name,
            "close": float(p.close_price) if p.close_price is not None else None,
            "volume": int(p.volume),
            "amount": float(p.amount) if p.amount is not None else 0,
        }
        for p, code, name in prices
    ])


# ─── 数据质量 ─────────────────────────────────


@app.get(
    "/quality",
    response_model=BaseResponse,
    summary="数据质量检查",
    description="返回当前数据库中的数据质量报告",
)
def quality(db: Session = Depends(get_db)):
    return ok(data_quality_check(db))


# ─── 数据导出 ─────────────────────────────────


@app.get(
    "/stocks/{code}/export",
    response_model=BaseResponse,
    summary="导出 CSV",
    description="导出股票日线行情为 CSV 格式",
)
def export_prices(
    code: str,
    start: Optional[str] = Query(None, description="起始日期 YYYY-MM-DD"),
    end: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    _validate_code(code)
    stock = _get_stock_or_404(code, db)
    start = _validate_date(start, "start")
    end = _validate_date(end, "end")

    query = db.query(DailyPrice).filter(DailyPrice.stock_id == stock.id)
    if start:
        query = query.filter(DailyPrice.trade_date >= date.fromisoformat(start))
    if end:
        query = query.filter(DailyPrice.trade_date <= date.fromisoformat(end))
    prices = query.order_by(DailyPrice.trade_date.asc()).all()

    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["date", "open", "close", "high", "low", "volume", "amount", "pct_change"])
    for p in prices:
        writer.writerow([
            p.trade_date, p.open_price, p.close_price,
            p.high_price, p.low_price, p.volume,
            p.amount, p.pct_change,
        ])
    return ok({"code": code, "name": stock.name, "csv": output.getvalue()})
