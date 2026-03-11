import json
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from strategies.advanced_filter import apply_advanced_filters
from backtest.engine import run_portfolio_backtest
from utils.data_context import DataContext
from utils.data_fetcher import get_daily_hfq_data  # 🚀 新增引入，用于循环内动态拉取专属板块
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

    with st.container(border=True):
        st.subheader("⚙️ 策略底层参数 (默认基座)")
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

        # ==========================================
        # 🚀 模块对调：先选定轮动池，再配置千股千策！
        # ==========================================
        with st.expander("🎯 1. 账户与资金分配模型 (先选定股票池)", expanded=True):
            c_l, c_m, c_r, c_4 = st.columns([2, 1, 1.5, 1])
            with c_l: selected_pool = st.multiselect("选取轮动池", display_list, default=display_list[:5], key="p_pool")
            with c_m: max_pos = st.slider("最大持仓数", 1, 10, 5, key="p_max_pos")
            with c_r: alloc_method = st.selectbox("资金分配模型", ["等权资金模型", "ATR 风险平价模型"], key="p_alloc")
            with c_4:
                st.write("")
                is_dynamic = st.toggle("开启动态复利", value=True)

        # 🚀 终极进化：千股千策路由字典 (向导式配置)
        with st.expander("🗺️ 2. 高阶玩法：千股千策 (向导式配置)", expanded=False):
            st.markdown("""
            **何为千股千策？** 为组合内的不同股票配置专属的“策略”、“参数”甚至**“专属共振板块”**。
            *(注：未配置的股票，将默认采用全局策略与全局板块配置)*
            """)
            use_routing = st.toggle("🔌 启用策略路由引擎", value=False, key="p_use_route")

            if 'p_routing_dict' not in st.session_state:
                st.session_state['p_routing_dict'] = {}

            routing_dict = st.session_state['p_routing_dict']

            if use_routing:
                try:
                    strat_list = StrategyRegistry.list_strategies()
                except Exception:
                    strat_list = ["双均线动能策略", "MACD趋势策略"]

                # ---------------- 区域 A：展示已配置的规则 ----------------
                if routing_dict:
                    st.write("📋 **当前已生效的专属路由规则：**")
                    display_data = []
                    for sym, rule in routing_dict.items():
                        strat_obj = StrategyRegistry.get(rule['strategy'])
                        param_desc_list = []
                        if strat_obj:
                            for k, v in rule['params'].items():
                                p_def = strat_obj.params.get(k)
                                desc = p_def.description if p_def else k
                                param_desc_list.append(f"{desc}: {v}")
                        param_str = " | ".join(param_desc_list) if param_desc_list else "默认参数"

                        sec_str = rule.get('sector_code', '')
                        sec_display = sec_str if sec_str else "跟随全局"

                        display_data.append(
                            {"标的代码": sym, "专属策略": rule['strategy'], "专属板块": sec_display,
                             "参数配置": param_str})

                    st.dataframe(pd.DataFrame(display_data), use_container_width=True, hide_index=True)

                    if st.button("🗑️ 清空所有规则", key="clear_routes"):
                        st.session_state['p_routing_dict'] = {}
                        st.rerun()
                else:
                    st.info("💡 当前未配置任何专属路由，所有股票将使用上方的全局策略与板块。")

                st.divider()

                # ---------------- 区域 B：魔法动态配置表单 ----------------
                st.write("🛠️ **新增 / 修改专属规则**")
                with st.container(border=True):
                    col1, col2 = st.columns(2)
                    with col1:
                        # 🚀 完美联动：这里的下拉框选项，直接变成了你在上面选中的 selected_pool！
                        safe_pool = selected_pool if selected_pool else display_list[:1]
                        selected_disp = st.selectbox("1. 从上方轮动池选取股票", options=safe_pool, index=0,
                                                     key="rt_sym_box")
                        target_sym = selected_disp.split('(')[-1].replace(')', '').strip() if selected_disp else ""

                    existing_rule = routing_dict.get(target_sym) if target_sym else None

                    default_strat = existing_rule['strategy'] if existing_rule else strategy_type
                    try:
                        strat_index = strat_list.index(default_strat)
                    except ValueError:
                        strat_index = 0

                    with col2:
                        target_strat = st.selectbox("2. 为该股指派专属策略", options=strat_list, index=strat_index,
                                                    key="rt_strat")

                    st.write("3. 覆盖全局环境 (可选)：")
                    target_sector = st.text_input("专属板块 ETF 代码 (留空则默认跟随侧边栏全局板块)",
                                                  value=existing_rule.get('sector_code', '') if existing_rule else "",
                                                  key="rt_sector")

                    new_params = {}
                    if target_strat:
                        strat_instance = StrategyRegistry.get(target_strat)
                        if strat_instance and strat_instance.params:
                            st.write(f"4. 调节【{target_strat}】的实战参数：")
                            p_cols = st.columns(min(3, len(strat_instance.params)))
                            col_idx = 0
                            for p_name, p_def in strat_instance.params.items():
                                with p_cols[col_idx % len(p_cols)]:
                                    ui_key = f"rt_{target_sym}_{target_strat}_{p_name}"

                                    if existing_rule and existing_rule['strategy'] == target_strat and p_name in \
                                            existing_rule['params']:
                                        default_val = existing_rule['params'][p_name]
                                    else:
                                        default_val = p_def.default

                                    if isinstance(p_def.default, bool):
                                        new_params[p_name] = st.toggle(f"{p_def.description or p_name}",
                                                                       value=default_val, key=ui_key)
                                    else:
                                        step = p_def.step if p_def.step else 1
                                        min_val = type(p_def.default)(
                                            p_def.min_val) if p_def.min_val is not None else None
                                        max_val = type(p_def.default)(
                                            p_def.max_val) if p_def.max_val is not None else None
                                        new_params[p_name] = st.number_input(
                                            p_def.description or p_name,
                                            min_value=min_val, max_value=max_val, value=default_val, step=step,
                                            key=ui_key
                                        )
                                col_idx += 1
                        else:
                            st.info("ℹ️ 该策略无需调节额外参数。")

                    c_btn1, c_btn2, c_btn3 = st.columns([1, 1, 2])
                    with c_btn1:
                        if st.button("💾 保存/覆盖", type="primary", use_container_width=True):
                            if target_sym:
                                st.session_state['p_routing_dict'][target_sym] = {
                                    "strategy": target_strat,
                                    "sector_code": target_sector.strip(),
                                    "params": new_params
                                }
                                st.rerun()
                            else:
                                st.warning("⚠️ 请输入有效的股票代码！")
                    with c_btn2:
                        if target_sym and target_sym in st.session_state.get('p_routing_dict', {}):
                            if st.button("❌ 移除配置", use_container_width=True):
                                del st.session_state['p_routing_dict'][target_sym]
                                st.rerun()

            routing_dict = st.session_state.get('p_routing_dict', {}) if use_routing else {}
    btn_ph = st.empty()
    run_port = btn_ph.button("🚀 启动全量轮动回测", type="primary", use_container_width=True, key="p_run")

    if run_port:
        with ui_button_lock(btn_ph, "⏳ 全局资金分配与路由演算中...", "🚀 启动全量轮动回测", "p_run"):
            if not selected_pool:
                st.warning("请选择股票！")
                st.stop()
            all_data_for_bt = {}
            prog = st.progress(0)
            status = st.empty()

            ctx = DataContext()
            ctx.preload(selected_pool, start_date, end_date, global_filters.get('use_index'),
                        use_sector=global_filters.get('use_sector', False),
                        sector_code=global_filters.get('sector_code', ''),
                        use_macro=global_filters.get('use_macro', False),
                        macro_code=global_filters.get('macro_code', ''),
                        use_geo=global_filters.get('use_geo', False), geo_code=global_filters.get('geo_code', ''))

            for i, disp in enumerate(selected_pool):
                sym = disp.split('(')[-1].replace(')', '').strip()

                raw = ctx.get_stock(sym)
                if raw is None or raw.empty: continue

                current_strategy = strategy
                current_params = param_values.copy()

                # 🚀 核心架构升级：深拷贝一份全局过滤器环境，用于这只股票的独立覆盖！
                stock_filters = global_filters.copy()
                route_msg = ""

                if use_routing and routing_dict and sym in routing_dict:
                    rule = routing_dict[sym]
                    route_strat_name = rule.get('strategy')
                    if route_strat_name:
                        route_strat = StrategyRegistry.get(route_strat_name)
                        if route_strat:
                            current_strategy = route_strat
                            custom_params = rule.get('params', {})
                            default_p = {k: v.default for k, v in route_strat.params.items()}
                            default_p.update(custom_params)
                            current_params = default_p
                            route_msg += f" ➡️ [专属路由: {route_strat_name}]"

                    # 🚀 覆盖独立板块信息
                    custom_sector = rule.get('sector_code')
                    if custom_sector:
                        stock_filters['sector_code'] = custom_sector
                        stock_filters['use_sector'] = True
                        route_msg += f" | 板块: {custom_sector}"

                status.text(f"正在生成信号: {sym}{route_msg}...")

                df = current_strategy.generate_signals(raw, **current_params)

                # 🚀 为这只股票动态挂载所需的数据环境
                if stock_filters.get('use_sector') and stock_filters.get('sector_code'):
                    # 如果这只股票有自己的专属板块，或者全局配置了板块
                    if stock_filters['sector_code'] == global_filters.get('sector_code'):
                        # 如果和全局板块代码一样，直接用预加载好的内存数据，实现0毫秒延迟
                        stock_filters['sector_df'] = ctx.sector_data
                    else:
                        # 如果是独立专属板块，则动态拉取 (拉取接口自带缓存，速度极快)
                        stock_filters['sector_df'] = get_daily_hfq_data(stock_filters['sector_code'], start_date,
                                                                        end_date)
                else:
                    stock_filters['sector_df'] = None

                stock_filters['index_df'] = ctx.index_data
                stock_filters['macro_df'] = ctx.macro_data
                stock_filters['geo_df'] = ctx.geo_data

                # 将独立过滤环境传给高级过滤器引擎
                df = apply_advanced_filters(df, stock_filters)

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