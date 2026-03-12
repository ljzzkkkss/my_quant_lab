import streamlit as st
import os
from datetime import datetime, timedelta
from views.tab_arena import render_arena_tab
from utils.logger import logger
from utils.workspace import save_workspace, load_workspace
from utils.stock_info import get_a_share_list_display as get_all_stock_list
from views.tab_manual import render_manual_tab
from views.tab_auto import render_auto_tab
from views.tab_batch import render_batch_tab
from views.tab_portfolio import render_portfolio_tab
from configs.settings import get_ui_config,get_data_config,get_filter_config
from strategies.base import StrategyRegistry
from views.tab_realtime import render_realtime_tab

ui_conf = get_ui_config()
data_conf = get_data_config()
filter_conf = get_filter_config()


logger.info("💻 Web UI 界面开始渲染...")

def main():
    st.set_page_config(page_title=ui_conf.PAGE_TITLE, page_icon=ui_conf.PAGE_ICON, layout=ui_conf.LAYOUT_MODE)
    st.title("🚀 极客量化实验室 - 全维度寻优系统")

    # 🚀 2. 启动时自动恢复工作区配置到内存
    if 'workspace_loaded' not in st.session_state:
        saved_state = load_workspace()
        for k, v in saved_state.items():
            # 🚀 增加安全锁：如果是按钮的 key，直接丢弃，不放入 session_state
            if k.startswith("btn_") or k.endswith("_run") or k.endswith("_done"):
                continue
            st.session_state[k] = v
        st.session_state['workspace_loaded'] = True
        logger.info("♻️ UI 状态已从工作区恢复。")

    with st.sidebar:
        # 🚀 3. 增加工作区存档按钮面板
        st.header("💾 工作区状态")
        c_save, c_reset = st.columns(2)
        if c_save.button("保存当前配置", use_container_width=True):
            if save_workspace(st.session_state):
                st.toast("✅ 所有参数已永久保存！", icon="💾")
        if c_reset.button("恢复默认值", use_container_width=True):
            st.session_state.clear()
            st.rerun()

        st.divider()
        if st.button("🔄 强制更新股票代码库", use_container_width=True, key="btn_update"):
            # 🚀 放在不受缓存影响的 UI 视图层绝对安全！
            st.toast("正在云端同步全市场 5000+ A股与 ETF，请稍候...", icon="🔄")

            if os.path.exists(data_conf.STOCK_LIST_CACHE):
                os.remove(data_conf.STOCK_LIST_CACHE)
            st.cache_data.clear()
            st.rerun()

        st.divider()
        # 🚀 1. 恢复：动态生成所有策略的 Tips 指南
        available_strategies = StrategyRegistry.list_strategies()
        strategy_tips = "**💡 策略流派库指南：**\n\n"
        for name in available_strategies:
            strat = StrategyRegistry.get(name)
            strategy_tips += f"- **{name}**: {strat.description}\n"

        # 🚀 2. 恢复：渲染带有 help 悬浮提示的联动下拉框
        strategy_type = st.selectbox(
            "🧠 核心策略模型",
            available_strategies,
            key="global_strategy",
            help=strategy_tips
        )

        # 🚀 3. 恢复：实时高亮显示当前选中策略的说明
        current_strat = StrategyRegistry.get(strategy_type)
        if current_strat:
            st.info(f"🎯 **当前策略**：{current_strat.description}")

        initial_capital = st.number_input("初始资金 (元)", 10000, 1000000, 100000, step=10000, key="global_capital")
        today = datetime.now()
        start_date = st.date_input("开始日期", today - timedelta(days=365), key="date_start")
        end_date = st.date_input("结束日期", today, key="date_end")

        st.divider()
        st.header("🛡️ 资金管理与防守纪律")
        global_tp = st.number_input("硬性止盈 (%)", 1, 300, 30, key="g_tp") / 100.0
        global_sl = st.number_input("绝对止损 (%)", -50, -1, -8, key="g_sl") / 100.0

        st.write("")
        use_trailing = st.toggle("📈 开启动态跟踪止损", value=False, key="tg_trail")
        if use_trailing:
            with st.container(border=True):
                trail_act = st.slider("🎯 激活门槛 (%)", 1, 50, 10, key="sl_t_act") / 100.0
                trail_rate = st.slider("🔪 回撤红线 (%)", 1, 30, 5, key="sl_t_rate") / 100.0
        else:
            trail_act, trail_rate = 0.10, 0.05

        st.divider()
        st.header("🛡️ 过滤引擎 (实战宽松版)")
        use_index = st.toggle("开启大盘择时 (HS300)", value=False, key="tg_index")
        if use_index:
            index_ma_period = st.number_input("大盘均线过滤周期", min_value=5, max_value=250, value=20, step=5, key="ni_idx_ma")
        else:
            index_ma_period = 20
        use_sector = st.toggle("🎯 开启板块共振过滤", value=False, key="tg_sector")
        if use_sector:
            sector_code = st.text_input("输入代表性行业 ETF 代码 (如 512760 半导体)", value="512760", key="ti_sec_code")
            sector_ma_period = st.number_input("板块均线过滤周期", min_value=5, max_value=250, value=20, step=5,
                                               key="ni_sec_ma")
        else:
            sector_code = ""
            sector_ma_period = 20
        vol_ratio = st.slider("成交量放大倍数 (量比)", 0.0, 3.0, 0.0, 0.1, key="sl_vol")
        rsi_limit = st.slider("RSI 超买拦截阈值", 50, 95, 90, key="sl_rsi")
        slope_min = st.slider("趋势最小向上斜率", -0.5, 1.0, -0.2, 0.1, key="sl_slope")

        st.divider()
        st.header("🧠 AI 机器学习引擎 (Meta-Labeling)")
        with st.expander("ℹ️ 使用说明与 ETF 探针建议", expanded=False):
            st.markdown("""
            **🎯 核心原理与影响**
            这是一个**“一票否决”**防骗线系统。当传统策略（如 MACD 金叉）发出版买入信号时，AI 会回顾该股历史表现，结合当前的宏观/地缘环境，预测本次买入未来 5 天赚钱的概率。
            * **影响**：交易频次会大幅下降（滤除杂波），但**胜率和抗回撤能力将发生质的飞跃**。

            **🛠️ 如何使用**
            1. 开启下方开关，设定“最低胜率放行阈值”（震荡市建议调高至 55%-60%）。
            2. 可选：勾选外部探针。AI 会自动提取这些 ETF 的动能和波动率作为额外“特征”进行学习。

            **📡 探针 ETF 代码推荐库**
            * **🌍 宏观情绪探针** (感知风险与流动性)
                * `518880` (黄金 ETF) - 避险情绪、通胀预期 (默认推荐)
                * `513500` (标普 500) - 外部环境与外资风险偏好
                * `511010` (国债 ETF) - 国内市场流动性宽裕度
            * **🔥 地缘恐慌探针** (感知冲突与博弈)
                * `512710` (原油 ETF) - 中东局势、全球能源危机 (默认推荐)
                * `512670` (军工 ETF) - 区域摩擦、中美科技/军工博弈
            """)
        use_ml = st.toggle("🤖 开启智能胜率预测拦截", value=False, key="tg_ml",
                           help="系统将根据个股历史股性，使用逻辑回归动态预测该买点未来5天上涨概率。概率过低则强行拦截信号。")
        if use_ml:
            ml_threshold = st.slider("最低胜率放行阈值 (%)", 30, 80, 50, step=5, key="sl_ml_th") / 100.0
            st.markdown("**(可选) 外部因子探针**")
            use_macro = st.checkbox("🌍 宏观情绪探针 (默认:黄金)", value=False, key="chk_macro")
            macro_code = st.text_input("宏观 ETF 代码", value=getattr(filter_conf, 'DEFAULT_MACRO_ETF', '518880'),
                                       key="ti_macro") if use_macro else ""

            use_geo = st.checkbox("🔥 地缘恐慌探针 (默认:原油)", value=False, key="chk_geo")
            geo_code = st.text_input("地缘 ETF 代码", value=getattr(filter_conf, 'DEFAULT_GEO_ETF', '512710'),
                                     key="ti_geo") if use_geo else ""
        else:
            ml_threshold = 0.50
            use_macro = False
            macro_code = ""
            use_geo = False
            geo_code = ""
        st.divider()
        st.header("⚖️ 交易成本与环境配置")
        with st.expander("🛠️ 自定义手续费与滑点", expanded=False):
            buy_fee = st.number_input("买入费率 (‱)", 0.0, 30.0, 3.0, 0.5, key="ni_buy_fee") / 10000.0
            sell_fee = st.number_input("卖出费率 (含印花税 ‱)", 0.0, 50.0, 8.0, 0.5, key="ni_sell_fee") / 10000.0
            min_comm = st.number_input("单笔最低手续费 (元)", 0.0, 50.0, 5.0, 1.0, key="ni_min_comm")
            slippage = st.number_input("双边滑点 (‰)", 0.0, 10.0, 1.0, 0.5, key="ni_slip") / 1000.0
            min_shares = st.number_input("最小交易单位 (股)", 1, 1000, 100, 100, key="ni_shares")

        global_filters = {
            'use_index': use_index, 'index_ma_period': index_ma_period,
            'use_sector': use_sector, 'sector_code': sector_code, 'sector_ma_period': sector_ma_period,
            'vol_ratio': vol_ratio, 'rsi_limit': rsi_limit, 'slope_min': slope_min,
            'use_ml_filter': use_ml, 'ml_threshold': ml_threshold,
            'use_macro': use_macro, 'macro_code': macro_code,  # 🚀 打包宏观参数
            'use_geo': use_geo, 'geo_code': geo_code,
            'tp': global_tp, 'sl': global_sl,
            'use_trailing': use_trailing, 'trail_act': trail_act, 'trail_rate': trail_rate,
            'buy_fee': buy_fee, 'sell_fee': sell_fee, 'min_comm': min_comm,
            'slippage': slippage, 'min_shares': int(min_shares)
        }

    display_list = get_all_stock_list()
    default_idx = next((i for i, s in enumerate(display_list) if "600519" in s), 0)

    tab_manual, tab_auto, tab_batch, tab_port, tab_arena, tab_realtime = st.tabs([
        "📊 手动回测看板", "🤖 机器参数寻优", "📡 雷达全场扫描", "🧺 组合轮动", "🏟️ 策略角斗场", "⚡ 盘中实时狙击"
    ])

    with tab_manual:
        sym_manual = st.selectbox("🔍 选择分析标的", display_list, index=default_idx, key="m_s").split('(')[-1].replace(
            ')', '').strip()
        render_manual_tab(sym_manual, start_date.strftime('%Y%m%d'), end_date.strftime('%Y%m%d'), initial_capital,
                          global_filters, strategy_type)
    with tab_auto:
        sym_auto = st.selectbox("🔍 选择分析标的", display_list, index=default_idx, key="a_s").split('(')[-1].replace(
            ')', '').strip()
        render_auto_tab(sym_auto, start_date.strftime('%Y%m%d'), end_date.strftime('%Y%m%d'), initial_capital,
                        global_filters, strategy_type)
    with tab_batch:
        render_batch_tab(display_list, start_date.strftime('%Y%m%d'), end_date.strftime('%Y%m%d'), initial_capital,
                         global_filters, strategy_type)
    with tab_port:
        render_portfolio_tab(display_list, start_date.strftime('%Y%m%d'), end_date.strftime('%Y%m%d'), initial_capital,
                             global_filters, strategy_type)
    # 🚀 渲染新增的角斗场
    with tab_arena:
        render_arena_tab(display_list, start_date.strftime('%Y%m%d'), end_date.strftime('%Y%m%d'), initial_capital, global_filters)

    # 🚀 渲染新增的 实时狙击 Tab
    with tab_realtime:
        render_realtime_tab(display_list, start_date.strftime('%Y%m%d'), end_date.strftime('%Y%m%d'), initial_capital, global_filters, strategy_type)

if __name__ == "__main__":
    main()