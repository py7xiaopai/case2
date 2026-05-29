"""定时调度任务"""
import logging
from contextlib import contextmanager

from apscheduler.schedulers.blocking import BlockingScheduler

from stock_platform.crawler.daily_price import crawl_all_stocks_daily_prices
from stock_platform.crawler.stock_list import crawl_stock_list
from stock_platform.data.etl import data_quality_check
from stock_platform.data.indicators import calculate_all_indicators
from stock_platform.db.engine import SessionLocal
from stock_platform.db.models import Stock

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@contextmanager
def _db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def job_daily_update():
    """每日增量更新：抓取最新行情 + 重算指标"""
    logger.info("开始每日增量更新...")
    with _db_session() as db:
        try:
            count = crawl_all_stocks_daily_prices(db, years_back=0.02)
            logger.info(f"更新日线数据: {count} 条")

            ind_count = calculate_all_indicators(db)
            logger.info(f"更新技术指标: {ind_count} 条")

            report = data_quality_check(db)
            logger.info(f"数据质量: {report.get('issues', [])}")
        except Exception as e:
            logger.error(f"更新失败: {e}")


def job_daily_backfill():
    """每日检查缺失字段并回填新股票信息"""
    logger.info("开始每日缺失字段回填检查...")
    with _db_session() as db:
        try:
            missing = db.query(Stock).filter(
                (Stock.industry.is_(None))
                | (Stock.listing_date.is_(None))
                | (Stock.total_market_cap.is_(None))
            ).count()
            logger.info(f"发现 {missing} 条缺失记录")
        except Exception as e:
            logger.error(f"回填检查失败: {e}")


def job_weekly_stock_list():
    """每周更新股票列表"""
    logger.info("开始更新股票列表...")
    with _db_session() as db:
        try:
            count = crawl_stock_list(db)
            logger.info(f"股票列表更新完成: {count} 只")
        except Exception as e:
            logger.error(f"更新股票列表失败: {e}")


def start_scheduler():
    """启动调度器"""
    scheduler = BlockingScheduler()

    # 每日 18:00 更新行情
    scheduler.add_job(job_daily_update, "cron", hour=18, minute=0, id="daily_update")

    # 每日 18:30 检查缺失字段
    scheduler.add_job(job_daily_backfill, "cron", hour=18, minute=30, id="daily_backfill")

    # 每周日 19:00 更新股票列表
    scheduler.add_job(job_weekly_stock_list, "cron", day_of_week="sun", hour=19, minute=0, id="weekly_stock_list")

    logger.info("🚀 调度器已启动")
    logger.info("  - 每日 18:00: 增量更新行情 + 指标")
    logger.info("  - 周日 19:00: 更新股票列表")

    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("🛑 调度器已停止")


if __name__ == "__main__":
    start_scheduler()
