"""历史日线行情抓取模块 —— 从新浪财经网页接口抓取"""
import time
import json
import requests
from datetime import date, timedelta
from sqlalchemy.orm import Session
from stock_platform.db.models import Stock, DailyPrice, CrawlTask, CrawlLog
from stock_platform import settings

WEB_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://finance.sina.com.cn/stock/",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def crawl_daily_prices(
    session: Session,
    stock: Stock,
    years_back: int = 3,
    adjust_type: int = 1,
) -> int:
    """从新浪财经抓取单只股票的历史日线行情"""
    end_date = date.today()
    start_date = end_date - timedelta(days=years_back * 365)
    return _fetch_from_sina(session, stock, start_date, end_date)


def _fetch_from_sina(
    session: Session, stock: Stock,
    start_date: date, end_date: date,
) -> int:
    """从新浪财经 K 线接口抓取日线数据

    数据源: money.finance.sina.com.cn
    和 sina 财经网页「历史行情」数据完全一致
    """
    market = "sh" if stock.market == "SH" else "sz"
    symbol = f"{market}{stock.code}"

    http = requests.Session()
    http.trust_env = False
    http.headers.update(WEB_HEADERS)

    # datalen=2000 获取尽可能多的日线（实际最多返回约 1023 条，约 4 年）
    url = (
        "https://money.finance.sina.com.cn/quotes_service/"
        "api/json_v2.php/CN_MarketData.getKLineData"
        f"?symbol={symbol}&scale=240&ma=5&datalen=1023"
    )

    resp = http.get(url, timeout=settings.crawler_timeout)
    resp.encoding = "gbk"
    text = resp.text.strip()

    if not text or text == "null":
        return 0

    # 清理可能的前缀
    if not text.startswith("["):
        idx = text.find("[")
        if idx >= 0:
            text = text[idx:]
        else:
            return 0

    data = json.loads(text)
    if not data:
        return 0

    count = 0
    for item in data:
        trade_date_str = item.get("day", "")
        try:
            trade_date = date.fromisoformat(str(trade_date_str)[:10])
        except ValueError:
            continue

        # 过滤超出时间范围的数据
        if trade_date < start_date or trade_date > end_date:
            continue

        # 去重
        existing = session.query(DailyPrice).filter_by(
            stock_id=stock.id, trade_date=trade_date, adjust_type=1
        ).first()
        if existing:
            continue

        dp = DailyPrice(
            stock_id=stock.id,
            trade_date=trade_date,
            adjust_type=1,
            open_price=_to_decimal(item.get("open")),
            close_price=_to_decimal(item.get("close")),
            high_price=_to_decimal(item.get("high")),
            low_price=_to_decimal(item.get("low")),
            volume=_to_float(item.get("volume", 0)),
            source="sina_web",
        )
        session.add(dp)
        count += 1

    session.flush()
    return count


def crawl_all_stocks_daily_prices(
    session: Session,
    years_back: int = 3,
    adjust_type: int = 1,
    max_stocks: int = 0,
) -> int:
    """串行抓取所有股票的历史日线行情"""
    query = session.query(Stock).filter(Stock.status == 1)
    if max_stocks > 0:
        query = query.limit(max_stocks)
    stocks = query.all()

    task = CrawlTask(
        task_type="daily_prices", status="running",
        total_items=len(stocks),
    )
    session.add(task)
    session.flush()
    task_id = task.id
    session.commit()

    total = 0
    success = 0
    fail = 0

    for idx, stock in enumerate(stocks, 1):
        try:
            count = crawl_daily_prices(session, stock, years_back, adjust_type)
            if count > 0:
                success += 1
            total += count
            session.commit()
        except Exception as e:
            fail += 1
            session.rollback()
            log = CrawlLog(
                task_id=task_id, stock_code=stock.code,
                error_message=str(e),
            )
            session.add(log)
            session.commit()

        if idx % 100 == 0 or idx == len(stocks):
            print(f"  进度: {idx}/{len(stocks)}  成功:{success}  失败:{fail}  日线:{total}")

    task.status = "completed"
    task.success_items = success
    task.fail_items = fail
    task.total_items = len(stocks)
    session.commit()

    print(f"✅ 全量完成: {total} 条日线 (成功{success} 失败{fail})")
    return total


def _to_decimal(val):
    if val is None or val == "null":
        return None
    try:
        from decimal import Decimal
        return Decimal(str(val))
    except Exception:
        return None


def _to_float(val):
    if val is None or val == "null":
        return None
    try:
        return float(val)
    except Exception:
        return None
