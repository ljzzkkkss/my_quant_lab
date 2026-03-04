import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from strategies.advanced_filter import apply_advanced_filters
from backtest.engine import run_portfolio_backtest
from utils.data_context import DataContext
from strategies.base import StrategyRegistry
from configs.settings import get_backtest_config
from utils.ui_helpers import ui_button_lock

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

    strategy = StrategyRegistry.get(strategy_type)
    if not strategy:
        st.error("策略未注册！")
        return

    # 🚀 新增 1：开放自定义策略参数
    with st.container(border=True):
        st.subheader("⚙️ 策略底层参数 (自定义)")
        param_values = {}
        num_params = {k: v for k, v in strategy.params.items() if not isinstance(v.default, bool)}
        bool_params = {k: v for k, v in strategy.params.items() if isinstance(v.default, bool)}

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
                        key=f"p_{strategy_type}_{p_name}"
                    )

        if bool_params:
            st.write("")
            bool_cols = st.columns(len(bool_params))
            for i, (p_name, p_def) in enumerate(bool_params.items()):
                with bool_cols[i]:
                    param_values[p_name] = st.toggle(
                        f"🛠️ {p_def.description or p_name}", value=p_def.default,
                        key=f"p_{strategy_type}_{p_name}"
                    )

    # 🚀 新增 2：增加资金分配模型选项
    with st.expander("🎯 账户与资金分配模型", expanded=True):
        c_l, c_m, c_r, c_4 = st.columns([2, 1, 1.5, 1])
        with c_l: selected_pool = st.multiselect("选取轮动池", display_list, default=display_list[:5], key="p_pool")
        with c_m: max_pos = st.slider("最大持仓数", 1, 10, 5, key="p_max_pos")
        with c_r: alloc_method = st.selectbox("资金分配模型", ["等权资金模型", "ATR 风险平价模型"], key="p_alloc")
        with c_4:
            st.write("")
            is_dynamic = st.toggle("开启动态复利", value=True)
    btn_ph = st.empty()
    run_port = btn_ph.button("🚀 启动全量轮动回测", type="primary", use_container_width=True, key="p_run")
    if run_port:
        with ui_button_lock(btn_ph, "⏳ 全局资金分配演算中...", "🚀 启动全量轮动回测", "p_run"):
            if not selected_pool:
                st.warning("请选择股票！")
                st.stop()  # 优雅停止，上下文会自动恢复按钮
            all_data_for_bt = {}
            prog = st.progress(0)
            status = st.empty()

            # 🚀 核武器：构建全局数据中心，一波全拉到内存！
            ctx = DataContext()
            ctx.preload(selected_pool, start_date, end_date, global_filters.get('use_index'),
                        use_sector=global_filters.get('use_sector', False),
                        sector_code=global_filters.get('sector_code', ''),
                        use_macro=global_filters.get('use_macro', False),
                        macro_code=global_filters.get('macro_code', ''),
                        use_geo=global_filters.get('use_geo', False), geo_code=global_filters.get('geo_code', ''))

            for i, disp in enumerate(selected_pool):
                sym = disp.split('(')[-1].replace(')', '').strip()
                status.text(f"正在准备信号: {sym}...")

                # 🚀 0毫秒延迟直接从内存抽取
                raw = ctx.get_stock(sym)
                if raw is None or raw.empty: continue

                df = strategy.generate_signals(raw, **param_values)
                # 传入内存大盘数据
                global_filters['index_df'] = ctx.index_data
                global_filters['sector_df'] = ctx.sector_data
                global_filters['macro_df'] = ctx.macro_data
                global_filters['geo_df'] = ctx.geo_data

                df = apply_advanced_filters(df, ctx.index_data, global_filters)

                df['final_signal'] = np.where(df['filter_pass'], df['signal'], 0)
                if 'position_diff' not in df.columns:
                    df['position_diff'] = df['final_signal'].diff().fillna(0)

                all_data_for_bt[sym] = df
                prog.progress((i + 1) / len(selected_pool))

            if not all_data_for_bt:
                st.error("⚠️ 所选股票均无可用数据或全部停牌，请检查网络或更换标的池！")
                st.stop()

            res_df, details_df, log_df = run_portfolio_backtest(
                all_data_for_bt, initial_capital, max_pos, global_filters,
                dynamic_sizing=is_dynamic, allocation_method=alloc_method
            )
            st.session_state['p_res'] = res_df
            st.session_state['p_details'] = details_df
            st.session_state['p_log'] = log_df
            st.rerun()

    # --- 📊 结果展示区 ---
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

        day_holdings = st.session_state['p_details'][
            st.session_state['p_details']['date'].astype(str).str.slice(0, 10) == pick_date_str[:10]
            ]
        day_summary = res.loc[pd.to_datetime(pick_date_str)]

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