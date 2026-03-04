import streamlit as st
import numpy as np
from utils.data_fetcher import get_daily_hfq_data
from backtest.engine import run_backtest, plot_equity_curve
from strategies.advanced_filter import apply_advanced_filters
from components.charts import plot_interactive_kline
from configs.settings import get_backtest_config
from strategies.base import StrategyRegistry
from utils.market_analyzer import MarketAnalyzer
from utils.ui_helpers import ui_button_lock

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
            btn_ph = st.empty() #创建占位符空按钮
            run_btn = btn_ph.button("🚀 执行完整回测", use_container_width=True, type="primary", key="m_run")

    if run_btn:
        # 🚀 一行代码搞定锁定与恢复！
        with ui_button_lock(btn_ph, "⏳ 引擎高速运转中...", "🚀 执行完整回测", "m_run"):
            with st.spinner('回测计算与盘口诊断中...'):
                raw_data = get_daily_hfq_data(symbol, start_date, end_date)
                diagnostic = MarketAnalyzer.generate_diagnostic_report(raw_data)

                if diagnostic:
                    st.divider()
                    st.subheader(f"🩺 {symbol} 实盘深度体检报告")

                    # 渲染体检仪表盘
                    c_score, c_vp, c_sr = st.columns(3)

                    with c_score:
                        score = diagnostic['trend_score']
                        color = "red" if score > 0 else "green" if score < 0 else "gray"
                        st.metric("中期趋势共振得分", f"{score} 分", delta="多头控盘" if score > 0 else "空头压制",
                                  delta_color="normal" if score > 0 else "inverse")

                    with c_vp:
                        st.markdown(
                            f"**资金动能检测**：<br><span style='color:{diagnostic['vp_color']}; font-weight:bold; font-size:18px;'>{diagnostic['vp_status']}</span>",
                            unsafe_allow_html=True)
                        st.caption(diagnostic['vp_desc'])

                    with c_sr:
                        st.markdown("**近期关键攻防点位**：")
                        st.markdown(f"🧱 强力阻力位: **{diagnostic['resistance']:.2f}**")
                        st.markdown(f"垫 核心支撑位: **{diagnostic['support']:.2f}**")

                        # 计算盈亏比空间
                        if diagnostic['resistance'] > diagnostic['current_price'] and diagnostic['current_price'] > \
                                diagnostic['support']:
                            up_space = (diagnostic['resistance'] / diagnostic['current_price']) - 1
                            down_space = 1 - (diagnostic['support'] / diagnostic['current_price'])
                            st.caption(
                                f"当前盈亏空间比: **{up_space / down_space:.1f}** (向上{up_space * 100:.1f}% / 向下{down_space * 100:.1f}%)")
                    st.markdown("#### 📡 异动形态雷达 (近期捕捉)")
                    if diagnostic['patterns']:
                        p_cols = st.columns(len(diagnostic['patterns']))
                        for idx, pat in enumerate(diagnostic['patterns']):
                            with p_cols[idx]:
                                bg_color = "#ffe6e6" if pat['color'] == 'red' else "#e6ffe6"
                                text_color = "#cc0000" if pat['color'] == 'red' else "#006600"
                                st.markdown(
                                    f"""
                                                    <div style='background-color: {bg_color}; padding: 12px; border-radius: 8px; border-left: 5px solid {text_color};'>
                                                        <h5 style='color: {text_color}; margin-top: 0;'>{pat['name']}</h5>
                                                        <span style='font-size: 0.9em; color: #333;'>{pat['desc']}</span>
                                                    </div>
                                                    """, unsafe_allow_html=True
                                )
                    else:
                        # 💡 兜底提示：如果平淡无奇，就告诉你一切正常，证明雷达没坏！
                        st.info("🍵 当前未检测到极端的 K 线异动或均线变盘形态，盘面运行较为平稳。")
                if raw_data is not None and not raw_data.empty:
                    # 调用底层接口，直接传入组装好的参数字典
                    strat_df = strategy.generate_signals(raw_data, **param_values)

                    index_data = get_daily_hfq_data(bt_conf.BENCHMARK_CODE, start_date, end_date) if global_filters['use_index'] else None
                    global_filters['index_df'] = index_data
                    # ... 提取板块数据 ...
                    sector_data = get_daily_hfq_data(global_filters['sector_code'], start_date,
                                                     end_date) if global_filters.get(
                        'use_sector') and global_filters.get('sector_code') else None
                    global_filters['sector_df'] = sector_data

                    # 🚀 提取并注入宏观探针数据
                    macro_data = get_daily_hfq_data(global_filters['macro_code'], start_date,
                                                    end_date) if global_filters.get('use_macro') and global_filters.get(
                        'macro_code') else None
                    global_filters['macro_df'] = macro_data

                    # 🚀 提取并注入地缘探针数据
                    geo_data = get_daily_hfq_data(global_filters['geo_code'], start_date,
                                                  end_date) if global_filters.get('use_geo') and global_filters.get(
                        'geo_code') else None
                    global_filters['geo_df'] = geo_data

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
                        # 🚀 提取极端恶劣的形态
                        fatal_patterns = [p for p in diagnostic['patterns'] if
                                          p.get('type') in ['fatal_sell', 'warning_sell']] if diagnostic else []
                        strong_buy_patterns = [p for p in diagnostic['patterns'] if
                                               p.get('type') == 'strong_buy'] if diagnostic else []

                        # 逻辑 1：策略要求买入
                        if last_day['position_diff'] == 1:
                            if fatal_patterns:
                                # 🛑 雷达一票否决！
                                st.error(
                                    f"### 🛑 指令：【取消买入！强行阻断】\n**依据**：虽然策略发出开仓信号，但形态雷达捕捉到 **{fatal_patterns[0]['name']}**！当前盘口极其恶劣，切勿盲目入场，建议放弃本次信号！")
                            else:
                                st.success(
                                    f"### 🏹 指令：【开盘买入】\n**依据**：{last_date_str} 策略发出开仓信号。建议明天集合竞价或开盘阶段按计划仓位买入。")
                                if strong_buy_patterns:
                                    st.info(
                                        f"🔥 **附加利好**：雷达同时捕捉到 **{strong_buy_patterns[0]['name']}**，本次突破胜率极高，可考虑适当放大仓位！")

                        # 逻辑 2：策略要求卖出
                        elif last_day['position_diff'] == -1:
                            st.error(
                                f"### 🏳️ 指令：【开盘平仓】\n**依据**：{last_date_str} 触发 {last_day.get('sell_reason', '平仓')}。请务必清仓。")

                        # 逻辑 3：策略要求持股
                        elif last_day['final_signal'] == 1:
                            unrealized_pct = (last_day['收盘'] - last_day.get('buy_price',
                                                                              last_day['收盘'])) / last_day.get('buy_price',
                                                                                                                1)
                            if fatal_patterns:
                                st.warning(
                                    f"### ⚠️ 指令：【考虑提前减仓】\n**依据**：虽然策略仍看多，但雷达捕捉到 **{fatal_patterns[0]['name']}**，盘面抛压加剧！当前浮盈：{unrealized_pct * 100:.2f}%，建议立刻锁定部分利润！")
                            else:
                                st.info(
                                    f"### 💎 指令：【继续持股】\n**依据**：策略信号稳定，无恶劣异动。当前参考浮动盈亏：{unrealized_pct * 100:.2f}%。")

                        # 逻辑 4：空仓观望
                        else:
                            st.write(f"### ☕ 指令：【空仓观望】\n**依据**：{last_date_str} 暂无买入信号。等待机会。")

                    with c_status:
                        st.metric("最新收盘价", f"¥{last_day['收盘']:.2f}")
                        st.metric("核心信号状态", "看多 (Long)" if last_day['final_signal'] == 1 else "看空 (Flat)")

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
                else:
                    st.error("❌ 无法获取数据，请检查网络或股票代码")
                    st.stop()