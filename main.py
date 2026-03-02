import streamlit as st
from datetime import datetime, timedelta
import os
import logging
from configs.settings import get_data_config
data_conf = get_data_config()

# ========== 日志配置 ==========
def setup_logger():
    """配置日志系统"""
    os.makedirs("logs", exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("logs/quant.log", encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

    # 降低第三方库日志级别
    logging.getLogger('streamlit').setLevel(logging.WARNING)
    logging.getLogger('baostock').setLevel(logging.WARNING)
    logging.getLogger('akshare').setLevel(logging.WARNING)

setup_logger()
logger = logging.getLogger(__name__)

from utils.stock_info import get_a_share_list_display as get_all_stock_list
from views.tab_manual import render_manual_tab
from views.tab_auto import render_auto_tab
from views.tab_batch import render_batch_tab
from views.tab_portfolio import render_portfolio_tab
from configs.settings import get_ui_config
ui_conf = get_ui_config()

st.set_page_config(
    page_title=ui_conf.PAGE_TITLE,
    page_icon=ui_conf.PAGE_ICON,
    layout=ui_conf.LAYOUT_MODE
)


def main():
    st.title("🚀 极客量化实验室 - 全维度寻优系统")

    # --- 1. 侧边栏：全局配置 ---
    with st.sidebar:
        st.header("⚙️ 全局设置")
        if st.button("🔄 强制更新股票代码库", use_container_width=True, key="btn_update"):
            if os.path.exists(data_conf.STOCK_LIST_CACHE):
                os.remove(data_conf.STOCK_LIST_CACHE)
            st.cache_data.clear()
            st.rerun()

        st.divider()
        strategy_tips = """
        **💡 五大流派优缺点指南：**\n
        📈 **双均线动能**：捕捉大牛股主升浪；震荡市反复打脸。\n
        🌋 **布林带突破**：专抓妖股起爆点；假突破较多。\n
        🧲 **RSI极值反转**：震荡市印钞机；单边暴跌易腰斩。\n
        🌊 **MACD趋势**：波段稳健抗骗线；信号滞后。\n
        ⚡ **KDJ震荡**：短线极其敏锐；遇主升浪易踏空。
        """
        strategy_type = st.selectbox(
            "🧠 核心策略模型",
            ["双均线动能策略", "布林带突破策略", "RSI极值反转策略", "MACD趋势策略", "KDJ震荡策略"],
            key="global_strategy",
            help=strategy_tips
        )

        initial_capital = st.number_input("初始资金 (元)", 10000, 1000000, 100000, step=10000, key="global_capital")
        today = datetime.now()
        start_date = st.date_input("开始日期", today - timedelta(days=365), key="date_start")
        end_date = st.date_input("结束日期", today, key="date_end")

        st.divider()
        st.header("🛡️ 全局交易纪律")
        # 【核心修改】：将止盈止损提升为全系统共享参数
        global_tp = st.number_input("全局硬性止盈 (%)", 1, 100, 15, key="g_tp") / 100.0
        global_sl = st.number_input("全局硬性止损 (%)", -50, -1, -8, key="g_sl") / 100.0

        st.divider()
        st.header("🛡️ 过滤引擎 (实战宽松版)")
        use_macd = st.toggle("开启 MACD 动能过滤", value=False, key="tg_macd")
        use_index = st.toggle("开启大盘择时 (HS300)", value=False, key="tg_index")
        vol_ratio = st.slider("成交量放大倍数 (量比)", 0.0, 3.0, 0.0, 0.1, key="sl_vol")
        rsi_limit = st.slider("RSI 超买拦截阈值", 50, 95, 90, key="sl_rsi")
        slope_min = st.slider("趋势最小向上斜率", -0.5, 1.0, -0.2, 0.1, key="sl_slope")

        # 整合所有全局参数
        global_filters = {
            'use_macd': use_macd, 'use_index': use_index, 'vol_ratio': vol_ratio,
            'rsi_limit': rsi_limit, 'slope_min': slope_min,
            'tp': global_tp, 'sl': global_sl  # 注入止盈止损
        }

    display_list = get_all_stock_list()
    try:
        default_idx = next(i for i, s in enumerate(display_list) if "600519" in s)
    except StopIteration:
        default_idx = 0

    tab_manual, tab_auto, tab_batch, tab_port = st.tabs(["📊 手动回测看板", "🤖 机器参数寻优", "📡 雷达全场扫描", "🧺 组合轮动"])

    with tab_manual:
        sel_manual = st.selectbox("🔍 选择分析标的", display_list, index=default_idx, key="manual_stock")
        sym_manual = sel_manual.split('(')[-1].replace(')', '').strip()
        render_manual_tab(sym_manual, start_date.strftime('%Y%m%d'), end_date.strftime('%Y%m%d'), initial_capital,
                          global_filters, strategy_type)

    with tab_auto:
        sel_auto = st.selectbox("🔍 选择分析标的", display_list, index=default_idx, key="auto_stock")
        sym_auto = sel_auto.split('(')[-1].replace(')', '').strip()
        render_auto_tab(sym_auto, start_date.strftime('%Y%m%d'), end_date.strftime('%Y%m%d'), initial_capital,
                        global_filters, strategy_type)

    with tab_batch:
        render_batch_tab(display_list, start_date.strftime('%Y%m%d'), end_date.strftime('%Y%m%d'), initial_capital,
                         global_filters, strategy_type)
    with tab_port:
        render_portfolio_tab(display_list, start_date.strftime('%Y%m%d'), end_date.strftime('%Y%m%d'), initial_capital,
                             global_filters, strategy_type)

if __name__ == "__main__":
    main()