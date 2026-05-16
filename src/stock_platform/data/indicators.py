"""技术指标计算模块"""
import numpy as np
from decimal import Decimal
from sqlalchemy.orm import Session
from stock_platform.db.models import Stock, DailyPrice, TechnicalIndicator, CrawlTask


def calculate_indicators(session: Session, stock: Stock) -> int:
    """计算单只股票的全部技术指标"""
    prices = (
        session.query(DailyPrice)
        .filter(DailyPrice.stock_id == stock.id, DailyPrice.adjust_type == 1)
        .order_by(DailyPrice.trade_date.asc())
        .all()
    )

    if len(prices) < 20:
        return 0

    closes = np.array([float(p.close_price) for p in prices], dtype=np.float64)
    highs = np.array([float(p.high_price) for p in prices], dtype=np.float64)
    lows = np.array([float(p.low_price) for p in prices], dtype=np.float64)
    dates = [p.trade_date for p in prices]

    count = 0
    for i in range(len(prices)):
        if i < 5:
            continue  # need at least 5 days for MA5

        dp = prices[i]
        existing = session.query(TechnicalIndicator).filter_by(
            stock_id=stock.id, trade_date=dp.trade_date
        ).first()
        if existing:
            continue

        ti = TechnicalIndicator(stock_id=stock.id, trade_date=dp.trade_date)

        # MA
        ti.ma5 = _ma(closes, i, 5)
        ti.ma10 = _ma(closes, i, 10) if i >= 9 else None
        ti.ma20 = _ma(closes, i, 20) if i >= 19 else None
        ti.ma30 = _ma(closes, i, 30) if i >= 29 else None
        ti.ma60 = _ma(closes, i, 60) if i >= 59 else None

        # MACD
        dif, dea, bar = _macd(closes[:i + 1])
        ti.macd_dif = _dec(dif)
        ti.macd_dea = _dec(dea)
        ti.macd_bar = _dec(bar)

        # RSI
        if i >= 5:
            ti.rsi_6 = _dec(_rsi(closes[:i + 1], 6))
            ti.rsi_12 = _dec(_rsi(closes[:i + 1], 12))
            ti.rsi_24 = _dec(_rsi(closes[:i + 1], 24))

        # Bollinger Bands
        if i >= 19:
            up, mid, down = _bollinger(closes[:i + 1], 20)
            ti.boll_up = _dec(up)
            ti.boll_mid = _dec(mid)
            ti.boll_down = _dec(down)

        session.add(ti)
        count += 1

    session.flush()
    return count


def calculate_all_indicators(session: Session) -> int:
    """计算所有股票的技术指标"""
    stocks = session.query(Stock).filter(Stock.status == 1).all()
    task = CrawlTask(
        task_type="indicators", status="running", total_items=len(stocks),
    )
    session.add(task)
    session.flush()

    total = 0
    for stock in stocks:
        try:
            total += calculate_indicators(session, stock)
            session.commit()
        except Exception:
            session.rollback()

    task.status = "completed"
    task.success_items = total
    session.commit()
    return total


def _ma(arr: np.ndarray, i: int, n: int) -> float | None:
    if i < n - 1:
        return None
    return round(float(arr[i - n + 1:i + 1].mean()), 4)


def _macd(closes: np.ndarray) -> tuple:
    """计算 MACD"""
    if len(closes) < 26:
        return 0.0, 0.0, 0.0

    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    dif = ema12[-1] - ema26[-1]
    # DEA: EMA of all DIF values over the full series
    difs = ema12 - ema26
    dea = _ema(difs, 9)[-1] if len(difs) >= 9 else difs[-1]
    bar = 2 * (dif - dea)

    return round(dif, 4), round(dea, 4), round(bar, 4)


def _ema(arr: np.ndarray, n: int) -> np.ndarray:
    """指数移动平均"""
    result = np.zeros_like(arr)
    alpha = 2 / (n + 1)
    result[0] = arr[0]
    for i in range(1, len(arr)):
        result[i] = alpha * arr[i] + (1 - alpha) * result[i - 1]
    return result


def _rsi(closes: np.ndarray, n: int) -> float:
    """计算 RSI"""
    if len(closes) < n + 1:
        return 50.0

    deltas = np.diff(closes[-n - 1:])
    gains = np.sum(deltas[deltas > 0])
    losses = abs(np.sum(deltas[deltas < 0]))

    if abs(losses) < 1e-10:
        return 100.0

    rs = gains / losses
    return round(100 - 100 / (1 + rs), 4)


def _bollinger(closes: np.ndarray, n: int = 20, k: float = 2.0) -> tuple:
    """计算布林带"""
    subset = closes[-n:]
    mid = subset.mean()
    std = subset.std(ddof=1)
    return round(mid + k * std, 4), round(mid, 4), round(mid - k * std, 4)


def _dec(val: float) -> Decimal:
    return Decimal(str(val))
