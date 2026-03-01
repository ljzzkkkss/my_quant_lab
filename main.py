import streamlit as st
from datetime import datetime, timedelta
import os

# --- 修正导入路径 ---
from utils.stock_info import get_a_share_list
from views.tab_manual import render_manual_tab
from views.tab_auto import render_auto_tab
from views.tab_batch import render_batch_tab

st.set_page_config(page_title="极客量化实验室", layout="wide", page_icon="📈")


def main():
    st.title("🚀 极客量化实验室 - 全维度寻优系统")

    # --- 1. 侧边栏：全局配置与高级过滤器 ---
    with st.sidebar:
        st.header("⚙️ 全局设置")
        if st.button("🔄 强制更新股票代码库", use_container_width=True):
            if os.path.exists("data/stock_list_cache.csv"):
                os.remove("data/stock_list_cache.csv")
            st.cache_data.clear()
            st.rerun()

        st.divider()
        initial_capital = st.number_input("初始资金 (元)", 10000, 1000000, 100000, step=10000)

        today = datetime.now()
        start_date = st.date_input("开始日期", today - timedelta(days=365))
        end_date = st.date_input("结束日期", today)

        st.divider()
        st.header("🛡️ 过滤引擎")
        use_macd = st.toggle("开启 MACD 动能过滤", value=True)
        use_index = st.toggle("开启大盘择时 (HS300)", value=True)
        vol_ratio = st.slider("成交量放大倍数 (量比)", 0.0, 3.0, 1.2, 0.1)
        rsi_limit = st.slider("RSI 超买拦截阈值", 50, 95, 80)
        slope_min = st.slider("趋势最小向上斜率", -0.5, 1.0, 0.0, 0.1)

        global_filters = {
            'use_macd': use_macd,
            'use_index': use_index,
            'vol_ratio': vol_ratio,
            'rsi_limit': rsi_limit,
            'slope_min': slope_min
        }

    # --- 2. 顶部选择区 ---
    col1, col2 = st.columns([2, 1])
    with col1:
        display_list = get_a_share_list()
        selected_stock_display = st.selectbox("🔍 选择分析标的", display_list, index=0)
        symbol = selected_stock_display.split('(')[-1].replace(')', '')

    with col2:
        strategy_type = st.selectbox("🧠 策略模型", ["双均线动能策略", "布林带突破策略"])

    # --- 3. 标签页切换 ---
    tab_manual, tab_auto, tab_batch = st.tabs(["📊 手动回测看板", "🤖 机器参数寻优", "📡 雷达全场扫描"])

    with tab_manual:
        render_manual_tab(symbol, start_date.strftime('%Y%m%d'), end_date.strftime('%Y%m%d'), initial_capital,
                          global_filters, strategy_type)

    with tab_auto:
        render_auto_tab(symbol, start_date.strftime('%Y%m%d'), end_date.strftime('%Y%m%d'), initial_capital,
                        global_filters, strategy_type)

    with tab_batch:
        render_batch_tab(display_list, start_date.strftime('%Y%m%d'), end_date.strftime('%Y%m%d'), initial_capital,
                         global_filters, strategy_type)


if __name__ == "__main__":
    main()