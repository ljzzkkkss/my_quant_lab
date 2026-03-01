import streamlit as st
from utils.data_fetcher import get_daily_hfq_data
from strategies.double_ma import apply_double_ma_strategy
from strategies.bollinger_bands import apply_bollinger_strategy
from backtest.engine import run_backtest, plot_equity_curve
from components.charts import plot_interactive_kline
import numpy as np


# 注意：这里接收 global_filters 字典
def render_manual_tab(symbol, start_date, end_date, initial_capital, global_filters, strategy_type):
    st.markdown(f"### 🎛️ {strategy_type} - 参数手动控制")

    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])

    if strategy_type == "双均线动能策略":
        with col1:
            short_w = st.number_input("短期均线", 2, 60, 5)
        with col2:
            long_w = st.number_input("长期均线", 5, 250, 20)
        params = (short_w, long_w)
    else:
        with col1:
            window = st.number_input("计算周期", 5, 120, 20)
        with col2:
            std_dev = st.number_input("标准差倍数", 1.0, 3.5, 2.0, 0.1)
        params = (window, std_dev)

    with col3:
        pos_ratio = st.number_input("买入仓位", 0.1, 1.0, 1.0, 0.1)
    with col4:
        st.write("")
        st.write("")
        run_btn = st.button("🚀 执行回测", use_container_width=True, type="primary")

    if run_btn:
        with st.spinner('回测计算中...'):
            raw_data = get_daily_hfq_data(symbol, start_date, end_date)
            if raw_data is not None and not raw_data.empty:
                # 1. 基础信号
                if strategy_type == "双均线动能策略":
                    strat_df = apply_double_ma_strategy(raw_data, params[0], params[1], global_filters['use_macd'])
                else:
                    strat_df = apply_bollinger_strategy(raw_data, params[0], params[1])

                # 2. 引入大盘择时数据
                index_data = None
                if global_filters['use_index']:
                    from utils.data_fetcher import get_daily_hfq_data as get_idx
                    index_data = get_idx("000300", start_date, end_date)

                # 3. 复用 optimizer 中的高级过滤逻辑 (直接导入应用)
                from backtest.optimizer import apply_advanced_filters
                strat_df = apply_advanced_filters(strat_df, index_data, global_filters)

                # 4. 融合最终信号
                strat_df['final_signal'] = np.where(strat_df['filter_pass'], strat_df['signal'], 0)
                strat_df['position_diff'] = strat_df['final_signal'].diff()

                # 5. 回测并绘图
                bt_results = run_backtest(strat_df, initial_capital, pos_ratio)

                # 指标展示
                m1, m2, m3 = st.columns(3)
                m1.metric("累计收益", f"{((bt_results['strategy_equity'].iloc[-1] / initial_capital) - 1) * 100:.2f}%")
                m2.metric("夏普比率", f"{bt_results.attrs['sharpe_ratio']:.2f}")
                m3.metric("胜率", f"{bt_results.attrs['win_rate']:.1f}%")

                st.plotly_chart(plot_equity_curve(bt_results), use_container_width=True)