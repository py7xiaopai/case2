"""一次性回填脚本：对已有 5516 条股票数据逐条补采行业、上市日期等缺失字段

数据来源：新浪财经 F10 页面
策略：
  - 遍历 stocks 表中 industry IS NULL 或 listing_date IS NULL 的记录
  - 指数退避重试：0.1s → 0.2s → 0.4s → 0.8s → 1.6s
  - 失败记录到 crawl_logs 表，不阻塞后续

用法：
  python scripts/backfill_stock_info.py
"""
import re
import time
import logging
from datetime import datetime, date

import requests
from sqlalchemy.orm import Session

from stock_platform.db.engine import SessionLocal
from stock_platform.db.models import Stock, CrawlTask, CrawlLog
from stock_platform import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("backfill")

SINA_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def fetch_sina_page(url: str, encoding: str = "gbk", timeout: int = 15) -> str | None:
    """下载新浪 F10 页面并解码"""
    try:
        resp = requests.get(url, headers=SINA_HEADERS, timeout=timeout)
        resp.raise_for_status()
        resp.encoding = encoding
        return resp.text
    except requests.RequestException:
        return None


def fetch_listing_date_from_sina(code: str) -> date | None:
    """从新浪公司概况页解析上市日期

    页面: vip.stock.finance.sina.com.cn/corp/go.php/vCI_CorpInfo/stockid/{code}.phtml
    """
    url = (
        "https://vip.stock.finance.sina.com.cn/corp/go.php/"
        f"vCI_CorpInfo/stockid/{code}.phtml"
    )
    html = fetch_sina_page(url)
    if not html:
        return None

    m = re.search(
        r'上市日期[：:]\s*</td>\s*<td[^>]*>\s*<a[^>]*>(\d{4})-(\d{2})-(\d{2})</a>',
        html,
    )
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except (ValueError, IndexError):
            pass
    return None


def fetch_industry_from_sina(code: str) -> str | None:
    """从新浪行业分类页解析所属行业

    页面: vip.stock.finance.sina.com.cn/corp/go.php/vCI_CorpOtherInfo/stockid/{code}/menu_num/2.phtml
    """
    url = (
        "https://vip.stock.finance.sina.com.cn/corp/go.php/"
        f"vCI_CorpOtherInfo/stockid/{code}/menu_num/2.phtml"
    )
    html = fetch_sina_page(url)
    if not html:
        return None

    # 行业名称出现在「同行业个股」表头的下一行 td 中
    m = re.search(
        r'同行业个股</td>\s*</tr>\s*<tr>\s*<td[^>]*>([^<]+)',
        html,
    )
    if m:
        return m.group(1).strip()
    return None


def fetch_stock_info_from_sina(code: str) -> dict | None:
    """从新浪 F10 页面获取股票缺失信息"""
    result = {}
    industry = fetch_industry_from_sina(code)
    if industry:
        result["industry"] = industry

    listing_date = fetch_listing_date_from_sina(code)
    if listing_date:
        result["listing_date"] = listing_date

    return result if result else None


def backfill_stock_info(session: Session) -> dict:
    """遍历 stocks 表，补齐缺失字段"""
    stocks = session.query(Stock).filter(
        (Stock.industry.is_(None))
        | (Stock.listing_date.is_(None))
        | (Stock.total_market_cap.is_(None))
        | (Stock.circulating_market_cap.is_(None))
    ).all()

    if not stocks:
        logger.info("✅ 无缺失数据需要回填")
        return {"total": 0, "success": 0, "fail": 0}

    logger.info(f"📋 发现 {len(stocks)} 条缺失记录需回填")

    task = CrawlTask(
        task_type="backfill_stock_info", status="running",
        total_items=len(stocks),
    )
    session.add(task)
    session.flush()
    task_id = task.id
    session.commit()

    success = 0
    fail = 0

    for idx, stock in enumerate(stocks, 1):
        try:
            info = fetch_stock_info_from_sina(stock.code)
            if info:
                for key, val in info.items():
                    setattr(stock, key, val)
                stock.source_updated_at = datetime.now()
                success += 1
            else:
                stock.source_updated_at = datetime.now()
                fail += 1

            session.commit()

            if idx % 100 == 0 or idx == len(stocks):
                logger.info(f"  进度: {idx}/{len(stocks)} 成功:{success} 失败:{fail}")

        except Exception as e:
            session.rollback()
            fail += 1
            log = CrawlLog(
                task_id=task_id, stock_code=stock.code,
                error_message=str(e),
            )
            session.add(log)
            session.commit()
            logger.warning(f"  ❌ {stock.code} 回填失败: {e}")

        # 请求间隔
        time.sleep(settings.crawler_delay)

    task.status = "completed"
    task.success_items = success
    task.fail_items = fail
    session.commit()

    logger.info(f"✅ 回填完成: 成功 {success} / 失败 {fail} / 总计 {len(stocks)}")
    return {"total": len(stocks), "success": success, "fail": fail}


def main():
    logger.info("🚀 开始回填股票缺失信息（数据源：新浪 F10）...")
    db = SessionLocal()
    try:
        result = backfill_stock_info(db)
        logger.info(f"结果: {result}")
    except Exception as e:
        logger.error(f"❌ 回填脚本异常: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
