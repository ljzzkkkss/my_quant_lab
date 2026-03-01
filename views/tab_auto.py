import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from utils.data_fetcher import get_daily_hfq_data
from backtest.optimizer import optimize_strategy


def render_auto_tab(symbol, start_date, end_date, initial_capital, use_macd, strategy_type):
    st.markdown(f"### 🤖 {strategy_type} - 智能参数寻优")

    # --- 1. 动态参数范围设置区 ---
    with st.expander("🎯 自定义寻优搜索空间", expanded=True):
        col_p1, col_p2, col_step = st.columns(3)

        if strategy_type == "双均线动能策略":
            with col_p1:
                s_range = st.slider("短期均线搜索范围", 2, 60, (5, 15))
            with col_p2:
                l_range = st.slider("长期均线搜索范围", 10, 250, (20, 60))
            with col_step:
                step = st.number_input("均线变动步长", 1, 20, 2)

            p1_param = (s_range[0], s_range[1], step)
            p2_param = (l_range[0], l_range[1], step)
            total_comb = len(range(p1_param[0], p1_param[1] + 1, step)) * len(range(p2_param[0], p2_param[1] + 1, step))

        else:  # 布林带突破策略
            with col_p1:
                w_range = st.slider("布林带周期范围", 5, 120, (10, 30))
                # 【核心修改】：增加周期步长自定义输入
                w_step = st.number_input("周期变动步长", 1, 20, 5)
            with col_p2:
                std_range = st.slider("标准差倍数范围", 1.0, 3.5, (1.5, 2.5))
            with col_step:
                std_step = st.number_input("标准差变动步长", 0.1, 1.0, 0.1, 0.1)

            # 【核心修改】：应用用户输入的 w_step
            p1_param = (w_range[0], w_range[1], w_step)
            p2_param = (std_range[0], std_range[1], std_step)

            total_comb = len(range(p1_param[0], p1_param[1] + 1, w_step)) * len(
                np.arange(p2_param[0], p2_param[1] + 0.01, std_step))

    # --- 2. 核心操作区 ---
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        pos_ratio = st.number_input("寻优测试仓位", 0.1, 1.0, 1.0, 0.1, key="opt_pos")
    with c2:
        st.write(f"📊 预计回测次数: **{int(total_comb)}** 次")
        run_opt = st.button("🔥 开启暴力扫描", use_container_width=True, type="primary")

    if run_opt:
        with st.spinner('正在全速计算所有组合...'):
            raw_data = get_daily_hfq_data(symbol, start_date, end_date)
            if raw_data is not None and not raw_data.empty:
                results_df, la, lb = optimize_strategy(
                    raw_data, strategy_type, initial_capital,
                    use_macd, pos_ratio, p1_param, p2_param
                )

                if results_df is not None and not results_df.empty:
                    # --- 3. 结果展示 ---
                    best_row = results_df.sort_values('夏普比率', ascending=False).iloc[0]
                    st.success(f"🏆 寻优完成！最佳参数组合：{la}={best_row[la]} / {lb}={best_row[lb]}")

                    # --- 视觉升级：正红负绿，绝对值越大颜色越深 ---
                    max_abs_val = results_df['收益率(%)'].abs().max()
                    if max_abs_val == 0: max_abs_val = 1

                    plot_df = results_df.pivot(index=lb, columns=la, values='收益率(%)')

                    fig = go.Figure(data=go.Heatmap(
                        z=plot_df.values,
                        x=plot_df.columns,
                        y=plot_df.index,
                        colorscale='RdYlGn_r',
                        zmin=-max_abs_val,
                        zmax=max_abs_val,
                        hovertemplate=f'{la}: %{{x}}<br>{lb}: %{{y}}<br>收益率: %{{z}}%<extra></extra>'
                    ))
                    fig.update_layout(title="参数收益热力图 (红涨绿跌)", xaxis_title=la, yaxis_title=lb)
                    st.plotly_chart(fig, use_container_width=True)

                    st.dataframe(results_df.sort_values('收益率(%)', ascending=False), use_container_width=True)