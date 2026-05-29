"""Streamlit 数据可视化看板 — v0.2.0

重构内容 (DEVELOPMENT_PLAN.md Phase 3):
  - 侧边栏数字千分位 + 单位说明
  - 详情卡片 5字段3列布局，空值显示"暂无"
  - 市值自动换算：元 → 亿/万亿
  - K 线图 MA5/MA10/MA20 + rangeslider + hovermode
  - 成交量涨红跌绿，与 K 线颜色联动
  - MACD 柱正红负绿，图例右上角
  - 近期行情表：千分位、万手、涨跌颜色、最近交易日高亮、滚动
"""
import os
from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from plotly.subplots import make_subplots

st.set_page_config(
    page_title="A 股行情数据平台",
    page_icon="📈",
    layout="wide",
)

API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")
TIMEOUT = 5


# ─── 工具函数 ───────────────────────────────────────


def format_num(v, decimals=0):
    """数字千分位格式化"""
    if v is None:
        return "暂无"
    try:
        return f"{v:,.{decimals}f}"
    except (ValueError, TypeError):
        return "暂无"


def format_market_cap(value):
    """市值自动换算规则
       < 1 亿     → x.xx 万
       1 亿 ~ 1 万亿 → x.xx 亿
       >= 1 万亿  → x.xx 万亿
    """
    if value is None:
        return "暂无"
    try:
        v = float(value)
    except (ValueError, TypeError):
        return "暂无"
    if v < 1e8:
        return f"{v / 1e4:,.2f} 万"
    elif v < 1e12:
        return f"{v / 1e8:,.2f} 亿"
    else:
        return f"{v / 1e12:,.2f} 万亿"


def format_volume_to_wan(v):
    """成交量从股转为万手"""
    if v is None:
        return "暂无"
    try:
        return f"{int(v) / 1e4:,.2f}"
    except (ValueError, TypeError):
        return "暂无"


def _extract(resp):
    """从统一 API 响应中提取 data 字段"""
    body = resp.json()
    return body.get("data", body) if isinstance(body, dict) else body


def color_pct(v, inverse=False):
    """涨跌颜色"""
    if v is None:
        return ""
    try:
        val = float(v)
    except (ValueError, TypeError):
        return ""
    if inverse:
        return "color: green" if val > 0 else ("color: red" if val < 0 else "")
    return "color: red" if val > 0 else ("color: green" if val < 0 else "")


def style_pct(v):
    """涨跌幅数字带符号和颜色"""
    if v is None:
        return "暂无"
    try:
        val = float(v)
        s = f"{val:+.2f}%"
        if val > 0:
            return f'<span style="color:red">{s}</span>'
        elif val < 0:
            return f'<span style="color:green">{s}</span>'
        return s
    except (ValueError, TypeError):
        return "暂无"


# ─── 侧边栏 ─────────────────────────────────────

with st.sidebar:
    st.header("🔍 股票搜索")

    q = st.text_input("输入股票代码或名称", value="")
    search_btn = st.button("搜索")

    if q and search_btn:
        try:
            resp = requests.get(f"{API_BASE}/stocks/search", params={"q": q, "limit": 10}, timeout=TIMEOUT)
            if resp.status_code == 200:
                stocks = _extract(resp)
                if stocks:
                    st.session_state["stocks"] = stocks
                else:
                    st.info("未找到匹配的股票")
        except requests.ConnectionError:
            st.error("API 服务未启动")
        except Exception:
            st.error("搜索失败")

    if "stocks" in st.session_state:
        opts = st.session_state["stocks"]
        stock_options = {f"{s['code']} {s['name']} ({s.get('market', s.get('exchange', '-'))})": s["code"] for s in opts}
        selected_label = st.selectbox("选择股票", list(stock_options.keys()))
        selected_code = stock_options[selected_label]

        if st.button("查看详情"):
            st.session_state["selected_code"] = selected_code

    st.markdown("---")
    st.markdown("### 📊 数据概览")
    try:
        q_resp = requests.get(f"{API_BASE}/quality", timeout=TIMEOUT)
        if q_resp.status_code == 200:
            qd_data = _extract(q_resp)
            st.metric("股票总数", f"{format_num(qd_data.get('stock_count', 0))} 家")
            st.metric("日线数据", f"{format_num(qd_data.get('daily_prices_count', 0))} 条")
            st.metric("技术指标", f"{format_num(qd_data.get('indicator_count', 0))} 条")
            st.metric("交易日历", f"{format_num(qd_data.get('calendar_count', 0))} 天")
            # 更新时间展示
            checked_at = qd_data.get("checked_at")
            if checked_at:
                st.caption(f"🕐 更新于 {str(checked_at)[:19]}")
    except Exception:
        st.warning("API 未连接")


# ─── 主区域 ─────────────────────────────────────

if "selected_code" not in st.session_state:
    st.info("👈 在侧边栏搜索并选择股票以查看详情")
else:
    code = st.session_state["selected_code"]

    try:
        # 获取详情
        detail_resp = requests.get(f"{API_BASE}/stocks/{code}", timeout=TIMEOUT)
        if detail_resp.status_code != 200:
            st.error("股票不存在或 API 返回错误")
            st.stop()
        detail_data = _extract(detail_resp)

        name = detail_data.get("name", code)
        st.header(f"{name} ({code})")

        # ─── 详情卡片（5字段3列布局，空值显示"暂无"）───
        col1, col2, col3 = st.columns(3)
        with col1:
            market = detail_data.get("market") or detail_data.get("exchange") or "暂无"
            st.metric("交易所", market)
        with col2:
            board = detail_data.get("board") or "暂无"
            st.metric("板块", board)
        with col3:
            industry = detail_data.get("industry") or "暂无"
            st.metric("行业", industry)

        col1, col2, col3 = st.columns(3)
        with col1:
            listing_date = detail_data.get("listing_date") or "暂无"
            st.metric("上市日期", listing_date)
        with col2:
            total_mc = format_market_cap(detail_data.get("total_market_cap"))
            st.metric("总市值", total_mc)
        with col3:
            circ_mc = format_market_cap(detail_data.get("circulating_market_cap"))
            st.metric("流通市值", circ_mc)

        st.markdown("---")

        # 获取行情（K线图用 — chart 端点）
        end = date.today()
        start = end - timedelta(days=365)
        chart_resp = requests.get(
            f"{API_BASE}/stocks/{code}/chart",
            params={"start": str(start), "end": str(end)},
            timeout=TIMEOUT,
        )
        if chart_resp.status_code != 200:
            st.warning("行情数据不可用")
            st.stop()

        prices_raw = _extract(chart_resp)

        if prices_raw and isinstance(prices_raw, list):
            df = pd.DataFrame(prices_raw)
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").reset_index(drop=True)

            # ─── K 线图（含 MA5/MA10/MA20 + 成交量着色）───
            fig = make_subplots(
                rows=2, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.08,
                row_heights=[0.7, 0.3],
            )

            fig.add_trace(
                go.Candlestick(
                    x=df["date"],
                    open=df["open"], close=df["close"],
                    high=df["high"], low=df["low"],
                    name="K线",
                    increasing_line_color="red",
                    decreasing_line_color="green",
                ),
                row=1, col=1,
            )

            # MA 均线 — 从 indicators 接口获取更准确，但这里用 chart 数据计算近似值
            if len(df) >= 5:
                df["ma5"] = df["close"].rolling(5).mean()
                fig.add_trace(
                    go.Scatter(x=df["date"], y=df["ma5"],
                               name="MA5", line=dict(color="orange", width=1.5)),
                    row=1, col=1,
                )
            if len(df) >= 10:
                df["ma10"] = df["close"].rolling(10).mean()
                fig.add_trace(
                    go.Scatter(x=df["date"], y=df["ma10"],
                               name="MA10", line=dict(color="blue", width=1.5)),
                    row=1, col=1,
                )
            if len(df) >= 20:
                df["ma20"] = df["close"].rolling(20).mean()
                fig.add_trace(
                    go.Scatter(x=df["date"], y=df["ma20"],
                               name="MA20", line=dict(color="purple", width=1.5)),
                    row=1, col=1,
                )

            # 成交量涨红跌绿
            vol_colors = [
                "red" if df.loc[i, "close"] >= df.loc[i, "open"]
                else "green"
                for i in range(len(df))
            ]
            fig.add_trace(
                go.Bar(x=df["date"], y=df["volume"],
                       name="成交量", marker_color=vol_colors),
                row=2, col=1,
            )

            fig.update_layout(
                title=f"{name} K线图",
                xaxis_title="日期",
                yaxis_title="价格",
                height=600,
                hovermode="x unified",
                xaxis_rangeslider_visible=True,
                dragmode="zoom",
            )
            fig.update_yaxes(title_text="价格", row=1, col=1)
            fig.update_yaxes(title_text="成交量", row=2, col=1)

            st.plotly_chart(fig, use_container_width=True)

            # ─── 近期行情表（格式化）───
            st.subheader("📋 近期行情")
            display_df = df.tail(30).copy()
            display_df["date"] = display_df["date"].dt.strftime("%Y-%m-%d")
            display_df["volume_wan"] = display_df["volume"].apply(format_volume_to_wan)
            display_df["pct_formatted"] = display_df["pct_change"].apply(
                lambda v: f"{v:+.2f}%" if v is not None else "暂无"
            )

            table_cols = display_df[["date", "open", "close", "high", "low",
                                      "volume_wan", "pct_formatted"]].copy()
            # 数字千分位
            for col in ["open", "close", "high", "low"]:
                if col in table_cols.columns:
                    table_cols[col] = table_cols[col].apply(lambda v: f"{v:,.2f}" if pd.notna(v) else "暂无")

            table_cols.columns = ["日期", "开盘", "收盘", "最高", "最低",
                                  "成交量(万手)", "涨跌幅"]

            # 涨跌颜色样式
            def highlight_row(row):
                styles = [""] * len(row)
                # 最近交易日高亮（最后一行）
                if row.name == display_df.index[-1]:
                    styles = ["background-color: #fffacd"] * len(row)  # 浅黄
                # 涨跌幅列颜色
                pct_idx = table_cols.columns.get_loc("涨跌幅")
                try:
                    pct_val = float(display_df.loc[row.name, "pct_change"])
                    if pct_val > 0:
                        styles[pct_idx] += "color: red"
                    elif pct_val < 0:
                        styles[pct_idx] += "color: green"
                except (ValueError, TypeError, KeyError):
                    pass
                return styles

            styled_df = table_cols.style.apply(highlight_row, axis=1)
            st.dataframe(
                styled_df,
                use_container_width=True,
                height=400,
            )

        # ─── MACD 图 ─────────────────────────────
        ind_resp = requests.get(
            f"{API_BASE}/stocks/{code}/indicators",
            params={"limit": 250},
            timeout=TIMEOUT,
        )
        if ind_resp.status_code == 200:
            indicators = _extract(ind_resp)

            if indicators and isinstance(indicators, list):
                indf = pd.DataFrame(indicators)
                indf["date"] = pd.to_datetime(indf["date"])
                indf = indf.sort_values("date").reset_index(drop=True)

                st.subheader("📊 MACD 指标")
                fig_macd = make_subplots(
                    rows=2, cols=1,
                    shared_xaxes=True,
                    vertical_spacing=0.08,
                    row_heights=[0.5, 0.5],
                )

                # 上子图：收盘价 + MA20 + MA60
                if len(df) > 0 and "close" in df.columns:
                    fig_macd.add_trace(
                        go.Scatter(x=df["date"], y=df["close"],
                                   name="收盘价", line=dict(color="blue", width=1.5)),
                        row=1, col=1,
                    )
                if "ma20" in indf.columns:
                    fig_macd.add_trace(
                        go.Scatter(x=indf["date"], y=indf["ma20"],
                                   name="MA20", line=dict(color="orange", width=1.5)),
                        row=1, col=1,
                    )
                if "ma60" in indf.columns:
                    fig_macd.add_trace(
                        go.Scatter(x=indf["date"], y=indf["ma60"],
                                   name="MA60", line=dict(color="purple", width=1.5)),
                        row=1, col=1,
                    )

                # 下子图：MACD
                if "macd_bar" in indf.columns:
                    macd_colors = [
                        "red" if v >= 0 else "green"
                        for v in indf["macd_bar"].fillna(0)
                    ]
                    fig_macd.add_trace(
                        go.Bar(x=indf["date"], y=indf["macd_bar"],
                               name="MACD柱", marker_color=macd_colors),
                        row=2, col=1,
                    )
                if "macd_dif" in indf.columns:
                    fig_macd.add_trace(
                        go.Scatter(x=indf["date"], y=indf["macd_dif"],
                                   name="DIF", line=dict(color="blue", width=1.5)),
                        row=2, col=1,
                    )
                if "macd_dea" in indf.columns:
                    fig_macd.add_trace(
                        go.Scatter(x=indf["date"], y=indf["macd_dea"],
                                   name="DEA", line=dict(color="red", width=1.5)),
                        row=2, col=1,
                    )

                fig_macd.update_layout(
                    height=500,
                    hovermode="x unified",
                    legend=dict(x=0.98, y=0.98, xanchor="right", yanchor="top"),
                )
                fig_macd.update_yaxes(title_text="价格", row=1, col=1)
                fig_macd.update_yaxes(title_text="MACD", row=2, col=1)

                st.plotly_chart(fig_macd, use_container_width=True)

    except requests.ConnectionError:
        st.error("❌ API 服务未运行。请先启动: PYTHONPATH=src uvicorn stock_platform.api.main:app --reload")
    except Exception as e:
        st.error(f"❌ 加载失败: {e}")
