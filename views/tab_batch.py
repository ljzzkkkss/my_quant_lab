import streamlit as st
import pandas as pd
import numpy as np
from utils.data_fetcher import get_daily_hfq_data
from backtest.optimizer import optimize_strategy


def render_batch_tab(display_list, start_date, end_date, initial_capital, use_macd, strategy_type):
    st.markdown(f"### 📡 {strategy_type} - 暴力寻优雷达 (专家模式)")

    # 标的选择
    selected_stocks = st.multiselect("🗃️ 监控标的池", display_list, default=display_list[:2])

    # 1. 步长与范围配置
    with st.expander("🎯 寻优精度与步长设置", expanded=True):
        c1, c2, c3 = st.columns(3)
        if strategy_type == "双均线动能策略":
            with c1:
                s_range = st.slider("短期范围", 2, 40, (5, 15))
                s_step = st.number_input("短期步长", 1, 10, 2)
            with c2:
                l_range = st.slider("长期范围", 20, 150, (30, 90))
                l_step = st.number_input("长期步长", 1, 20, 5)
            p1_param, p2_param = (s_range[0], s_range[1], s_step), (l_range[0], l_range[1], l_step)
        else:
            with c1:
                w_range = st.slider("周期范围", 10, 100, (15, 30))
                w_step = st.number_input("周期步长", 1, 10, 5)
            with c2:
                std_range = st.slider("标准差范围", 1.0, 3.5, (1.5, 2.5))
                std_step = st.number_input("标准差步长", 0.1, 1.0, 0.1)
            p1_param, p2_param = (w_range[0], w_range[1], w_step), (std_range[0], std_range[1], std_step)

        with c3:
            pos_ratio = st.slider("扫描仓位", 0.1, 1.0, 0.8)

    # 2. 执行扫描
    if st.button("📡 启动全量寻优扫描", use_container_width=True, type="primary"):
        if not selected_stocks:
            st.warning("请选择标的")
            return

        all_res = []
        prog = st.progress(0)

        for i, disp in enumerate(selected_stocks):
            sym = disp.split('(')[-1].replace(')', '')
            name = disp.split(' (')[0]

            raw = get_daily_hfq_data(sym, start_date, end_date)
            if raw is not None:
                res_df, la, lb = optimize_strategy(raw, strategy_type, initial_capital, use_macd, pos_ratio, p1_param,
                                                   p2_param)

                if res_df is not None:
                    # 获取夏普最高的一组
                    best = res_df.sort_values('夏普比率', ascending=False).iloc[0]
                    analysis, advice = generate_advice(best)

                    all_res.append({
                        "名称": name,
                        "最优参数": f"{best[la]} / {best[lb]}",
                        "预期收益": best['收益率(%)'],
                        "胜率": f"{best['胜率(%)']:.1f}%",
                        "盈亏比": round(best['盈亏比'], 2),
                        "最大回撤": best['最大回撤(%)'],
                        "智能建议": advice
                    })
            prog.progress((i + 1) / len(selected_stocks))

        # 3. 结果呈现
        if all_res:
            st.success("扫描完成")
            report_df = pd.DataFrame(all_res)
            st.dataframe(
                report_df.style.map(lambda x: 'color: red' if isinstance(x, float) and x > 0 else '',
                                    subset=['预期收益'])
                .map(lambda x: 'background-color: #fdf2f2' if "风险" in str(x) else '', subset=['智能建议']),
                use_container_width=True
            )


def generate_advice(best):
    """根据回测指标生成实战建议"""
    sharpe = best['夏普比率']
    plr = best['盈亏比']
    dd = abs(best['最大回撤(%)'])

    if sharpe > 1.2 and plr > 1.5:
        return "优质标的", "🚀 策略契合度极高，建议作为主力关注。"
    elif plr < 1.0:
        return "盈亏失衡", "⚠️ 虽然可能赚钱，但每赚1块要冒亏1块以上的风险，谨慎。"
    elif dd > 25:
        return "高回撤", "🍵 收益尚可但波动巨大，建议降仓操作。"
    else:
        return "中规中矩", "☕ 表现稳健，适合分仓配置。"