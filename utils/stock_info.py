import os
import time
import akshare as ak
import pandas as pd
import streamlit as st

CACHE_FILE = "data/stock_list_cache.csv"
CACHE_TTL = 86400 * 7  # 缓存有效期：7天


@st.cache_data
def get_a_share_list():
    """获取 A 股全市场映射 (修复了列名合并 Bug，绝对稳定版)"""

    if not os.path.exists("data"):
        os.makedirs("data")

    # 1. 读取本地缓存
    if os.path.exists(CACHE_FILE):
        file_age = time.time() - os.path.getmtime(CACHE_FILE)
        if file_age < CACHE_TTL:
            try:
                df_all = pd.read_csv(CACHE_FILE, dtype=str).dropna(subset=['symbol', 'name'])
                if len(df_all) > 1000:
                    return df_all
            except Exception:
                pass

    print("🌐 正在拉取 A 股全市场股票列表... (请保持网络通畅)")

    etf_data = {
        'symbol': ['515220', '512880', '510300', '159915', '512100'],
        'name': ['煤炭ETF', '证券ETF', '沪深300ETF', '创业板ETF', '中证1000ETF']
    }
    df_etf = pd.DataFrame(etf_data)

    df_a = None

    # 尝试数据源 1
    try:
        print("⏳ 尝试数据源 1 (基础列表接口)...")
        df_a = ak.stock_info_a_code_name()
        # 【核心修复】：必须把 'code' 改名成 'symbol'，否则合并时会全部丢失！
        if df_a is not None and not df_a.empty:
            df_a = df_a.rename(columns={'code': 'symbol'})
    except Exception as e1:
        print(f"⚠️ 数据源 1 失败: {e1}")

    # 尝试数据源 2
    if df_a is None or len(df_a) < 1000:
        try:
            print("⏳ 尝试数据源 2 (东方财富实时库)...")
            df_em = ak.stock_zh_a_spot_em()
            if df_em is not None and not df_em.empty:
                df_a = df_em[['代码', '名称']].rename(columns={'代码': 'symbol', '名称': 'name'})
        except Exception as e2:
            print(f"⚠️ 数据源 2 失败: {e2}")

    # 检验成果并落盘
    if df_a is not None and len(df_a) > 1000:
        df_all = pd.concat([df_a, df_etf], ignore_index=True)
        # 此时 symbol 对齐了，dropna 就不会误杀 A 股了
        df_all = df_all.dropna(subset=['symbol', 'name'])
        df_all['display'] = df_all['name'].astype(str) + " (" + df_all['symbol'].astype(str) + ")"

        df_all.to_csv(CACHE_FILE, index=False, encoding='utf-8-sig')
        # 打印出最终存了多少只股票，让你安心
        print(f"✅ 股票列表成功更新，共保存了 {len(df_all)} 只标的至: {CACHE_FILE}")
        return df_all

    print("❌ 所有网络数据源均失效，启动保底方案...")

    # 尝试使用过期的旧文件
    if os.path.exists(CACHE_FILE):
        try:
            df_old = pd.read_csv(CACHE_FILE, dtype=str).dropna(subset=['symbol', 'name'])
            if len(df_old) > 1000:
                print("♻️ 启动备用方案：使用本地过期的旧版全量股票...")
                return df_old
        except:
            pass

    fallback_df = pd.DataFrame({
        'symbol': ['600519'] + etf_data['symbol'],
        'name': ['贵州茅台'] + etf_data['name']
    })
    fallback_df['display'] = fallback_df['name'] + " (" + fallback_df['symbol'] + ")"
    return fallback_df