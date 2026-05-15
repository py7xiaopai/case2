"""Streamlit 数据可视化看板"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from datetime import date, timedelta

st.set_page_config(
    page_title="A 股行情数据平台",
    page_icon="📈",
    layout="wide",
)

API_BASE = "http://127.0.0.1:8000"

st.title("📈 A 股历史行情数据平台")
st.markdown("---")

# ─── 侧边栏 ─────────────────────────────────
with st.sidebar:
    st.header("🔍 股票搜索")

    q = st.text_input("输入股票代码或名称", value="")
    search_btn = st.button("搜索")

    if q and search_btn:
        try:
            resp = requests.get(f"{API_BASE}/stocks/search", params={"q": q, "limit": 10})
            if resp.status_code == 200:
                stocks = resp.json()
                if stocks:
                    st.session_state["stocks"] = stocks
                else:
                    st.info("未找到匹配的股票")
        except Exception:
            st.error("API 服务未启动，请先启动 API")

    if "stocks" in st.session_state:
        stock_options = {f"{s['code']} {s['name']} ({s['market']})": s["code"] for s in st.session_state["stocks"]}
        selected_label = st.selectbox("选择股票", list(stock_options.keys()))
        selected_code = stock_options[selected_label]

        if st.button("查看详情"):
            st.session_state["selected_code"] = selected_code

    st.markdown("---")
    st.markdown("### 📊 数据概览")
    try:
        q_resp = requests.get(f"{API_BASE}/quality")
        if q_resp.status_code == 200:
            q_data = q_resp.json()
            st.metric("股票总数", q_data.get("stock_count", 0))
            st.metric("日线数据", q_data.get("daily_prices_count", 0))
            st.metric("技术指标", q_data.get("indicator_count", 0))
            st.metric("交易日历", q_data.get("calendar_count", 0))
    except Exception:
        st.warning("API 未连接")


# ─── 主区域 ─────────────────────────────────

if "selected_code" not in st.session_state:
    st.info("👈 在侧边栏搜索并选择股票以查看详情")
else:
    code = st.session_state["selected_code"]

    try:
        # 获取详情
        detail = requests.get(f"{API_BASE}/stocks/{code}").json()
        st.header(f"{detail.get('name', code)} ({code})")
        col1, col2, col3 = st.columns(3)
        col1.metric("市场", detail.get("market", "-"))
        col2.metric("行业", detail.get("industry", "-") or "-")
        col3.metric("上市日期", detail.get("listing_date", "-") or "-")

        # 获取行情
        end = date.today()
        start = end - timedelta(days=365)
        prices = requests.get(
            f"{API_BASE}/stocks/{code}/prices",
            params={"start": str(start), "end": str(end), "limit": 250},
        ).json()

        if prices:
            df = pd.DataFrame(prices)
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date")

            # K-line chart with volume
            fig = make_subplots(
                rows=2, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.05,
                row_heights=[0.7, 0.3],
            )

            fig.add_trace(
                go.Candlestick(
                    x=df["date"],
                    open=df["open"], close=df["close"],
                    high=df["high"], low=df["low"],
                    name="K线",
                ),
                row=1, col=1,
            )

            colors = ["red" if v is not None and v >= 0 else "green" for v in df.get("pct_change", [0])]
            fig.add_trace(
                go.Bar(x=df["date"], y=df["volume"], name="成交量", marker_color=colors),
                row=2, col=1,
            )

            fig.update_layout(
                title=f"{detail.get('name', code)} K线图",
                xaxis_title="日期",
                yaxis_title="价格",
                height=600,
                xaxis_rangeslider_visible=False,
            )
            fig.update_yaxes(title_text="价格", row=1, col=1)
            fig.update_yaxes(title_text="成交量", row=2, col=1)

            st.plotly_chart(fig, use_container_width=True)

            # Recent price table
            st.subheader("📋 近期行情")
            display_df = df.tail(20).copy()
            display_df["date"] = display_df["date"].dt.strftime("%Y-%m-%d")
            display_df = display_df[["date", "open", "close", "high", "low", "volume", "amount", "pct_change"]]
            display_df.columns = ["日期", "开盘", "收盘", "最高", "最低", "成交量", "成交额", "涨跌幅(%)"]
            st.dataframe(display_df, use_container_width=True)

        # 获取技术指标
        indicators = requests.get(
            f"{API_BASE}/stocks/{code}/indicators",
            params={"limit": 200},
        ).json()

        if indicators:
            indf = pd.DataFrame(indicators)
            indf["date"] = pd.to_datetime(indf["date"])
            indf = indf.sort_values("date")

            # MACD chart
            st.subheader("📊 MACD 指标")
            fig_macd = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05)

            # Price + MA
            fig_macd.add_trace(
                go.Scatter(x=indf["date"], y=indf["ma20"], name="MA20", line=dict(color="orange")),
                row=1, col=1,
            )
            fig_macd.add_trace(
                go.Scatter(x=indf["date"], y=indf["ma60"], name="MA60", line=dict(color="purple")),
                row=1, col=1,
            )
            if prices and len(prices) > 0:
                fig_macd.add_trace(
                    go.Scatter(x=df["date"], y=df["close"], name="收盘价", line=dict(color="blue")),
                    row=1, col=1,
                )

            # MACD bars
            macd_colors = ["red" if v >= 0 else "green" for v in indf["macd_bar"].fillna(0)]
            fig_macd.add_trace(
                go.Bar(x=indf["date"], y=indf["macd_bar"], name="MACD柱", marker_color=macd_colors),
                row=2, col=1,
            )
            fig_macd.add_trace(
                go.Scatter(x=indf["date"], y=indf["macd_dif"], name="DIF", line=dict(color="blue")),
                row=2, col=1,
            )
            fig_macd.add_trace(
                go.Scatter(x=indf["date"], y=indf["macd_dea"], name="DEA", line=dict(color="red")),
                row=2, col=1,
            )

            fig_macd.update_layout(height=500, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig_macd, use_container_width=True)

    except requests.exceptions.ConnectionError:
        st.error("❌ API 服务未运行。请先启动: PYTHONPATH=src uvicorn stock_platform.api.main:app --reload")
    except Exception as e:
        st.error(f"❌ 加载失败: {e}")
