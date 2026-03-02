import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import plotly.express as px
from utils.data_fetcher import get_daily_hfq_data
from backtest.optimizer import optimize_strategy, apply_advanced_filters
from backtest.engine import run_backtest, plot_equity_curve
from strategies.base import StrategyRegistry
from configs.settings import get_backtest_config

bt_conf = get_backtest_config()


def run_single_param_backtest(raw_data, strategy_type, param_dict, global_filters, initial_capital, pos_ratio):
    strategy = StrategyRegistry.get(strategy_type)
    strat_df = strategy.generate_signals(raw_data, **param_dict)

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

    return run_backtest(strat_df, initial_capital, pos_ratio, global_filters)


def render_auto_tab(symbol, start_date, end_date, initial_capital, global_filters, strategy_type):
    st.markdown(f"### 🤖 {strategy_type} - 全维参数空间寻优")

    strategy = StrategyRegistry.get(strategy_type)
    if not strategy: return

    opt_keys = []
    grid_values = []
    dynamic_dims = []  # 记录哪些参数是动态扫描的（用于画图）

    with st.expander("🎯 寻优搜索空间与参数调校指南", expanded=True):
        st.info(
            "💡 **全维扫描说明**：勾选下方 `[参与多维寻优]` 的参数将构建网格进行全景扫描。寻优维度越多，计算呈指数级增长。未勾选的将作为静态常量。")

        for key, p_def in strategy.params.items():
            desc = p_def.description or key

            # 渲染布尔型（只能作为静态常量）
            if isinstance(p_def.default, bool):
                val = st.toggle(f"🛠️ {desc}", value=p_def.default, key=f"a_{key}")
                if p_def.impact: st.caption(f"💡 *影响：{p_def.impact}*")
                opt_keys.append(key)
                grid_values.append([val])
                continue

            # 渲染数值型
            with st.container(border=True):
                c1, c2, c3 = st.columns([1.5, 1, 1.5])
                with c1:
                    st.markdown(f"**{desc}**")
                    if hasattr(p_def, 'impact') and p_def.impact:
                        st.caption(f"💡 *{p_def.impact}*")
                with c2:
                    # 默认让前两个参数参与寻优
                    is_opt = st.checkbox("参与多维寻优扫描", value=(len(dynamic_dims) < 2), key=f"chk_{key}")
                with c3:
                    if is_opt:
                        dynamic_dims.append(desc)
                        def_min = p_def.min_val if p_def.min_val is not None else int(p_def.default * 0.5)
                        def_max = p_def.max_val if p_def.max_val is not None else int(p_def.default * 2.0)
                        if isinstance(p_def.default, float):
                            p_range = st.slider(f"范围", float(def_min), float(def_max),
                                                (float(p_def.default * 0.8), float(p_def.default * 1.2)),
                                                key=f"r_{key}", label_visibility="collapsed")
                            p_step = st.number_input(f"步长", 0.01, 1.0, float(p_def.step), key=f"s_{key}",
                                                     label_visibility="collapsed")
                            grid_values.append(list(np.arange(p_range[0], p_range[1] + p_step * 0.1, p_step)))
                        else:
                            p_range = st.slider(f"范围", int(def_min), int(def_max),
                                                (int(p_def.default * 0.8), int(p_def.default * 1.2)), key=f"r_{key}",
                                                label_visibility="collapsed")
                            p_step = st.number_input(f"步长", 1, max(10, int((def_max - def_min) / 5)), int(p_def.step),
                                                     key=f"s_{key}", label_visibility="collapsed")
                            grid_values.append(list(range(p_range[0], p_range[1] + 1, p_step)))
                    else:
                        val = st.number_input(f"静态值", value=p_def.default, key=f"v_{key}",
                                              label_visibility="collapsed")
                        grid_values.append([val])
                opt_keys.append(key)

        total_comb = np.prod([len(g) for g in grid_values])

    st.divider()
    st.subheader("🔬 稳定性体检：样本外盲测 (OOS)")
    enable_oos = st.toggle("🛡️ 开启多参数盲测排行榜", value=False, key="a_oos_toggle")
    if enable_oos: train_ratio = st.slider("训练集占比", 0.5, 0.9, 0.7, 0.05, key="a_oos_ratio")

    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        pos_ratio = st.number_input("寻优单次仓位", 0.1, 1.0, 1.0, 0.1, key="a_pos")
    with c2:
        st.markdown(
            f"<div style='margin-top: 32px;'>📊 预计扫描：<strong style='color:red;'>{total_comb}</strong> 个网格点</div>",
            unsafe_allow_html=True)
    with c3:
        st.write(""); run_opt = st.button("🔥 开启暴力扫描", use_container_width=True, type="primary", key="a_run")

    if run_opt:
        raw_data = get_daily_hfq_data(symbol, start_date, end_date)
        if raw_data is None or raw_data.empty: return st.error("❌ 无法获取数据")

        train_raw = raw_data.iloc[:int(len(raw_data) * train_ratio)] if enable_oos else raw_data
        split_idx = len(train_raw) if enable_oos else 0

        with st.spinner('建立多进程计算池...'):
            progress_bar = st.progress(0, text="🚀 正在多进程扫描参数空间...")
            results_df, desc_map = optimize_strategy(
                train_raw, strategy_type, initial_capital, global_filters, pos_ratio,
                opt_keys, grid_values, start_date, end_date,
                progress_callback=lambda p: progress_bar.progress(p, text=f"扫描进度: {int(p * 100)}%")
            )
            progress_bar.empty()

            if results_df is None or results_df.empty or '收益率 (%)' not in results_df.columns:
                return st.error("❌ 参数寻优失败，可能未产生有效交易")

            st.markdown("### 🗺️ 全维参数雷达地形图")
            # 🚀 根据寻优维度的数量，智能渲染图表类型！
            valid_dims = [d for d in dynamic_dims if d in results_df.columns]

            if len(valid_dims) == 1:
                # 1维：折线图
                fig = px.line(results_df, x=valid_dims[0], y='收益率 (%)', title="单参数收益率曲线", markers=True)
                st.plotly_chart(fig, use_container_width=True)
            elif len(valid_dims) == 2:
                # 2维：热力图
                plot_df = results_df.pivot(index=valid_dims[1], columns=valid_dims[0], values='收益率 (%)')
                max_abs = results_df['收益率 (%)'].abs().max() or 1
                fig = go.Figure(
                    data=go.Heatmap(z=plot_df.values, x=plot_df.columns, y=plot_df.index, colorscale='RdYlGn_r',
                                    zmin=-max_abs, zmax=max_abs))
                fig.update_layout(title="二维参数收益分布 (红区代表参数平原)", xaxis_title=valid_dims[0],
                                  yaxis_title=valid_dims[1])
                st.plotly_chart(fig, use_container_width=True)
            elif len(valid_dims) >= 3:
                # N维：平行坐标图 (高级数据科学家专用)
                st.info(
                    "💡 **图表指南**：您选择了 >=3 个维度。下图为**平行坐标图**。每一条线代表一种参数组合，最右侧红色的线为高收益组合。")
                fig = px.parallel_coordinates(
                    results_df,
                    dimensions=valid_dims + ['收益率 (%)', '夏普比率'],
                    color='收益率 (%)',
                    color_continuous_scale=px.colors.diverging.RdYlGn[::-1]
                )
                st.plotly_chart(fig, use_container_width=True)

            if enable_oos:
                st.subheader("📋 前 10 名参数 OOS 盲测排行榜")
                top_10 = results_df.sort_values('夏普比率', ascending=False).head(10).copy()
                oos_results = []
                for _, row in top_10.iterrows():
                    # 反向解析回原始参数 Key
                    param_dict = {k: row[desc_map[k]] for k in opt_keys}
                    bt_test = run_single_param_backtest(raw_data, strategy_type, param_dict, global_filters,
                                                        initial_capital, pos_ratio)

                    test_part = bt_test.iloc[split_idx:]
                    test_ret = ((test_part['strategy_equity'].iloc[-1] / test_part['strategy_equity'].iloc[
                        0]) - 1) * 100 if len(test_part) > 1 else 0
                    test_sharpe = test_part.attrs.get('sharpe_ratio', 0) if len(test_part) > 1 else 0

                    res_dict = {desc_map[k]: row[desc_map[k]] for k in valid_dims}
                    res_dict.update({"训练收益(%)": row['收益率 (%)'], "盲测收益(%)": round(test_ret, 2),
                                     "盲测夏普": round(test_sharpe, 2), "状态": "✅ 通过" if test_ret > 0 else "❌ 崩盘"})
                    oos_results.append(res_dict)

                st.dataframe(pd.DataFrame(oos_results).style.map(
                    lambda x: 'color: red' if x == '✅ 通过' else 'color: green' if x == '❌ 崩盘' else '',
                    subset=['状态']), use_container_width=True)
            else:
                st.subheader("📋 全局寻优排行榜")
                st.dataframe(results_df.sort_values('收益率 (%)', ascending=False), use_container_width=True)