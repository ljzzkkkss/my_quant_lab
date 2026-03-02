import streamlit as st
from datetime import datetime, timedelta
import os
import logging
from strategies import StrategyRegistry
from utils.stock_info import get_a_share_list_display as get_all_stock_list
from views.tab_manual import render_manual_tab
from views.tab_auto import render_auto_tab
from views.tab_batch import render_batch_tab
from views.tab_portfolio import render_portfolio_tab
from configs.settings import get_ui_config,get_data_config

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

ui_conf = get_ui_config()
data_conf = get_data_config()


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
        # 🚀 1. 动态生成所有策略的 Tips 指南
        available_strategies = StrategyRegistry.list_strategies()
        strategy_tips = "**💡 策略流派库指南：**\n\n"
        for name in available_strategies:
            strat = StrategyRegistry.get(name)
            strategy_tips += f"- **{name}**: {strat.description}\n"

        # 🚀 2. 渲染联动下拉框
        strategy_type = st.selectbox(
            "🧠 核心策略模型",
            available_strategies,
            key="global_strategy",
            help=strategy_tips
        )

        # 🚀 3. 实时高亮显示当前选中策略的说明
        current_strat = StrategyRegistry.get(strategy_type)
        if current_strat:
            st.info(f"🎯 **当前策略**：{current_strat.description}")

        initial_capital = st.number_input("初始资金 (元)", 10000, 1000000, 100000, step=10000, key="global_capital")
        today = datetime.now()
        start_date = st.date_input("开始日期", today - timedelta(days=365), key="date_start")
        end_date = st.date_input("结束日期", today, key="date_end")
        st.divider()
        st.header("🛡️ 资金管理与防守纪律")

        # 传统硬性止盈止损
        global_tp = st.number_input("硬性止盈 (建议调高，让利润奔跑 %)", 1, 300, 30, key="g_tp",
                                    help="如果开启追踪止损，建议将硬性止盈调高到 50% 以上") / 100.0
        global_sl = st.number_input("绝对止损 (跌破无条件出局 %)", -50, -1, -8, key="g_sl") / 100.0

        # 🚀 引入跟踪止损核武器 UI
        st.write("")
        use_trailing = st.toggle("📈 开启动态跟踪止损 (Trailing Stop)", value=False, key="tg_trail")
        if use_trailing:
            with st.container(border=True):
                trail_act = st.slider("🎯 激活门槛 (盈利超过该比例启动)", 1, 50, 10) / 100.0
                trail_rate = st.slider("🔪 撤退红线 (从峰值回撤即平仓)", 1, 30, 5) / 100.0
        else:
            trail_act, trail_rate = 0.10, 0.05
        st.divider()
        st.header("🛡️ 过滤引擎 (实战宽松版)")
        use_index = st.toggle("开启大盘择时 (HS300)", value=False, key="tg_index")

        # 🚀 修复1：如果开启大盘择时，允许选择均线周期
        if use_index:
            index_ma_period = st.number_input("大盘均线过滤周期", min_value=5, max_value=250, value=20, step=5,
                                              key="ni_idx_ma")
        else:
            index_ma_period = 20
        vol_ratio = st.slider("成交量放大倍数 (量比)", 0.0, 3.0, 0.0, 0.1, key="sl_vol")
        rsi_limit = st.slider("RSI 超买拦截阈值", 50, 95, 90, key="sl_rsi")
        slope_min = st.slider("趋势最小向上斜率", -0.5, 1.0, -0.2, 0.1, key="sl_slope")

        # 🚀 新增：将硬核交易设置推向前端
        st.divider()
        st.header("⚖️ 交易成本与环境配置")
        with st.expander("🛠️ 自定义手续费与滑点", expanded=False):
            buy_fee = st.number_input("买入费率 (‱)", 0.0, 30.0, 3.0, 0.5, help="默认万三") / 10000.0
            sell_fee = st.number_input("卖出费率 (含印花税 ‱)", 0.0, 50.0, 8.0, 0.5, help="默认万八") / 10000.0
            min_comm = st.number_input("单笔最低手续费 (元)", 0.0, 50.0, 5.0, 1.0)
            slippage = st.number_input("双边滑点 (‰)", 0.0, 10.0, 1.0, 0.5, help="默认千分之一") / 1000.0
            min_shares = st.number_input("最小交易单位 (股)", 1, 1000, 100, 100)

        # 🚀 修改：整合所有参数下传给底层的引擎
        global_filters = {
            'use_index': use_index, 'index_ma_period': index_ma_period,  # 新增
            'vol_ratio': vol_ratio, 'rsi_limit': rsi_limit, 'slope_min': slope_min,
            'tp': global_tp, 'sl': global_sl,
            'use_trailing': use_trailing, 'trail_act': trail_act, 'trail_rate': trail_rate,
            'buy_fee': buy_fee, 'sell_fee': sell_fee, 'min_comm': min_comm,
            'slippage': slippage, 'min_shares': int(min_shares)
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