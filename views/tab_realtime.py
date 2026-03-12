import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import akshare as ak
import os
import json
from utils.data_fetcher import get_daily_hfq_data
from strategies.base import StrategyRegistry
from strategies.advanced_filter import apply_advanced_filters
from configs.settings import get_backtest_config
from utils.ui_helpers import ui_button_lock

bt_conf = get_backtest_config()


def render_realtime_tab(display_list, start_date, end_date, initial_capital, global_filters, strategy_type):
    st.markdown("### ⚡ 盘中实时狙击 (Auto-Funnel Sniper)")
    st.markdown("通过全市场快照实施**【漏斗初筛】**，剔除死水股后，对精锐标的进行**【数据缝合】**与主力策略推演。")

    # ==========================================
    # 🌪️ 漏斗配置面板
    # ==========================================
    with st.container(border=True):
        st.markdown("#### 🌪️ 第一层：全市场漏斗初筛条件 (过滤 95% 垃圾股)")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            min_price = st.number_input("最低股价 (元)", 1.0, 50.0, 5.0, step=1.0)
        with c2:
            max_price = st.number_input("最高股价 (元)", 10.0, 500.0, 100.0, step=5.0)
        with c3:
            min_turnover = st.number_input("今日最低成交额 (亿)", 0.1, 100.0, 1.0, step=0.5,
                                           help="过滤掉没有主力资金关注的死水股")
        with c4:
            max_scan = st.number_input("最高送检数量", 10, 200, 30, step=10,
                                       help="按成交额降序，截取最活跃的前 N 只送入引擎进行深度运算（防止拉取数据超时）")

        exclude_st = st.toggle("🚫 强制过滤 ST 股与退市股", value=True)

    with st.container(border=True):
        st.markdown("#### ⚔️ 第二层：主力狙击策略指派")
        all_strategies = StrategyRegistry.list_strategies()
        try:
            default_idx = all_strategies.index(strategy_type)
        except ValueError:
            default_idx = 0
        target_strat_name = st.selectbox("选择用于判定最终买点的策略模型", all_strategies, index=default_idx,
                                         key="runtime_strat")

    btn_ph = st.empty()
    is_running = st.session_state.get('runtime_run_running', False)

    if is_running:
        run_btn = btn_ph.button("⏳ 引擎轰鸣中...", disabled=True, use_container_width=True, key="runtime_run_disabled")
    else:
        run_btn = btn_ph.button("🔥 14:50 立即开启全市场盲狙", type="primary", use_container_width=True, key="runtime_run")

    if run_btn and not is_running:
        with ui_button_lock(btn_ph, "⏳ 引擎轰鸣中...", "🔥 14:50 立即开启全市场盲狙", "runtime_run"):
            strategy = StrategyRegistry.get(target_strat_name)
            default_params = {k: v.default for k, v in strategy.params.items()}

            status_text = st.empty()
            progress_bar = st.progress(0)

            # ==========================================
            # 1. 获取全市场快照 (优先尝试东财，极速降级到新浪)
            # ==========================================
            status_text.text("📡 正在抓取全市场 5000 只股票实时切片...")

            # 清理代理环境
            for k in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'all_proxy']:
                if k in os.environ:
                    del os.environ[k]

            spot_df = None
            try:
                # 只试一次东财，不行立刻换新浪，节约时间
                spot_df = ak.stock_zh_a_spot_em()
            except Exception:
                pass

            if spot_df is None or spot_df.empty:
                status_text.text("🔄 东财线路受阻，已无缝切换至【新浪财经】高优通道...")
                try:
                    spot_df = ak.stock_zh_a_spot()
                    # 统一新浪的列名和代码格式
                    if '代码' in spot_df.columns:
                        spot_df['代码'] = spot_df['代码'].astype(str).str.replace(r'^[a-zA-Z]+', '', regex=True)
                    rename_map = {'开盘': '今开'}
                    spot_df = spot_df.rename(columns={k: v for k, v in rename_map.items() if k in spot_df.columns})
                except Exception as e:
                    st.error(f"❌ 快照拉取彻底失败，请检查网络: {e}")
                    return

            if spot_df is None or spot_df.empty:
                st.error("❌ 未能获取到任何快照数据。")
                return

            # ==========================================
            # 2. 第一层漏斗：向量化极速清洗 (耗时 < 0.1秒)
            # ==========================================
            status_text.text("🌪️ 正在执行第一层漏斗：清洗垃圾股...")

            # 强转数值类型防报错
            spot_df['最新价'] = pd.to_numeric(spot_df['最新价'], errors='coerce')
            spot_df['成交额'] = pd.to_numeric(spot_df['成交额'], errors='coerce')

            # 过滤价格
            mask = (spot_df['最新价'] >= min_price) & (spot_df['最新价'] <= max_price)
            # 过滤成交额 (注意：新浪的成交额单位是元，东财单位也是元，所以 1亿 = 100,000,000)
            mask &= (spot_df['成交额'] >= min_turnover * 100000000)
            # 过滤 ST
            if exclude_st and '名称' in spot_df.columns:
                mask &= (~spot_df['名称'].astype(str).str.contains('ST'))
                mask &= (~spot_df['名称'].astype(str).str.contains('退'))

            filtered_df = spot_df[mask].copy()

            # 按成交额降序排列，截取前 N 只最活跃的票进入第二阶段
            filtered_df = filtered_df.sort_values(by='成交额', ascending=False).head(max_scan)

            if filtered_df.empty:
                st.warning("⚠️ 漏斗初筛后没有任何股票符合条件，请放宽初筛条件！")
                return

            st.toast(f"🌪️ 漏斗初筛完成：从全市场成功锁定 {len(filtered_df)} 只高活跃标的，准备送入策略引擎！")

            # ==========================================
            # 3. 准备防守探针数据
            # ==========================================
            status_text.text("🛡️ 正在拉取宏观与大盘防守数据...")
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

            # ==========================================
            # 4. 第三层漏斗：数据缝合与策略推演
            # ==========================================
            today_str = datetime.now().strftime('%Y-%m-%d')
            buy_signals = []

            # 🚀 终极进化：从硬盘强行读取你配置的千股千策！
            routing_dict = {}
            if os.path.exists("configs/my_routing_dict.json"):
                try:
                    with open("configs/my_routing_dict.json", 'r', encoding='utf-8') as f:
                        routing_dict = json.load(f)
                except Exception as e:
                    st.warning(f"读取千股千策配置失败: {e}")

            # 兜底：如果硬盘没读到，去内存里找找
            if not routing_dict:
                routing_dict = st.session_state.get('p_routing_dict', {})

            total_targets = len(filtered_df)
            for i, (_, row) in enumerate(filtered_df.iterrows()):
                sym = str(row['代码'])
                stock_name = row['名称']
                status_text.text(f"🧵 正在缝合与推演 [{i + 1}/{total_targets}]: {stock_name} ({sym})")

                df = get_daily_hfq_data(sym, start_date, end_date)

                if df is not None and not df.empty:
                    # 缝合今天的实时 K 线
                    if today_str not in df.index:
                        current_price = row.get('最新价', np.nan)
                        open_price = row.get('今开', current_price)
                        high_price = row.get('最高', current_price)
                        low_price = row.get('最低', current_price)
                        volume = row.get('成交量', 0)

                        if pd.notna(current_price):
                            today_bar = pd.DataFrame({
                                '开盘': [open_price], '收盘': [current_price],
                                '最高': [high_price], '最低': [low_price], '成交量': [volume]
                            }, index=[pd.to_datetime(today_str)])
                            df = pd.concat([df, today_bar])

                    # 🚀 核心改造：动态参数注入！
                    if sym in routing_dict:
                        actual_strat_name = routing_dict[sym]['strategy']
                        actual_params = routing_dict[sym]['params']
                        strat_instance = StrategyRegistry.get(actual_strat_name)
                        status_text.text(f"🧠 触发千股千策！正在使用专属参数推演: {stock_name}")
                    else:
                        actual_strat_name = target_strat_name
                        actual_params = default_params
                        strat_instance = strategy

                    # 引擎全速运转 (带着不同的参数)
                    df_signals = strat_instance.generate_signals(df, **actual_params)
                    df_signals = apply_advanced_filters(df_signals, arena_filters)

                    df_signals['final_signal'] = np.where(df_signals['filter_pass'], df_signals['signal'], 0)
                    df_signals['position_diff'] = df_signals['final_signal'].diff().fillna(0)

                    last_row = df_signals.iloc[-1]

                    if last_row['position_diff'] == 1 and last_row['final_signal'] == 1:
                        turnover_yi = row['成交额'] / 100000000 if pd.notna(row['成交额']) else 0
                        buy_signals.append({
                            "股票代码": sym,
                            "股票名称": stock_name,
                            "今日成交额": f"{turnover_yi:.2f} 亿",
                            "实时现价": f"¥ {last_row['收盘']:.2f}",
                            "触发策略": actual_strat_name,  # 显示真实触发的策略名
                            "参数来源": "⚙️ 专属配置" if sym in routing_dict else "📦 默认鲁棒",
                            "推演时间": datetime.now().strftime('%H:%M:%S')
                        })

                progress_bar.progress((i + 1) / total_targets)

            status_text.empty()
            progress_bar.empty()

            # ==========================================
            # 5. 终极战报展示
            # ==========================================
            st.divider()
            st.subheader(f"🎯 盲狙雷达报告 (深度扫描了 {total_targets} 只极度活跃标的)")

            if buy_signals:
                st.success(f"🎉 引擎轰鸣！在盘中成功捕捉到 {len(buy_signals)} 只极其符合买入形态的主力活跃票！")
                # 按照成交额排序展示，最前面的往往流动性最好
                res_df = pd.DataFrame(buy_signals)
                st.dataframe(res_df, use_container_width=True, hide_index=True)
                st.balloons()
            else:
                st.info(
                    "☕ 深度扫描完毕。经过严格的策略与大盘风控过滤，当前高活跃池中暂无触发买点的标的。不乱买就是最好的防守！")