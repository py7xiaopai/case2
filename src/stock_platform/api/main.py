"""FastAPI 主应用"""
from fastapi import FastAPI, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from datetime import date, datetime
from typing import Optional

from stock_platform.db.engine import get_db
from stock_platform.db.models import Stock, DailyPrice, TechnicalIndicator
from stock_platform.data.etl import data_quality_check

app = FastAPI(
    title="A 股历史行情数据平台 API",
    description="提供股票信息查询、历史行情、技术指标、数据质量等服务",
    version="0.1.0",
)


@app.get("/")
def root():
    return {"service": "A 股行情数据平台", "status": "running", "version": "0.1.0"}


@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


# ─── 股票搜索 ─────────────────────────────────


@app.get("/stocks/search")
def search_stocks(
    q: str = Query("", description="股票代码或名称"),
    market: Optional[str] = Query(None, description="市场: SH/SZ/BJ"),
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Stock)
    if q:
        query = query.filter(
            Stock.code.like(f"%{q}%") | Stock.name.like(f"%{q}%")
        )
    if market:
        query = query.filter(Stock.market == market)
    stocks = query.limit(limit).all()
    return [
        {
            "id": s.id, "code": s.code, "name": s.name,
            "market": s.market, "industry": s.industry,
            "listing_date": str(s.listing_date) if s.listing_date else None,
            "status": s.status,
        }
        for s in stocks
    ]


# ─── 股票详情 ─────────────────────────────────


@app.get("/stocks/{code}")
def stock_detail(code: str, db: Session = Depends(get_db)):
    stock = db.query(Stock).filter(Stock.code == code).first()
    if not stock:
        raise HTTPException(404, "股票不存在")
    return {
        "id": stock.id, "code": stock.code, "name": stock.name,
        "market": stock.market, "industry": stock.industry,
        "listing_date": str(stock.listing_date) if stock.listing_date else None,
        "status": stock.status,
    }


# ─── 历史行情 ─────────────────────────────────


@app.get("/stocks/{code}/prices")
def stock_prices(
    code: str,
    start: Optional[str] = Query(None, description="起始日期 YYYY-MM-DD"),
    end: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    limit: int = Query(200, le=1000),
    db: Session = Depends(get_db),
):
    stock = db.query(Stock).filter(Stock.code == code).first()
    if not stock:
        raise HTTPException(404, "股票不存在")

    query = db.query(DailyPrice).filter(DailyPrice.stock_id == stock.id)
    if start:
        query = query.filter(DailyPrice.trade_date >= date.fromisoformat(start))
    if end:
        query = query.filter(DailyPrice.trade_date <= date.fromisoformat(end))
    prices = query.order_by(desc(DailyPrice.trade_date)).limit(limit).all()

    return [
        {
            "date": str(p.trade_date),
            "open": float(p.open_price) if p.open_price else None,
            "close": float(p.close_price) if p.close_price else None,
            "high": float(p.high_price) if p.high_price else None,
            "low": float(p.low_price) if p.low_price else None,
            "volume": int(p.volume) if p.volume else 0,
            "amount": float(p.amount) if p.amount else 0,
            "pct_change": float(p.pct_change) if p.pct_change else None,
            "turnover_rate": float(p.turnover_rate) if p.turnover_rate else None,
        }
        for p in prices
    ]


# ─── 技术指标 ─────────────────────────────────


@app.get("/stocks/{code}/indicators")
def stock_indicators(
    code: str,
    limit: int = Query(200, le=1000),
    db: Session = Depends(get_db),
):
    stock = db.query(Stock).filter(Stock.code == code).first()
    if not stock:
        raise HTTPException(404, "股票不存在")

    indicators = (
        db.query(TechnicalIndicator)
        .filter(TechnicalIndicator.stock_id == stock.id)
        .order_by(desc(TechnicalIndicator.trade_date))
        .limit(limit)
        .all()
    )

    return [
        {
            "date": str(i.trade_date),
            "ma5": float(i.ma5) if i.ma5 else None,
            "ma10": float(i.ma10) if i.ma10 else None,
            "ma20": float(i.ma20) if i.ma20 else None,
            "ma60": float(i.ma60) if i.ma60 else None,
            "macd_dif": float(i.macd_dif) if i.macd_dif else None,
            "macd_dea": float(i.macd_dea) if i.macd_dea else None,
            "macd_bar": float(i.macd_bar) if i.macd_bar else None,
            "rsi_6": float(i.rsi_6) if i.rsi_6 else None,
            "rsi_12": float(i.rsi_12) if i.rsi_12 else None,
            "rsi_24": float(i.rsi_24) if i.rsi_24 else None,
            "boll_up": float(i.boll_up) if i.boll_up else None,
            "boll_mid": float(i.boll_mid) if i.boll_mid else None,
            "boll_down": float(i.boll_down) if i.boll_down else None,
        }
        for i in indicators
    ]


# ─── 排行榜 ─────────────────────────────────


@app.get("/rankings/changes")
def ranking_changes(
    date_str: Optional[str] = Query(None, description="日期 YYYY-MM-DD"),
    direction: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
):
    """涨跌幅排行"""
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

    return [
        {
            "code": code, "name": name,
            "close": float(p.close_price) if p.close_price else None,
            "pct_change": float(p.pct_change),
            "volume": int(p.volume) if p.volume else 0,
        }
        for p, code, name in prices
    ]


@app.get("/rankings/volume")
def ranking_volume(
    date_str: Optional[str] = Query(None, description="日期 YYYY-MM-DD"),
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
):
    """成交量排行"""
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

    return [
        {
            "code": code, "name": name,
            "close": float(p.close_price) if p.close_price else None,
            "volume": int(p.volume),
            "amount": float(p.amount) if p.amount else 0,
        }
        for p, code, name in prices
    ]


# ─── 数据质量 ─────────────────────────────────


@app.get("/quality")
def quality(db: Session = Depends(get_db)):
    return data_quality_check(db)


# ─── 数据导出 ─────────────────────────────────


@app.get("/stocks/{code}/export")
def export_prices(
    code: str,
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    stock = db.query(Stock).filter(Stock.code == code).first()
    if not stock:
        raise HTTPException(404, "股票不存在")

    query = db.query(DailyPrice).filter(DailyPrice.stock_id == stock.id)
    if start:
        query = query.filter(DailyPrice.trade_date >= date.fromisoformat(start))
    if end:
        query = query.filter(DailyPrice.trade_date <= date.fromisoformat(end))
    prices = query.order_by(DailyPrice.trade_date.asc()).all()

    import csv, io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["date", "open", "close", "high", "low", "volume", "amount", "pct_change"])
    for p in prices:
        writer.writerow([
            p.trade_date, p.open_price, p.close_price,
            p.high_price, p.low_price, p.volume,
            p.amount, p.pct_change,
        ])
    return {"code": code, "name": stock.name, "csv": output.getvalue()}
