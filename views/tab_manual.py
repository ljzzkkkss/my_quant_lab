import streamlit as st
import numpy as np
from utils.data_fetcher import get_daily_hfq_data
from strategies.double_ma import apply_double_ma_strategy
from strategies.bollinger_bands import apply_bollinger_strategy
from strategies.rsi_reversal import apply_rsi_strategy
from strategies.macd_strategy import apply_macd_strategy
from strategies.kdj_strategy import apply_kdj_strategy
from backtest.engine import run_backtest, plot_equity_curve
from backtest.optimizer import apply_advanced_filters
from components.charts import plot_interactive_kline


def render_manual_tab(symbol, start_date, end_date, initial_capital, global_filters, strategy_type):
    st.markdown(f"### 🎛️ {strategy_type} - 手动深度回测")
    with st.container(border=True):
        st.subheader("⚙️ 信号参数")
        col1, col2, col3 = st.columns(3)

        if strategy_type == "双均线动能策略":
            with col1:
                p1 = st.number_input("短期均线", 2, 60, 5, key="m_ma_s")
            with col2:
                p2 = st.number_input("长期均线", 5, 250, 20, key="m_ma_l")
        elif strategy_type == "布林带突破策略":
            with col1:
                p1 = st.number_input("计算周期", 5, 120, 20, key="m_boll_w")
            with col2:
                p2 = st.number_input("标准差倍数", 1.0, 3.5, 2.0, 0.1, key="m_boll_s")
        elif strategy_type == "RSI极值反转策略":
            with col1:
                p1 = st.number_input("抄底阈值", 10, 50, 30, key="m_rsi_b")
            with col2:
                p2 = st.number_input("逃顶阈值", 50, 95, 70, key="m_rsi_s")
        elif strategy_type == "MACD趋势策略":
            with col1:
                p1 = st.number_input("快线周期", 5, 40, 12, key="m_macd_f")
            with col2:
                p2 = st.number_input("慢线周期", 10, 100, 26, key="m_macd_s")
        elif strategy_type == "KDJ震荡策略":
            with col1:
                p1 = st.number_input("超卖抄底线", -20, 30, 0, key="m_kdj_b")
            with col2:
                p2 = st.number_input("超买逃顶线", 70, 120, 100, key="m_kdj_s")
        with col3:
            pos_ratio = st.slider("买入仓位", 0.1, 1.0, 1.0, key="m_pos")
            run_btn = st.button("🚀 执行完整回测", use_container_width=True, type="primary", key="m_run")

    if run_btn:
        with st.spinner('回测计算中...'):
            raw_data = get_daily_hfq_data(symbol, start_date, end_date)
            if raw_data is not None and not raw_data.empty:
                if strategy_type == "双均线动能策略":
                    strat_df = apply_double_ma_strategy(raw_data, p1, p2, global_filters['use_macd'])
                elif strategy_type == "布林带突破策略":
                    strat_df = apply_bollinger_strategy(raw_data, p1, p2)
                elif strategy_type == "RSI极值反转策略":
                    strat_df = apply_rsi_strategy(raw_data, p1, p2)
                elif strategy_type == "MACD趋势策略":
                    strat_df = apply_macd_strategy(raw_data, p1, p2)
                elif strategy_type == "KDJ震荡策略":
                    strat_df = apply_kdj_strategy(raw_data, p1, p2)

                index_data = get_daily_hfq_data("510300", start_date, end_date) if global_filters['use_index'] else None
                strat_df = apply_advanced_filters(strat_df, index_data, global_filters)

                strat_df['final_signal'] = np.where(strat_df['filter_pass'], strat_df['signal'], 0)
                strat_df['position_diff'] = strat_df['final_signal'].diff().fillna(0)

                bt_results = run_backtest(strat_df, initial_capital, pos_ratio, take_profit=global_filters['tp'], stop_loss=global_filters['sl'])

                m1, m2, m3, m4, m5 = st.columns(5)
                ret = ((bt_results['strategy_equity'].iloc[-1] / initial_capital) - 1) * 100
                bench_ret = ((bt_results['benchmark_equity'].iloc[-1] / initial_capital) - 1) * 100
                m1.metric("策略收益", f"{ret:.2f}%", delta=f"{ret - bench_ret:.2f}% (超额)")
                m2.metric("基准收益", f"{bench_ret:.2f}%")
                m3.metric("夏普比率", f"{bt_results.attrs['sharpe_ratio']:.2f}")
                m4.metric("胜率", f"{bt_results.attrs['win_rate']:.1f}%")
                m5.metric("交易次数", f"{bt_results.attrs['trade_count']}次")

                st.plotly_chart(plot_interactive_kline(strat_df, 5, 20, title=f"{symbol} 信号与买卖点分布"),
                                use_container_width=True)
                st.plotly_chart(plot_equity_curve(bt_results), use_container_width=True)

                with st.expander("📄 查看详细交易明细"):
                    detail_df = bt_results[bt_results['position_diff'] != 0].copy()
                    if not detail_df.empty:
                        detail_df['动作'] = detail_df['position_diff'].apply(
                            lambda x: "🟢 建立仓位" if x > 0 else "🔴 清仓出局")
                        if 'sell_reason' not in detail_df.columns: detail_df['sell_reason'] = ""
                        detail_df = detail_df.rename(columns={'收盘': '成交价', 'sell_reason': '离场原因','strategy_equity':'策略净值'})
                        st.dataframe(detail_df[['动作', '成交价', '离场原因', '策略净值']],
                                     use_container_width=True)