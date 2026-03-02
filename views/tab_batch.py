import streamlit as st
import pandas as pd
import numpy as np
from utils.data_fetcher import get_daily_hfq_data
from backtest.optimizer import optimize_strategy


def render_batch_tab(display_list, start_date, end_date, initial_capital, global_filters, strategy_type):
    st.markdown(f"### 📡 {strategy_type} - 暴力寻优雷达")

    # 顶部核心说明
    st.info(
        "💡 **批量诊断提示**：本功能将对下方选定的多只股票执行**并行扫描**。不仅找出它们各自的最优参数，还会基于该参数的夏普比率、盈亏比等指标，给出机构级的**资金分配诊断建议**。")

    selected_stocks = st.multiselect("🗃️ 监控标的池 (支持拼音/代码/汉字搜索)", display_list,
                                     default=display_list[:3] if display_list else [], key="b_pool")

    # 双列宽阔排版
    with st.expander("🎯 寻优精度与步长设置", expanded=True):
        col_p1, col_p2 = st.columns(2)
        p1_param = p2_param = None  # 初始化变量
        la = lb = ""  # 初始化参数名称

        if strategy_type == "双均线动能策略":
            with col_p1:
                s_range = st.slider("短期范围", 2, 40, (5, 15), key="b_ma_sr")
                s_step = st.number_input("👉 短期步长", 1, 10, 2, key="b_ma_ss")
            with col_p2:
                l_range = st.slider("长期范围", 20, 150, (30, 90), key="b_ma_lr")
                l_step = st.number_input("👉 长期步长", 1, 20, 5, key="b_ma_ls")
            p1_param, p2_param = (s_range[0], s_range[1], s_step), (l_range[0], l_range[1], l_step)

        elif strategy_type == "布林带突破策略":
            with col_p1:
                w_range = st.slider("周期范围", 10, 100, (15, 30), key="b_boll_wr")
                w_step = st.number_input("👉 周期步长", 1, 10, 5, key="b_boll_ws")
            with col_p2:
                std_range = st.slider("标准差范围", 1.0, 3.5, (1.5, 2.5), key="b_boll_sr")
                std_step = st.number_input("👉 标准差步长", 0.1, 1.0, 0.1, key="b_boll_ss")
            p1_param, p2_param = (w_range[0], w_range[1], w_step), (std_range[0], std_range[1], std_step)

        elif strategy_type == "RSI极值反转策略":
            with col_p1:
                lower_range = st.slider("抄底线范围", 10, 50, (20, 40), key="b_rsi_lr")
                lower_step = st.number_input("👉 抄底线步长", 1, 10, 5, key="b_rsi_ls")
            with col_p2:
                upper_range = st.slider("逃顶线范围", 50, 95, (60, 85), key="b_rsi_ur")
                upper_step = st.number_input("👉 逃顶线步长", 1, 10, 5, key="b_rsi_us")
            p1_param, p2_param = (lower_range[0], lower_range[1], lower_step), (upper_range[0], upper_range[1], upper_step)

        elif strategy_type == "MACD趋势策略":
            with col_p1:
                fast_range = st.slider("快线范围", 5, 40, (10, 20), key="b_macd_fr")
                fast_step = st.number_input("👉 快线步长", 1, 10, 2, key="b_macd_fs")
            with col_p2:
                slow_range = st.slider("慢线范围", 15, 100, (20, 40), key="b_macd_sr")
                slow_step = st.number_input("👉 慢线步长", 1, 20, 2, key="b_macd_ss")
            p1_param, p2_param = (fast_range[0], fast_range[1], fast_step), (slow_range[0], slow_range[1], slow_step)

        elif strategy_type == "KDJ震荡策略":
            with col_p1:
                buy_range = st.slider("抄底线范围", -20, 30, (-10, 10), key="b_kdj_br")
                buy_step = st.number_input("👉 抄底步长", 1, 10, 5, key="b_kdj_bs")
            with col_p2:
                sell_range = st.slider("逃顶线范围", 70, 120, (90, 110), key="b_kdj_sr")
                sell_step = st.number_input("👉 逃顶步长", 1, 10, 5, key="b_kdj_ss")
            p1_param, p2_param = (buy_range[0], buy_range[1], buy_step), (sell_range[0], sell_range[1], sell_step)
        else:
            st.error(f"❌ 未知的策略类型：{strategy_type}")
            return

    c1, c2 = st.columns([1, 1])
    with c1:
        pos_ratio = st.number_input("单次扫描测试仓位", 0.1, 1.0, 0.8, key="b_pos")
    with c2:
        st.write("")
        run_opt = st.button("📡 启动全量寻优扫描", use_container_width=True, type="primary", key="b_run")

    if run_opt:
        if not selected_stocks:
            st.warning("请至少在【监控标的池】中选择一只股票！")
            return

        all_res = []
        prog = st.progress(0)

        for i, disp in enumerate(selected_stocks):
            sym = disp.split('(')[-1].replace(')', '').strip()
            name = disp.split(' (')[0]

            raw = get_daily_hfq_data(sym, start_date, end_date)
            if raw is not None and not raw.empty:
                res_df, la, lb = optimize_strategy(raw, strategy_type, initial_capital, global_filters, pos_ratio,
                                                   p1_param, p2_param, start_date, end_date)

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
            st.error("❌ 未发掘任何有效交易信号，可能过滤条件过于严苛。")


def generate_advice(best):
    """基于机构视角的深度智能诊断算法"""
    sharpe = best['夏普比率']
    plr = best['盈亏比']
    dd = abs(best['最大回撤 (%)'])
    wr = best['胜率 (%)']

    if sharpe > 1.2 and plr > 1.5 and wr > 45:
        return "🌟 绝佳主力", f"收益风险比极佳 (夏普 {sharpe:.2f})。盈利空间对亏损风险形成压倒性优势，建议作为核心仓位跟踪。"
    elif sharpe > 0.8 and plr > 1.0:
        return "✅ 稳健防守", f"表现良好且抗击打能力强。能稳步实现净值复利累积，适合作为投资组合的底仓防御型配置。"
    elif plr < 1.0 and wr > 55:
        return "⚠️ 赚小亏大", f"胜率虽有 {wr:.1f}%，但盈亏比严重失衡。极易出现“赚几次不够亏一次”的情况，实盘必须严设止损。"
    elif dd > 25:
        return "🌋 波动剧烈", f"历史最大回撤深达 {dd:.1f}%，该参数组合极容易遭遇极端杀跌。不建议盲目重仓介入。"
    else:
        return "☕ 建议观望", f"核心动能不足，极易受震荡杂波干扰 (夏普 {sharpe:.2f})。资金周转效率低下，建议放弃或等待右侧信号。"