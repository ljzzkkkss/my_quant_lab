import streamlit as st
import pandas as pd
import numpy as np
from utils.data_fetcher import get_daily_hfq_data
from backtest.optimizer import optimize_strategy
from strategies.base import StrategyRegistry
from utils.data_context import DataContext
from utils.ui_helpers import ui_button_lock


def render_batch_tab(display_list, start_date, end_date, initial_capital, global_filters, strategy_type):
    st.markdown(f"### 📡 {strategy_type} - 雷达全景批量寻优")

    strategy = StrategyRegistry.get(strategy_type)
    if not strategy: return

    st.info(
        "💡 **批量诊断提示**：本功能将对下方选定的多只股票执行**并行扫描**。基于最优参数下的夏普比率、盈亏比给出机构级的**资金分配诊断建议**。")

    selected_stocks = st.multiselect("🗃️ 监控标的池", display_list, default=display_list[:3] if display_list else [],
                                     key="b_pool")

    opt_keys = []
    grid_values = []
    dynamic_dims = []

    with st.expander("🎯 全维寻优搜索空间与参数设置", expanded=True):
        st.write("勾选 `[参与多维寻优]` 将对该股票池构建对应维度的网格扫描，未勾选的作为静态常量。")

        for key, p_def in strategy.params.items():
            desc = p_def.description or key

            if isinstance(p_def.default, bool):
                val = st.toggle(f"🛠️ {desc}", value=p_def.default, key=f"b_{key}")
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
                    is_opt = st.checkbox("参与多维寻优", value=(len(dynamic_dims) < 2), key=f"b_chk_{key}")
                with c3:
                    if is_opt:
                        dynamic_dims.append(desc)
                        def_min = p_def.min_val if p_def.min_val is not None else int(p_def.default * 0.5)
                        def_max = p_def.max_val if p_def.max_val is not None else int(p_def.default * 2.0)
                        if isinstance(p_def.default, float):
                            p_range = st.slider(f"范围", float(def_min), float(def_max),
                                                (float(p_def.default * 0.8), float(p_def.default * 1.2)),
                                                key=f"b_r_{key}", label_visibility="collapsed")
                            p_step = st.number_input(f"步长", 0.01, 1.0, float(p_def.step), key=f"b_s_{key}",
                                                     label_visibility="collapsed")
                            grid_values.append(list(np.arange(p_range[0], p_range[1] + p_step * 0.1, p_step)))
                        else:
                            p_range = st.slider(f"范围", int(def_min), int(def_max),
                                                (int(p_def.default * 0.8), int(p_def.default * 1.2)), key=f"b_r_{key}",
                                                label_visibility="collapsed")
                            p_step = st.number_input(f"步长", 1, max(10, int((def_max - def_min) / 5)), int(p_def.step),
                                                     key=f"b_s_{key}", label_visibility="collapsed")
                            grid_values.append(list(range(p_range[0], p_range[1] + 1, p_step)))
                    else:
                        val = st.number_input(f"静态值", value=p_def.default, key=f"b_v_{key}",
                                              label_visibility="collapsed")
                        grid_values.append([val])
                opt_keys.append(key)

        total_comb = np.prod([len(g) for g in grid_values])

    c1, c2 = st.columns([1, 1])
    with c1:
        pos_ratio = st.number_input("单次扫描测试仓位", 0.1, 1.0, 0.8, key="b_pos")
    with c2:
        st.markdown(
            f"<div style='margin-top: 32px;'>预计单票扫描：<strong style='color:red;'>{total_comb}</strong> 个组合</div>",
            unsafe_allow_html=True)

    btn_ph = st.empty()
    run_opt = btn_ph.button("📡 启动全量寻优扫描", use_container_width=True, type="primary", key="b_run")

    if run_opt:
        with ui_button_lock(btn_ph, "⏳ 雷达全域扫描中...", "📡 启动全量寻优扫描", "b_run"):
            if not selected_stocks:
                st.warning("请选择股票！")
                st.stop()

            all_res = []
            prog = st.progress(0)

            # 🚀 核武器：构建全局数据中心
            ctx = DataContext()
            ctx.preload(selected_stocks, start_date, end_date, global_filters.get('use_index'))

            for i, disp in enumerate(selected_stocks):
                sym = disp.split('(')[-1].replace(')', '').strip()
                name = disp.split(' (')[0]

                # 🚀 0毫秒延迟取数据
                raw = ctx.get_stock(sym)
                if raw is not None and not raw.empty:
                    res_df, desc_map = optimize_strategy(
                        raw, strategy_type, initial_capital, global_filters, pos_ratio,
                        opt_keys, grid_values, start_date, end_date,
                        preloaded_index=ctx.index_data  # 🚀 直接把内存大盘数据穿透传给引擎
                    )

                    if res_df is not None and not res_df.empty:
                        best = res_df.sort_values('夏普比率', ascending=False).iloc[0]
                        analysis_title, advice_desc = generate_advice(best)

                        # 🚀 智能拼接所有的最优动态参数维度
                        valid_dims = [d for d in dynamic_dims if d in res_df.columns]
                        if valid_dims:
                            best_params_str = " | ".join([f"{d}: {best[d]}" for d in valid_dims])
                        else:
                            best_params_str = "全部使用静态参数"

                        all_res.append({
                            "名称": name,
                            "🏆 最优参数": best_params_str,
                            "预期收益": best['收益率 (%)'],
                            "夏普比率": best['夏普比率'],
                            "胜率": f"{best['胜率 (%)']:.1f}%",
                            "盈亏比": round(best['盈亏比'], 2),
                            "最大回撤": best['最大回撤 (%)'],
                            "诊断结论": analysis_title,
                            "深度建议": advice_desc
                        })
                prog.progress((i + 1) / len(selected_stocks))
            prog.empty()

            if all_res:
                st.success("✅ 雷达全量扫描完成！")
                report_df = pd.DataFrame(all_res)
                st.dataframe(
                    report_df.style.map(lambda x: 'color: #ff4b4b; font-weight: bold' if isinstance(x, (int,
                                                                                                        float)) and x > 0 else 'color: #00b050' if isinstance(
                        x, (int, float)) and x < 0 else '', subset=['预期收益'])
                    .map(lambda x: 'background-color: #fff2f2; color: #cc0000; font-weight: bold' if "剧烈" in str(
                        x) or "赚小" in str(x) else '', subset=['诊断结论']),
                    use_container_width=True
                )
            else:
                st.error("❌ 未发掘任何有效交易信号")


def generate_advice(best):
    sharpe, plr, dd, wr = best['夏普比率'], best['盈亏比'], abs(best['最大回撤 (%)']), best['胜率 (%)']
    if sharpe > 1.2 and plr > 1.5 and wr > 45:
        return "🌟 绝佳主力", f"收益风险比极佳 (夏普 {sharpe:.2f})。盈利空间对亏损风险形成压倒性优势。"
    elif sharpe > 0.8 and plr > 1.0:
        return "✅ 稳健防守", f"表现良好且抗击打能力强。能稳步实现净值复利累积。"
    elif plr < 1.0 and wr > 55:
        return "⚠️ 赚小亏大", f"极易出现“赚几次不够亏一次”的情况，实盘必须严设止损。"
    elif dd > 25:
        return "🌋 波动剧烈", f"历史最大回撤深达 {dd:.1f}%，极容易遭遇极端杀跌。"
    else:
        return "☕ 建议观望", f"核心动能不足，极易受震荡杂波干扰 (夏普 {sharpe:.2f})。"