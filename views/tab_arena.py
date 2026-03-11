import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from utils.data_fetcher import get_daily_hfq_data
from backtest.engine import run_backtest
from strategies.advanced_filter import apply_advanced_filters
from strategies.base import StrategyRegistry
from configs.settings import get_backtest_config
from utils.ui_helpers import ui_button_lock

bt_conf = get_backtest_config()


def render_arena_tab(display_list, start_date, end_date, initial_capital, global_filters):
    st.markdown("### 🏟️ 策略角斗场 (Strategy Arena)")
    st.markdown("在这里，让多个策略在同一只股票上进行无情厮杀，用真实的夏普比率和回撤数据，寻找该股票的“天命策略”。")

    # 1. 动态获取系统内所有注册的策略
    try:
        all_strategies = StrategyRegistry.list_strategies()
    except Exception:
        all_strategies = []

    if not all_strategies:
        st.error("❌ 系统中未检测到任何已注册的策略！")
        return

    with st.container(border=True):
        c_sym, c_strat = st.columns([1, 2])  # ⚠️ 这里划分了左右两列，比例 1:2

        with c_sym:  # 👉 左侧较窄的列 (放股票和滑块)
            default_idx = next((i for i, s in enumerate(display_list) if "600522" in s), 0)
            selected_disp = st.selectbox("🎯 参赛标的", options=display_list, index=default_idx, key="arena_sym")
            target_symbol = selected_disp.split('(')[-1].replace(')', '').strip() if selected_disp else ""
            pos_ratio = st.slider("统一买入仓位比例", 0.1, 1.0, 1.0, key="arena_pos")

        with c_strat:  # 👉 右侧较宽的列 (放策略多选框。注意这里的缩进，必须和 with c_sym 对齐！)
            selected_strats = st.multiselect(
                "⚔️ 选择参战策略 (默认全量下场厮杀)",
                options=all_strategies,
                default=all_strategies,
                format_func=lambda name: f"{name} ｜ {StrategyRegistry.get(name).description}",
                key="arena_strats"
            )

    btn_ph = st.empty()
    run_btn = btn_ph.button("🔥 开启角斗", type="primary", use_container_width=True, key="arena_run")

    if run_btn:
        if not target_symbol:
            st.warning("⚠️ 请输入股票代码！")
            return
        if not selected_strats:
            st.warning("⚠️ 请至少选择一个参战策略！")
            return

        with ui_button_lock(btn_ph, "⏳ 引擎并发验算中...", "🔥 开启角斗", "arena_run"):
            with st.spinner(f"正在拉取 {target_symbol} 及全局环境数据..."):
                # 1. 拉取底层数据与全局环境探针
                raw_data = get_daily_hfq_data(target_symbol, start_date, end_date)
                if raw_data is None or raw_data.empty:
                    st.error("❌ 无法获取该股票数据，请检查代码或网络！")
                    return

                # 动态组装环境字典
                arena_filters = global_filters.copy()
                arena_filters['index_df'] = get_daily_hfq_data(bt_conf.BENCHMARK_CODE, start_date,
                                                               end_date) if arena_filters.get('use_index') else None
                arena_filters['sector_df'] = get_daily_hfq_data(arena_filters['sector_code'], start_date,
                                                                end_date) if arena_filters.get(
                    'use_sector') and arena_filters.get('sector_code') else None
                arena_filters['macro_df'] = get_daily_hfq_data(arena_filters['macro_code'], start_date,
                                                               end_date) if arena_filters.get(
                    'use_macro') and arena_filters.get('macro_code') else None
                arena_filters['geo_df'] = get_daily_hfq_data(arena_filters['geo_code'], start_date,
                                                             end_date) if arena_filters.get(
                    'use_geo') and arena_filters.get('geo_code') else None

                arena_results = {}
                metrics_list = []
                benchmark_equity = None

                # 2. 依次让策略下场跑数据
                progress_bar = st.progress(0)
                status_text = st.empty()

                for i, strat_name in enumerate(selected_strats):
                    status_text.text(f"正在测算策略: {strat_name} ...")
                    strategy = StrategyRegistry.get(strat_name)

                    # 提取策略的默认参数
                    default_params = {k: v.default for k, v in strategy.params.items()}

                    # 核心演算引擎
                    df = strategy.generate_signals(raw_data, **default_params)
                    df = apply_advanced_filters(df, arena_filters)
                    df['final_signal'] = np.where(df['filter_pass'], df['signal'], 0)
                    df['position_diff'] = df['final_signal'].diff().fillna(0)

                    bt_res = run_backtest(df, initial_capital, pos_ratio, arena_filters)

                    if bt_res is not None and not bt_res.empty:
                        arena_results[strat_name] = bt_res['strategy_equity']
                        if benchmark_equity is None:
                            benchmark_equity = bt_res['benchmark_equity']

                        # 🚀 手动计算总收益率和年化收益率 (因为 engine.py 的 attrs 里没有)
                        final_equity = bt_res['strategy_equity'].iloc[-1]
                        total_ret = (final_equity / initial_capital) - 1
                        ann_ret = (1 + total_ret) ** (bt_conf.TRADING_DAYS_PER_YEAR / len(bt_res)) - 1 if len(
                            bt_res) > 0 else 0

                        # 组装排行榜数据
                        metrics_list.append({
                            "策略名称": strat_name,
                            "总收益率": f"{total_ret * 100:.2f}%",
                            "年化收益": f"{ann_ret * 100:.2f}%",
                            "夏普比率": round(bt_res.attrs.get('sharpe_ratio', 0), 2),
                            "最大回撤": f"{bt_res.attrs.get('max_drawdown', 0):.2f}%",
                            "胜率": f"{bt_res.attrs.get('win_rate', 0):.1f}%",
                            "交易次数": bt_res.attrs.get('trade_count', 0),
                            "_raw_sharpe": bt_res.attrs.get('sharpe_ratio', 0)  # 用于排序的隐藏列
                        })

                    progress_bar.progress((i + 1) / len(selected_strats))

                status_text.empty()
                progress_bar.empty()

            # ==========================================
            # 🏆 3. 渲染兵器谱排行榜与可视化对比
            # ==========================================
            if metrics_list:
                st.divider()
                st.subheader(f"🏆 {target_symbol} 兵器谱排行榜")

                # 按照夏普比率进行降序排序
                df_metrics = pd.DataFrame(metrics_list).sort_values(by="_raw_sharpe", ascending=False)
                df_metrics = df_metrics.drop(columns=["_raw_sharpe"]).reset_index(drop=True)

                # 寻找天命策略
                best_strat = df_metrics.iloc[0]['策略名称']
                st.success(
                    f"🥇 恭喜！经过算力角逐，**【{best_strat}】** 展现出了最强的综合风控与盈利能力，是该标的当前的“天命策略”！")

                st.dataframe(df_metrics, use_container_width=True)

                st.subheader("📈 策略净值走势群殴图")
                fig = go.Figure()

                # 绘制基准线 (用暗色/虚线)
                if benchmark_equity is not None:
                    fig.add_trace(go.Scatter(x=benchmark_equity.index, y=benchmark_equity,
                                             mode='lines', name='无脑持有 (基准)',
                                             line=dict(color='rgba(128, 128, 128, 0.6)', width=2, dash='dot')))

                # 绘制各个策略的净值线
                colors = ['#FF4B4B', '#00B050', '#1E90FF', '#FFD700', '#FF1493', '#8A2BE2']
                for idx, (s_name, equity_series) in enumerate(arena_results.items()):
                    color = colors[idx % len(colors)]
                    width = 4 if s_name == best_strat else 2
                    fig.add_trace(go.Scatter(x=equity_series.index, y=equity_series,
                                             mode='lines', name=s_name,
                                             line=dict(color=color, width=width)))

                fig.update_layout(
                    height=550, template='plotly_white',
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    hovermode="x unified"
                )
                st.plotly_chart(fig, use_container_width=True)

            else:
                st.error("计算失败或所选策略均未产生有效交易记录。")