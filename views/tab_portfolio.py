import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from utils.data_fetcher import get_daily_hfq_data
from backtest.optimizer import apply_advanced_filters
from backtest.engine import run_portfolio_backtest

# 🚀 仅保留注册表导入，删除所有具体策略模块的硬编码导入
from strategies.base import StrategyRegistry
from configs.settings import get_backtest_config

bt_conf = get_backtest_config()


def render_portfolio_tab(display_list, start_date, end_date, initial_capital, global_filters, strategy_type):
    def calculate_performance_metrics(df, initial_cap):
        if df.empty: return {}
        total_ret = (df['total_value'].iloc[-1] / initial_cap) - 1
        ann_ret = (1 + total_ret) ** (bt_conf.TRADING_DAYS_PER_YEAR / len(df)) - 1
        df['cum_max'] = df['total_value'].cummax()
        df['drawdown'] = (df['total_value'] - df['cum_max']) / df['cum_max']
        max_dd = df['drawdown'].min()
        calmar = ann_ret / abs(max_dd) if max_dd != 0 else 0
        return {"total_ret": total_ret, "ann_ret": ann_ret, "max_dd": max_dd, "calmar": calmar}

    def local_plot_combined_chart(df):
        from plotly.subplots import make_subplots
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1,
                            subplot_titles=("组合净值雪球曲线", "动态回撤分布 (%)"), row_heights=[0.7, 0.3])
        fig.add_trace(go.Scatter(x=df.index, y=df['total_value'], name='总资产', line=dict(color='#FFD700', width=3)),
                      row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['drawdown'] * 100, name='回撤', fill='tozeroy',
                                 line=dict(color='rgba(255, 0, 0, 0.4)')), row=2, col=1)
        fig.update_layout(height=500, template='plotly_white', showlegend=False)
        return fig

    st.markdown(f"### 🧺 {strategy_type} - 多股轮动实战实验室")

    # 🚀 动态获取策略类
    strategy = StrategyRegistry.get(strategy_type)
    if not strategy:
        st.error("策略未注册！")
        return

    with st.expander("🎯 账户与动态仓位配置", expanded=True):
        c_l, c_m, c_r = st.columns([2, 1, 1])
        with c_l: selected_pool = st.multiselect("选取轮动池", display_list, default=display_list[:5], key="p_pool")
        with c_m: max_pos = st.slider("最大持仓槽位", 1, 10, 5, key="p_max_pos")
        with c_r: is_dynamic = st.toggle("开启动态复利", value=True)

    if st.button("🚀 启动全量轮动回测", type="primary", use_container_width=True):
        if not selected_pool:
            st.warning("请选择股票！")
            return

        all_data_for_bt = {}
        prog = st.progress(0)
        status = st.empty()

        # 🚀 提取策略默认参数，作为组合回测的基础参数
        param_dict = {k: v.default for k, v in strategy.params.items()}

        for i, disp in enumerate(selected_pool):
            sym = disp.split('(')[-1].replace(')', '').strip()
            status.text(f"正在准备信号: {sym}...")
            raw = get_daily_hfq_data(sym, start_date, end_date)
            if raw is None or raw.empty: continue

            # 🚀 彻底解耦：统一使用动态接口调用
            df = strategy.generate_signals(raw, **param_dict)
            df = apply_advanced_filters(df, None, global_filters)

            df['final_signal'] = np.where(df['filter_pass'], df['signal'], 0)
            if 'position_diff' not in df.columns:
                df['position_diff'] = df['final_signal'].diff().fillna(0)

            all_data_for_bt[sym] = df
            prog.progress((i + 1) / len(selected_pool))

        if all_data_for_bt:
            # 🚀 将全局设置一次性传入组合回测引擎
            res_df, details_df, log_df = run_portfolio_backtest(
                all_data_for_bt, initial_capital, max_pos, global_filters, dynamic_sizing=is_dynamic
            )
            st.session_state['p_res'] = res_df
            st.session_state['p_details'] = details_df
            st.session_state['p_log'] = log_df
            st.rerun()

    # --- 📊 结果展示区保持原样 ---
    if 'p_res' in st.session_state:
        res = st.session_state['p_res']
        metrics = calculate_performance_metrics(res, initial_capital)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("累计收益率", f"{metrics['total_ret'] * 100:.2f}%")
        c2.metric("年化收益率", f"{metrics['ann_ret'] * 100:.2f}%")
        c3.metric("最大回撤", f"{metrics['max_dd'] * 100:.2f}%")
        c4.metric("卡玛比率", f"{metrics['calmar']:.2f}")

        st.plotly_chart(local_plot_combined_chart(res), use_container_width=True)

        st.divider()
        st.subheader("🕵️ 账户穿梭复盘 (联动饼图与明细表)")
        all_dates = res.index.strftime('%Y-%m-%d').tolist()
        pick_date_str = st.select_slider("拖动滑块复盘任意一天的资产分布：", options=all_dates, value=all_dates[-1])
        pick_date = pd.to_datetime(pick_date_str)

        day_holdings = st.session_state['p_details'][st.session_state['p_details']['date'] == pick_date]
        day_summary = res.loc[pick_date]

        col_pie, col_tab = st.columns([2, 2])
        with col_pie:
            pie_df = pd.concat(
                [day_holdings[['股票', '价值']], pd.DataFrame([{'股票': '闲置现金', '价值': day_summary['cash']}])])
            fig = px.pie(pie_df, values='价值', names='股票', hole=0.4, title=f"📅 {pick_date_str} 资产构成")
            st.plotly_chart(fig, use_container_width=True)

        with col_tab:
            st.write(f"📈 **当日账户快照**")
            st.metric("总资产 (Equity)", f"¥ {day_summary['total_value']:,.2f}")
            if not day_holdings.empty:
                st.dataframe(day_holdings[['股票', '股数', '价值', '占比']], use_container_width=True, hide_index=True)
            else:
                st.info("该交易日账户为空仓状态（现金 100%）。")

        with st.expander("📜 查看完整历史交易流水"):
            st.dataframe(st.session_state['p_log'].sort_values('日期', ascending=False), use_container_width=True)