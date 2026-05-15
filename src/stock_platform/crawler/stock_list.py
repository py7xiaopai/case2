"""股票列表抓取模块 —— 从新浪财经网页接口抓取"""
import time
import requests
import json
from sqlalchemy.orm import Session
from stock_platform.db.models import Stock, CrawlTask
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


def crawl_stock_list(session: Session) -> int:
    """从新浪财经网页接口抓取沪深京全部 A 股，入库"""
    task = CrawlTask(task_type="stock_list", status="running", total_items=0)
    session.add(task)
    session.flush()

    try:
        stocks = _fetch_from_sina()
        count = 0
        for s in stocks:
            existing = session.query(Stock).filter_by(code=s["code"]).first()
            if existing:
                for key, val in s.items():
                    setattr(existing, key, val)
            else:
                session.add(Stock(**s))
            count += 1

        session.flush()
        task.status = "completed"
        task.success_items = count
        task.total_items = count
        session.commit()
        return count

    except Exception as e:
        task.status = "failed"
        task.error_message = str(e)
        session.commit()
        raise


def _fetch_from_sina() -> list[dict]:
    """从新浪财经市场中心逐页抓取 A 股列表

    数据来源: vip.stock.finance.sina.com.cn
    和新浪网页「沪深股市」标签页数据完全一致
    """
    http = requests.Session()
    http.trust_env = False
    http.headers.update(WEB_HEADERS)

    stocks = []
    seen_codes = set()

    # 从新浪的 hs_a 节点抓全量 A 股
    page = 1
    page_size = 100  # 新浪 API 硬限制每页最多 100 条

    while True:
        url = (
            "https://vip.stock.finance.sina.com.cn/quotes_service/"
            "api/json_v2.php/Market_Center.getHQNodeData"
            f"?page={page}&num={page_size}&sort=symbol&asc=1"
            "&node=hs_a&symbol=&_s_r_a=init"
        )

        try:
            resp = http.get(url, timeout=settings.crawler_timeout)
            resp.encoding = "gbk"
            text = resp.text.strip()
        except Exception as e:
            print(f"  抓取失败(page={page}): {e}")
            break

        if not text or text == "null":
            break

        if text.startswith("["):
            data = json.loads(text)
        else:
            idx = text.find("[")
            if idx >= 0:
                data = json.loads(text[idx:])
            else:
                break

        if not data:
            break

        for item in data:
            symbol = str(item.get("symbol", ""))
            name = item.get("name", "")
            if not symbol or not name:
                continue

            code = symbol
            for prefix in ["bj", "sh", "sz"]:
                if code.startswith(prefix):
                    code = code[len(prefix):]
                    break

            if code in seen_codes:
                continue
            seen_codes.add(code)

            # 根据代码前缀判断市场
            if code.startswith("6"):
                market = "SH"
            elif code.startswith(("0", "3")):
                market = "SZ"
            elif code.startswith(("8", "4", "92")):
                market = "BJ"
            else:
                market = "SH" if symbol.startswith("sh") else "SZ"

            stocks.append({
                "code": code,
                "name": name,
                "market": market,
            })

        if len(data) < page_size:
            break
        page += 1
        time.sleep(settings.crawler_delay)

    return stocks
