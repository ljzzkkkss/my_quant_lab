import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
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
                                    raw_data.index[-1].strftime('%Y%m%d')) if global_filters.get('use_index') else None
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
    dynamic_dims = []

    with st.expander("🎯 寻优搜索空间与参数调校", expanded=True):
        for key, p_def in strategy.params.items():
            desc = p_def.description or key
            if isinstance(p_def.default, bool):
                val = st.toggle(f"🛠️ {desc}", value=p_def.default, key=f"a_{key}")
                if hasattr(p_def, 'impact') and p_def.impact:
                    st.caption(f"💡 *影响：{p_def.impact}*")
                opt_keys.append(key)
                grid_values.append([val])
                continue

            with st.container(border=True):
                c1, c2, c3 = st.columns([1.5, 1, 1.5])
                with c1:
                    st.markdown(f"**{desc}**")
                    if hasattr(p_def, 'impact') and p_def.impact:
                        st.caption(f"💡 *{p_def.impact}*")
                with c2:
                    is_opt = st.checkbox("参与多维寻优", value=(len(dynamic_dims) < 2), key=f"chk_{key}")
                with c3:
                    if is_opt:
                        dynamic_dims.append(desc)
                        def_min = p_def.min_val if p_def.min_val is not None else int(p_def.default * 0.5)
                        def_max = p_def.max_val if p_def.max_val is not None else int(p_def.default * 2.0)
                        if isinstance(p_def.default, float):
                            p_range = st.slider("范围", float(def_min), float(def_max),
                                                (float(p_def.default * 0.8), float(p_def.default * 1.2)),
                                                key=f"r_{key}", label_visibility="collapsed")
                            p_step = st.number_input("步长", 0.01, 1.0, float(p_def.step), key=f"s_{key}",
                                                     label_visibility="collapsed")
                            grid_values.append(list(np.arange(p_range[0], p_range[1] + p_step * 0.1, p_step)))
                        else:
                            p_range = st.slider("范围", int(def_min), int(def_max),
                                                (int(p_def.default * 0.8), int(p_def.default * 1.2)), key=f"r_{key}",
                                                label_visibility="collapsed")
                            p_step = st.number_input("步长", 1, max(10, int((def_max - def_min) / 5)), int(p_def.step),
                                                     key=f"s_{key}", label_visibility="collapsed")
                            grid_values.append(list(range(p_range[0], p_range[1] + 1, p_step)))
                    else:
                        val = st.number_input("静态值", value=p_def.default, key=f"v_{key}",
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
                return st.error("❌ 参数寻优失败，未产生有效交易")

            valid_dims = [d for d in dynamic_dims if d in results_df.columns]

            # =============== 常驻图表 1：综合能力雷达图 ===============
            st.markdown("### 🏆 Top 5 组合六边形能力对决 (常驻雷达图)")
            top5 = results_df.sort_values('夏普比率', ascending=False).head(5)
            categories = ['年化收益', '夏普比率', '胜率', '盈亏比', '抗回撤(反向)']

            max_ret, min_ret = results_df['收益率 (%)'].max() or 1, results_df['收益率 (%)'].min()
            max_shp, min_shp = results_df['夏普比率'].max() or 1, results_df['夏普比率'].min()
            max_win, min_win = results_df['胜率 (%)'].max() or 1, results_df['胜率 (%)'].min()
            max_pl, min_pl = results_df['盈亏比'].max() or 1, results_df['盈亏比'].min()
            max_dd, min_dd = results_df['最大回撤 (%)'].abs().max() or 1, results_df['最大回撤 (%)'].abs().min()

            def scale(val, vmin, vmax, reverse=False):
                if pd.isna(val) or vmax == vmin: return 100 if vmax == vmin else 0
                res = (val - vmin) / (vmax - vmin) * 100
                return 100 - res if reverse else res

            fig_radar = go.Figure()
            for rank, (idx, row) in enumerate(top5.iterrows()):
                param_str = "<br>".join([f"{d}: {row[d]}" for d in valid_dims]) if valid_dims else "静态参数"
                actual_vals = [f"{row['收益率 (%)']:.2f}%", f"{row['夏普比率']:.2f}", f"{row['胜率 (%)']:.2f}%",
                               f"{row['盈亏比']:.2f}", f"回撤 {abs(row['最大回撤 (%)']):.2f}%"]
                r_vals = [
                    scale(row['收益率 (%)'], min_ret, max_ret), scale(row['夏普比率'], min_shp, max_shp),
                    scale(row['胜率 (%)'], min_win, max_win), scale(row['盈亏比'], min_pl, max_pl),
                    scale(abs(row['最大回撤 (%)']), min_dd, max_dd, reverse=True)
                ]
                fig_radar.add_trace(go.Scatterpolar(
                    r=r_vals + [r_vals[0]], theta=categories + [categories[0]], name=f"Top {rank + 1}",
                    text=actual_vals + [actual_vals[0]], hoverinfo="text+name",
                    hovertemplate=f"<b>⭐ 组合 Top {rank + 1}</b><br>{param_str}<br><br>维度: %{{theta}}<br>真实表现: %{{text}}<br>评分: %{{r:.1f}}分<extra></extra>",
                    mode='lines+markers'
                ))
            fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100], showticklabels=False)),
                                    title="排名前 5 参数综合实战能力分布", template='plotly_white')
            st.plotly_chart(fig_radar, use_container_width=True)

            # =============== 图表 2：参数地形动态分布图 ===============
            st.markdown("### 🗺️ 寻优参数空间全景地形")
            if len(valid_dims) == 1:
                fig = px.line(results_df, x=valid_dims[0], y='收益率 (%)', title="单参数收益率曲线", markers=True)
                st.plotly_chart(fig, use_container_width=True)
            elif len(valid_dims) == 2:
                plot_df = results_df.pivot(index=valid_dims[1], columns=valid_dims[0], values='收益率 (%)')
                max_abs = results_df['收益率 (%)'].abs().max() or 1
                fig = go.Figure(data=go.Heatmap(
                    z=plot_df.values, x=plot_df.columns, y=plot_df.index, colorscale='RdYlGn_r', zmin=-max_abs,
                    zmax=max_abs,
                    text=np.round(plot_df.values, 2), texttemplate="%{text}%", hoverinfo="x+y+text"
                ))
                fig.update_layout(title="二维参数收益分布 (红区代表参数平原)", xaxis_title=valid_dims[0],
                                  yaxis_title=valid_dims[1])
                st.plotly_chart(fig, use_container_width=True)
            elif len(valid_dims) >= 3:
                st.info("💡 **平行坐标图**：多维参数的上帝视角。每条线代表一种组合，跟踪最右侧红色的线追踪最佳参数。")
                fig = px.parallel_coordinates(results_df, dimensions=valid_dims + ['收益率 (%)', '夏普比率'],
                                              color='收益率 (%)',
                                              color_continuous_scale=px.colors.diverging.RdYlGn[::-1])
                st.plotly_chart(fig, use_container_width=True)

            # =============== OOS 盲测与曲线绘制 ===============
            if enable_oos:
                st.divider()
                st.subheader("🔬 样本外盲测 (OOS) 深度防过拟合检验")
                st.info(
                    "💡 **机构级评判标准**：盲测必须跑赢同期大盘(超额Alpha)，且夏普比率衰减不能过大。如果盲测夏普暴跌，说明该参数严重【过拟合】。")

                top_10 = results_df.sort_values('夏普比率', ascending=False).head(10).copy()
                oos_results = []
                best_oos_bt_df = None
                best_oos_score = -999

                # 🚀 辅助函数：精准计算独立切片区间的真实指标，彻底解决 attrs 继承作弊问题
                def calc_slice_metrics(df_slice):
                    if len(df_slice) < 2: return 0, 0, 0
                    ret = ((df_slice['strategy_equity'].iloc[-1] / df_slice['strategy_equity'].iloc[0]) - 1) * 100
                    bench_ret = ((df_slice['benchmark_equity'].iloc[-1] / df_slice['benchmark_equity'].iloc[
                        0]) - 1) * 100

                    daily_ret = df_slice['strategy_equity'].pct_change().fillna(0)
                    daily_rf = bt_conf.RISK_FREE_RATE / bt_conf.TRADING_DAYS_PER_YEAR
                    excess_ret = daily_ret - daily_rf
                    std_ret = daily_ret.std()
                    sharpe = float(
                        (excess_ret.mean() / std_ret) * np.sqrt(bt_conf.TRADING_DAYS_PER_YEAR)) if std_ret > 0 else 0
                    return ret, bench_ret, sharpe

                for _, row in top_10.iterrows():
                    param_dict = {}
                    for k in opt_keys:
                        col_name = desc_map.get(k, k)
                        val = row.get(col_name)
                        # 底层策略已加 int() 保护，这里正常传值即可
                        param_dict[k] = val if pd.notna(val) else strategy.params[k].default

                    bt_test = run_single_param_backtest(raw_data, strategy_type, param_dict, global_filters,
                                                        initial_capital, pos_ratio)

                    train_part = bt_test.iloc[:split_idx]
                    test_part = bt_test.iloc[split_idx:]

                    # 重新计算训练集与测试集的真实指标
                    train_ret, train_bench, train_sharpe = calc_slice_metrics(train_part)
                    test_ret, test_bench, test_sharpe = calc_slice_metrics(test_part)

                    # 🚀 计算性能衰减率 (降幅越小越稳)
                    if train_sharpe > 0:
                        degradation = (test_sharpe / train_sharpe) * 100
                    else:
                        degradation = 0

                    # 🚀 严苛的评级标准
                    if test_ret > test_bench and test_sharpe > 0.5:
                        status = "🌟 圣杯(超额收益)"
                        score = test_sharpe * 2 + (test_ret - test_bench)  # 综合评分
                    elif test_ret > 0:
                        status = "⚠️ 正收益(未跑赢大盘)"
                        score = test_sharpe
                    else:
                        status = "❌ 亏损崩盘"
                        score = -1

                    res_dict = {desc_map.get(k, k): row.get(desc_map.get(k, k)) for k in
                                valid_dims} if valid_dims else {}
                    res_dict.update({
                        "训练夏普": round(train_sharpe, 2),
                        "盲测夏普": round(test_sharpe, 2),
                        "夏普留存率": f"{degradation:.1f}%",  # 新增展示指标
                        "盲测收益": f"{test_ret:.2f}%",
                        "基准收益": f"{test_bench:.2f}%",
                        "评级": status
                    })
                    oos_results.append(res_dict)

                    # 记录盲测阶段综合得分最高的选手
                    if score > best_oos_score:
                        best_oos_score = score
                        best_oos_bt_df = bt_test

                # 渲染表格，加上热力色
                st.dataframe(
                    pd.DataFrame(oos_results).style.map(
                        lambda x: 'color: #ff4b4b; font-weight: bold' if '圣杯' in str(x)
                        else 'color: orange' if '⚠️' in str(x)
                        else 'color: green' if '❌' in str(x) else '', subset=['评级']
                    ).map(
                        lambda x: 'color: red' if float(str(x).replace('%', '')) > 70 else 'color: green',
                        subset=['夏普留存率']
                    ),
                    use_container_width=True
                )

                if best_oos_bt_df is not None:
                    st.markdown("#### 🥇 OOS 最强盲测组合 - 全周期净值表现")
                    split_date = raw_data.index[split_idx]
                    fig_oos = plot_equity_curve(best_oos_bt_df,
                                                title=f"最佳组合表现 (紫虚线左侧为训练集，右侧为 OOS 盲测阶段)")
                    fig_oos.add_vline(x=split_date, line_width=2, line_dash="dash", line_color="purple")
                    fig_oos.add_annotation(x=split_date, y=best_oos_bt_df['strategy_equity'].iloc[split_idx],
                                           text="开启样本外盲测", showarrow=True, arrowhead=1)
                    st.plotly_chart(fig_oos, use_container_width=True)
            else:
                st.subheader("📋 全局寻优排行榜")
                st.dataframe(results_df.sort_values('收益率 (%)', ascending=False), use_container_width=True)