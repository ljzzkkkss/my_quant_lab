import streamlit as st
import pandas as pd
import numpy as np
from utils.data_fetcher import get_daily_hfq_data
from backtest.optimizer import optimize_strategy
from strategies.base import StrategyRegistry


def render_batch_tab(display_list, start_date, end_date, initial_capital, global_filters, strategy_type):
    st.markdown(f"### 📡 {strategy_type} - 暴力寻优雷达")

    strategy = StrategyRegistry.get(strategy_type)
    if not strategy:
        st.error("策略未注册！")
        return

    st.info(
        "💡 **批量诊断提示**：本功能将对下方选定的多只股票执行**并行扫描**。基于最优参数下的夏普比率、盈亏比给出机构级的**资金分配诊断建议**。")

    selected_stocks = st.multiselect("🗃️ 监控标的池", display_list, default=display_list[:3] if display_list else [],
                                     key="b_pool")

    with st.expander("🎯 寻优精度与步长设置", expanded=True):
        opt_params = {k: v for k, v in strategy.params.items() if not isinstance(v.default, bool)}
        bool_params = {k: v for k, v in strategy.params.items() if isinstance(v.default, bool)}

        opt_keys = list(opt_params.keys())[:2]
        if len(opt_keys) < 2:
            st.warning("该策略参数不足，无法雷达扫描。")
            return

        col_p1, col_p2 = st.columns(2)
        grid_values = []

        for i, key in enumerate(opt_keys):
            p_def = opt_params[key]
            with (col_p1 if i == 0 else col_p2):
                desc = p_def.description or key
                def_min = p_def.min_val if p_def.min_val is not None else int(p_def.default * 0.5)
                def_max = p_def.max_val if p_def.max_val is not None else int(p_def.default * 2.0)

                if isinstance(p_def.default, float):
                    p_range = st.slider(f"{desc} 范围", float(def_min), float(def_max),
                                        (float(p_def.default * 0.8), float(p_def.default * 1.2)), key=f"b_r_{key}")
                    p_step = st.number_input(f"👉 {desc} 步长", 0.01, 1.0, float(p_def.step), key=f"b_s_{key}")
                    grid_values.append(list(np.arange(p_range[0], p_range[1] + p_step * 0.1, p_step)))
                else:
                    p_range = st.slider(f"{desc} 范围", int(def_min), int(def_max),
                                        (int(p_def.default * 0.8), int(p_def.default * 1.2)), key=f"b_r_{key}")
                    p_step = st.number_input(f"👉 {desc} 步长", 1, max(10, int((def_max - def_min) / 5)),
                                             int(p_def.step), key=f"b_s_{key}")
                    grid_values.append(list(range(p_range[0], p_range[1] + 1, p_step)))

        # 🚀 同理渲染静态开关
        if bool_params:
            st.divider()
            st.write("🛠️ **静态策略开关** (应用到全部标的测试)")
            bool_cols = st.columns(len(bool_params))
            for i, (p_name, p_def) in enumerate(bool_params.items()):
                with bool_cols[i]:
                    val = st.toggle(p_def.description or p_name, value=p_def.default, key=f"b_{strategy_type}_{p_name}")
                    opt_keys.append(p_name)
                    grid_values.append([val])

    c1, c2 = st.columns([1, 1])
    with c1:
        pos_ratio = st.number_input("单次扫描测试仓位", 0.1, 1.0, 0.8, key="b_pos")
    with c2:
        st.write(""); run_opt = st.button("📡 启动全量寻优扫描", use_container_width=True, type="primary", key="b_run")

    if run_opt:
        if not selected_stocks:
            st.warning("请选择股票！")
            return

        all_res = []
        prog = st.progress(0)

        for i, disp in enumerate(selected_stocks):
            sym = disp.split('(')[-1].replace(')', '').strip()
            name = disp.split(' (')[0]
            raw = get_daily_hfq_data(sym, start_date, end_date)

            if raw is not None and not raw.empty:
                res_df, la, lb = optimize_strategy(
                    raw, strategy_type, initial_capital, global_filters, pos_ratio,
                    opt_keys, grid_values, start_date, end_date
                )

                if res_df is not None and not res_df.empty:
                    best = res_df.sort_values('夏普比率', ascending=False).iloc[0]
                    analysis_title, advice_desc = generate_advice(best)

                    all_res.append({
                        "名称": name,
                        "最优参数": f"{best[la]} / {best[lb]}",
                        "预期收益": best['收益率 (%)'],
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