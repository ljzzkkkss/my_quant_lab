import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from utils.data_fetcher import get_daily_hfq_data
from backtest.optimizer import optimize_strategy, apply_advanced_filters
from backtest.engine import run_backtest, plot_equity_curve

# 导入所有策略计算底层
from strategies.double_ma import apply_double_ma_strategy
from strategies.bollinger_bands import apply_bollinger_strategy
from strategies.rsi_reversal import apply_rsi_strategy
from strategies.macd_strategy import apply_macd_strategy
from strategies.kdj_strategy import apply_kdj_strategy
from configs.settings import get_backtest_config
bt_conf = get_backtest_config()


def run_single_param_backtest(raw_data, strategy_type, p1, p2, global_filters, initial_capital, pos_ratio):
    # 1. 信号生成
    if strategy_type == "双均线动能策略":
        strat_df = apply_double_ma_strategy(raw_data, int(p1), int(p2), global_filters.get('use_macd'))
    elif strategy_type == "布林带突破策略":
        strat_df = apply_bollinger_strategy(raw_data, int(p1), float(p2))
    elif strategy_type == "RSI极值反转策略":
        strat_df = apply_rsi_strategy(raw_data, int(p1), int(p2))
    elif strategy_type == "MACD趋势策略":
        strat_df = apply_macd_strategy(raw_data, int(p1), int(p2))
    elif strategy_type == "KDJ震荡策略":
        strat_df = apply_kdj_strategy(raw_data, int(p1), int(p2))

    # 2. 过滤 (修复破坏持仓的致命Bug)
    index_data = get_daily_hfq_data(bt_conf.BENCHMARK_CODE, raw_data.index[0].strftime('%Y%m%d'),
                                    raw_data.index[-1].strftime('%Y%m%d')) if global_filters['use_index'] else None
    strat_df = apply_advanced_filters(strat_df, index_data, global_filters)

    if 'position_diff' not in strat_df.columns:
        strat_df['position_diff'] = strat_df['signal'].diff().fillna(0)
    strat_df['valid_buy'] = (strat_df['position_diff'] == 1) & strat_df['filter_pass']
    strat_df['valid_sell'] = (strat_df['position_diff'] == -1)

    strat_df['action'] = np.nan
    strat_df.loc[strat_df['valid_buy'], 'action'] = 1
    strat_df.loc[strat_df['valid_sell'], 'action'] = 0
    strat_df['final_signal'] = strat_df['action'].ffill().fillna(0)
    strat_df['position_diff'] = strat_df['final_signal'].diff().fillna(0)

    # 3. 回测
    return run_backtest(strat_df, initial_capital, pos_ratio, take_profit=global_filters['tp'],
                        stop_loss=global_filters['sl'])
def render_auto_tab(symbol, start_date, end_date, initial_capital, global_filters, strategy_type):
    stype = strategy_type.replace(" ", "")
    st.markdown(f"### 🤖 {strategy_type} - 参数寻优与稳定性检验")

    # 💡 寻优提示说明
    if strategy_type == "双均线动能策略":
        st.info("💡 **寻优目标**：寻找主力均线逻辑。短线极其敏感，步长建议设为 1；长线跨度大，步长设为 5。")

    with st.expander("🎯 自定义寻优搜索空间与步长", expanded=True):
        col_p1, col_p2 = st.columns(2)
        p1_param = p2_param = None  # 初始化变量
        la = lb = ""  # 初始化参数名称

        if stype == "双均线动能策略":
            with col_p1:
                s_range = st.slider("短期均线范围", 2, 60, (5, 15), key="a_ma_sr")
                s_step = st.number_input("短期步长", 1, 10, 1, key="a_ma_ss")
            with col_p2:
                l_range = st.slider("长期均线范围", 10, 250, (20, 60), key="a_ma_lr")
                l_step = st.number_input("长期步长", 1, 20, 5, key="a_ma_ls")
            p1_param, p2_param = (s_range[0], s_range[1], s_step), (l_range[0], l_range[1], l_step)
            la, lb = "短期均线", "长期均线"
        elif stype == "布林带突破策略":
            with col_p1:
                w_range = st.slider("周期范围", 5, 120, (10, 30), key="a_boll_wr"); w_step = st.number_input(
                    "周期步长", 1, 20, 5, key="a_boll_ws")
            with col_p2:
                std_range = st.slider("标准差范围", 1.0, 3.5, (1.5, 2.5), key="a_boll_sr"); std_step = st.number_input(
                    "标准差步长", 0.1, 1.0, 0.1, key="a_boll_ss")
            p1_param, p2_param = (w_range[0], w_range[1], w_step), (std_range[0], std_range[1], std_step)
            la, lb = "计算周期", "标准差倍数"
        elif stype == "RSI极值反转策略":
            with col_p1:
                lower_range = st.slider("抄底线范围", 10, 50, (20, 40), key="a_rsi_lr"); lower_step = st.number_input(
                    "抄底步长", 1, 10, 2, key="a_rsi_ls")
            with col_p2:
                upper_range = st.slider("逃顶线范围", 50, 95, (60, 85), key="a_rsi_ur"); upper_step = st.number_input(
                    "逃顶步长", 1, 10, 2, key="a_rsi_us")
            p1_param, p2_param = (lower_range[0], lower_range[1], lower_step), (upper_range[0], upper_range[1], upper_step)
            la, lb = "抄底阈值", "逃顶阈值"
        elif stype == "MACD趋势策略":
            with col_p1:
                fast_range = st.slider("快线范围", 5, 40, (10, 20), key="a_macd_fr"); fast_step = st.number_input(
                    "快线步长", 1, 10, 2, key="a_macd_fs")
            with col_p2:
                slow_range = st.slider("慢线范围", 15, 100, (20, 40), key="a_macd_sr"); slow_step = st.number_input(
                    "慢线步长", 1, 20, 2, key="a_macd_ss")
            p1_param, p2_param = (fast_range[0], fast_range[1], fast_step), (slow_range[0], slow_range[1], slow_step)
            la, lb = "快线周期", "慢线周期"
        elif stype == "KDJ震荡策略":
            with col_p1:
                buy_range = st.slider("抄底线范围", -20, 30, (-10, 10), key="a_kdj_br"); buy_step = st.number_input(
                    "抄底步长", 1, 10, 5, key="a_kdj_bs")
            with col_p2:
                sell_range = st.slider("逃顶线范围", 70, 120, (90, 110), key="a_kdj_sr"); sell_step = st.number_input(
                    "逃顶步长", 1, 10, 5, key="a_kdj_ss")
            p1_param, p2_param = (buy_range[0], buy_range[1], buy_step), (sell_range[0], sell_range[1], sell_step)
            la, lb = "超卖买入线", "超买卖出线"
        else:
            st.error(f"❌ 未知的策略类型：{strategy_type}")
            return

        # 计算总数
        if strategy_type == "布林带突破策略":
            total_comb = len(range(p1_param[0], p1_param[1] + 1, p1_param[2])) * len(
                np.arange(p2_param[0], p2_param[1] + 0.01, p2_param[2]))
        else:
            total_comb = len(range(p1_param[0], p1_param[1] + 1, p1_param[2])) * len(
                range(p2_param[0], p2_param[1] + 1, p2_param[2]))

    st.divider()
    st.subheader("🔬 稳定性体检：样本外盲测 (OOS)")
    enable_oos = st.toggle("🛡️ 开启多参数盲测排行榜 (检验前 10 名真实性)", value=False, key="a_oos_toggle")
    if enable_oos:
        train_ratio = st.slider("训练集占比", 0.5, 0.9, 0.7, 0.05, key="a_oos_ratio")

    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        pos_ratio = st.number_input("寻优单次仓位", 0.1, 1.0, 1.0, 0.1, key="a_pos")
    with c2:
        st.markdown(
            f"<div style='margin-top: 32px;'>📊 预计计算：<strong style='color:red;'>{int(total_comb)}</strong> 个组合</div>",
            unsafe_allow_html=True)
    with c3:
        st.write("");
        run_opt = st.button("🔥 开启暴力扫描", use_container_width=True, type="primary", key="a_run")

    if run_opt:
        raw_data = get_daily_hfq_data(symbol, start_date, end_date)
        if raw_data is None or raw_data.empty:
            st.error("❌ 无法获取数据，请检查股票代码或网络")
            return

        # 划分数据集
        if enable_oos:
            split_idx = int(len(raw_data) * train_ratio)
            train_raw = raw_data.iloc[:split_idx]
            test_raw = raw_data.iloc[split_idx:]
            st.warning(
                f"🪓 数据已切分！【训练集】至 {train_raw.index[-1].strftime('%Y-%m-%d')} | 【测试集】从 {test_raw.index[0].strftime('%Y-%m-%d')} 至今")
        else:
            train_raw = raw_data
            split_idx = 0
        with st.spinner('建立多进程计算池...'):
            # 💡 增加前端进度条实例与回调函数
            progress_bar = st.progress(0, text="🚀 正在多进程扫描参数空间...")

            def update_progress(p):
                progress_bar.progress(p, text=f"扫描进度: {int(p * 100)}%")

            results_df, param1_name, param2_name = optimize_strategy(
                train_raw, strategy_type, initial_capital, global_filters, pos_ratio,
                p1_param, p2_param, start_date, end_date,
                progress_callback=update_progress  # 👈 注入回调
            )

            progress_bar.empty()  # 计算完成后清空进度条
            # 🚨 核心逻辑：寻优时使用全局定义的止盈止损
            results_df, param1_name, param2_name = optimize_strategy(
                train_raw, strategy_type, initial_capital, global_filters, pos_ratio,
                p1_param, p2_param, start_date, end_date
            )

            # 🛡️ 检查结果有效性
            if results_df is None or results_df.empty:
                st.error("❌ 参数寻优失败，所有参数组合都无法产生有效结果")
                st.info("💡 可能原因：\n- 数据质量有问题（如停牌、数据不足）\n- 策略参数组合导致计算错误\n- 高级过滤器过滤了所有信号")
                return

            if '收益率 (%)' not in results_df.columns:
                st.error(f"❌ 结果数据格式异常，缺少列：收益率 (%)")
                st.info(f"当前列：{list(results_df.columns)}")
                return

            # 绘制热力图
            max_abs = results_df['收益率 (%)'].abs().max() or 1
            plot_df = results_df.pivot(index=lb, columns=la, values='收益率 (%)')
            fig = go.Figure(
                data=go.Heatmap(z=plot_df.values, x=plot_df.columns, y=plot_df.index, colorscale='RdYlGn_r',
                                zmin=-max_abs, zmax=max_abs))
            fig.update_layout(title="训练集参数收益分布 (红区代表参数平原，越宽越稳)", xaxis_title=la,
                              yaxis_title=lb)
            st.plotly_chart(fig, use_container_width=True)

            if enable_oos:
                st.subheader("📋 前 10 名参数 OOS 盲测排行榜")
                top_10 = results_df.sort_values('夏普比率', ascending=False).head(10).copy()

                oos_results = []
                for idx, row in top_10.iterrows():
                    # 对前 10 名每一组参数进行盲测
                    bt_test = run_single_param_backtest(raw_data, strategy_type, row[la], row[lb], global_filters,
                                                        initial_capital, pos_ratio)

                    # 仅切出测试集部分的收益
                    test_part = bt_test.iloc[split_idx:]
                    if test_part.empty or len(test_part) < 2:
                        test_ret = 0
                        test_sharpe = 0
                    else:
                        test_ret = ((test_part['strategy_equity'].iloc[-1] / test_part['strategy_equity'].iloc[0]) - 1) * 100
                        test_sharpe = test_part.attrs.get('sharpe_ratio', 0)

                    oos_results.append({
                        la: row[la], lb: row[lb],
                        "训练收益 (%)": row['收益率 (%)'],
                        "盲测收益 (%)": round(test_ret, 2),
                        "盲测夏普": round(test_sharpe, 2),
                        "状态": "✅ 通过" if test_ret > 0 else "❌ 崩盘"
                    })

                oos_df = pd.DataFrame(oos_results)
                st.dataframe(oos_df.style.map(
                    lambda x: 'color: red' if x == '✅ 通过' else 'color: green' if x == '❌ 崩盘' else '',
                    subset=['状态']), use_container_width=True)
            else:
                st.subheader("📋 全局寻优排行榜")
                st.dataframe(results_df.sort_values('收益率 (%)', ascending=False), use_container_width=True)
