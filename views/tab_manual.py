import streamlit as st
import numpy as np
from utils.data_fetcher import get_daily_hfq_data
from backtest.engine import run_backtest, plot_equity_curve
from backtest.optimizer import apply_advanced_filters
from components.charts import plot_interactive_kline
from configs.settings import get_backtest_config
from strategies.base import StrategyRegistry

bt_conf = get_backtest_config()


def render_manual_tab(symbol, start_date, end_date, initial_capital, global_filters, strategy_type):
    st.markdown(f"### 🎛️ {strategy_type} - 手动深度回测")

    strategy = StrategyRegistry.get(strategy_type)
    if not strategy:
        st.error(f"❌ 找不到策略实例：{strategy_type}")
        return

    with st.container(border=True):
        st.subheader("⚙️ 信号参数")
        param_values = {}

        # 🚀 1. 参数类型分离：数值型用于输入框，布尔型用于开关
        num_params = {k: v for k, v in strategy.params.items() if not isinstance(v.default, bool)}
        bool_params = {k: v for k, v in strategy.params.items() if isinstance(v.default, bool)}

        # 🚀 2. 渲染数值型参数（紧凑列排版）
        if num_params:
            num_cols = st.columns(len(num_params))
            for i, (p_name, p_def) in enumerate(num_params.items()):
                with num_cols[i]:
                    step = p_def.step if p_def.step else 1
                    min_val = type(p_def.default)(p_def.min_val) if p_def.min_val is not None else None
                    max_val = type(p_def.default)(p_def.max_val) if p_def.max_val is not None else None
                    param_values[p_name] = st.number_input(
                        p_def.description or p_name,
                        min_value=min_val, max_value=max_val, value=p_def.default, step=step,
                        key=f"m_{strategy_type}_{p_name}"
                    )

        # 🚀 3. 渲染布尔型参数（单独一行，美观的 Toggle 开关）
        if bool_params:
            st.write("")  # 留点呼吸空间
            bool_cols = st.columns(len(bool_params))
            for i, (p_name, p_def) in enumerate(bool_params.items()):
                with bool_cols[i]:
                    param_values[p_name] = st.toggle(
                        f"🛠️ {p_def.description or p_name}",
                        value=p_def.default,
                        key=f"m_{strategy_type}_{p_name}"
                    )

        st.divider()

        # 🚀 4. 执行操作区（底部对齐）
        c_pos, c_btn = st.columns([2, 1])
        with c_pos:
            pos_ratio = st.slider("买入仓位比例", 0.1, 1.0, 1.0, key="m_pos")
        with c_btn:
            st.write("")  # 下沉对齐滑块
            run_btn = st.button("🚀 执行完整回测", use_container_width=True, type="primary", key="m_run")

    if run_btn:
        with st.spinner('回测计算中...'):
            raw_data = get_daily_hfq_data(symbol, start_date, end_date)
            if raw_data is not None and not raw_data.empty:
                # 调用底层接口，直接传入组装好的参数字典
                strat_df = strategy.generate_signals(raw_data, **param_values)

                # ========= 以下逻辑保持完全不变 =========
                index_data = get_daily_hfq_data(bt_conf.BENCHMARK_CODE, start_date, end_date) if global_filters[
                    'use_index'] else None
                strat_df = apply_advanced_filters(strat_df, index_data, global_filters)

                strat_df['final_signal'] = np.where(strat_df['filter_pass'], strat_df['signal'], 0)
                strat_df['position_diff'] = strat_df['final_signal'].diff().fillna(0)

                bt_results = run_backtest(strat_df, initial_capital, pos_ratio, global_filters)

                st.divider()
                st.subheader("🎯 明日实战执行建议")
                if bt_results is None or bt_results.empty:
                    st.warning("⚠️ 回测期间内未产生任何有效交易信号或数据不足。")
                    return
                last_day = bt_results.iloc[-1]
                last_date_str = last_day.name.strftime('%Y-%m-%d')

                c_advice, c_status = st.columns([2, 1])
                with c_advice:
                    if last_day['position_diff'] == 1:
                        st.success(
                            f"### 🏹 指令：【开盘买入】\n**依据**：{last_date_str} 策略发出开仓信号。建议明天集合竞价或开盘阶段按计划仓位买入。")
                    elif last_day['position_diff'] == -1:
                        st.error(
                            f"### 🏳️ 指令：【开盘平仓】\n**依据**：{last_date_str} 触发 {last_day.get('sell_reason', '平仓')}。请务必清仓。")
                    elif last_day['final_signal'] == 1:
                        unrealized_pct = (last_day['收盘'] - last_day.get('buy_price',
                                                                          last_day['收盘'])) / last_day.get('buy_price',
                                                                                                            1)
                        st.info(
                            f"### 💎 指令：【继续持股】\n**依据**：策略信号稳定。当前参考浮动盈亏：{unrealized_pct * 100:.2f}%。")
                    else:
                        st.write(f"### ☕ 指令：【空仓观望】\n**依据**：{last_date_str} 暂无买入信号。等待机会。")

                with c_status:
                    st.metric("最新收盘价", f"¥{last_day['收盘']:.2f}")
                    st.metric("信号状态", "看多 (Long)" if last_day['final_signal'] == 1 else "看空 (Flat)")

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
                            lambda x: "🔴 建立仓位" if x > 0 else "🟢 清仓出局")
                        if 'sell_reason' not in detail_df.columns: detail_df['sell_reason'] = ""
                        detail_df = detail_df.rename(
                            columns={'收盘': '成交价', 'sell_reason': '离场原因', 'strategy_equity': '策略净值'})
                        st.dataframe(detail_df[['动作', '成交价', '离场原因', '策略净值']], use_container_width=True)