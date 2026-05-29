"""历史日线行情抓取模块 —— 从新浪财经网页接口抓取"""
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta

import requests
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from stock_platform import settings
from stock_platform.data.utils import to_decimal, to_float
from stock_platform.db.models import CrawlLog, CrawlTask, DailyPrice, Stock

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
    market = {"SH": "sh", "SZ": "sz", "BJ": "bj"}.get(stock.market, "sh")
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

    retries = settings.crawler_retries
    for attempt in range(retries):
        try:
            resp = http.get(url, timeout=settings.crawler_timeout)
            resp.encoding = "gbk"
            text = resp.text.strip()
            if text and text != "null":
                break
        except requests.RequestException:
            if attempt == retries - 1:
                return 0
            time.sleep(1 * (attempt + 1))
            continue
    else:
        return 0

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
            open_price=to_decimal(item.get("open")),
            close_price=to_decimal(item.get("close")),
            high_price=to_decimal(item.get("high")),
            low_price=to_decimal(item.get("low")),
            volume=to_float(item.get("volume", 0)),
            source="sina_web",
        )
        session.add(dp)
        count += 1

    session.flush()
    return count


_worker_engine = None
_worker_lock = threading.Lock()


def _init_worker(db_url: str):
    """ThreadPoolExecutor worker 初始化：每线程创建独立引擎"""
    global _worker_engine
    from sqlalchemy import create_engine
    _worker_engine = create_engine(
        db_url, poolclass=NullPool, pool_pre_ping=True,
    )


def _crawl_one_worker(stock_id: int, stock_code: str, delay: float,
                      years_back: int, adjust_type: int) -> tuple:
    """在线程中独立创建 session 抓取单只股票，返回 (code, count, error)"""
    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=_worker_engine)
    session = Session()
    try:
        time.sleep(delay)
        stock = session.query(Stock).get(stock_id)
        if not stock:
            return (stock_code, 0, "Stock deleted")
        count = crawl_daily_prices(session, stock, years_back, adjust_type)
        session.commit()
        return (stock_code, count, None)
    except Exception as e:
        session.rollback()
        return (stock_code, 0, str(e))
    finally:
        session.close()


def crawl_all_stocks_daily_prices(
    session: Session,
    years_back: int = 3,
    adjust_type: int = 1,
    max_stocks: int = 0,
    max_workers: int = 8,
) -> int:
    """并行抓取所有股票的历史日线行情（默认 8 线程）"""
    query = session.query(Stock).filter(Stock.status == 1)
    if max_stocks > 0:
        query = query.limit(max_stocks)
    stocks = query.all()

    if not stocks:
        print("⚠️ 无股票数据需要抓取")
        return 0

    task = CrawlTask(
        task_type="daily_prices", status="running",
        total_items=len(stocks),
    )
    session.add(task)
    session.flush()
    task_id = task.id
    session.commit()

    results = {"total": 0, "success": 0, "fail": 0}
    errors: list[tuple[str, str]] = []

    db_url = settings.database_url
    delay = settings.crawler_delay

    print(f"🚀 开始并行抓取 {len(stocks)} 只股票 (workers={max_workers})...")
    start_ts = time.time()

    with ThreadPoolExecutor(
        max_workers=max_workers,
        initializer=_init_worker,
        initargs=(db_url,),
    ) as executor:
        fut_map = {
            executor.submit(
                _crawl_one_worker, s.id, s.code, delay,
                years_back, adjust_type,
            ): s
            for s in stocks
        }

        done = 0
        for fut in as_completed(fut_map):
            stock = fut_map[fut]
            scode, count, err = fut.result()
            done += 1

            with _worker_lock:
                if err:
                    results["fail"] += 1
                    errors.append((stock.code, err))
                else:
                    if count > 0:
                        results["success"] += 1
                    results["total"] += count

            if done % 100 == 0 or done == len(stocks):
                elapsed = time.time() - start_ts
                rate = done / elapsed if elapsed > 0 else 0
                print(
                    f"  进度: {done}/{len(stocks)}  "
                    f"成功:{results['success']} 失败:{results['fail']}  "
                    f"日线:{results['total']}  {rate:.1f}股/s"
                )

    elapsed = time.time() - start_ts
    print(f"✅ 完成: {results['total']} 条日线 "
          f"(成功{results['success']} 失败{results['fail']}) "
          f"耗时 {elapsed:.0f}s")

    # 主 session 更新 task + 记录错误
    task.status = "completed"
    task.success_items = results["success"]
    task.fail_items = results["fail"]
    session.add(task)

    for code, err_msg in errors:
        session.add(CrawlLog(
            task_id=task_id, stock_code=code,
            error_message=err_msg,
        ))

    session.commit()
    return results["total"]

