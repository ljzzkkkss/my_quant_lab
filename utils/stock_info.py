import os
import time
import akshare as ak
import pandas as pd
import streamlit as st
from configs.settings import get_data_config

data_conf = get_data_config()

CACHE_FILE = data_conf.STOCK_LIST_CACHE
CACHE_DIR = data_conf.CACHE_DIR
CACHE_TTL = data_conf.CACHE_TTL_DAYS * 86400  # 天数转秒数


@st.cache_data
def get_a_share_list():
    os.makedirs(CACHE_DIR, exist_ok=True)

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
    try:
        st.toast("🌐 本地代码库已过期，正在从云端同步全市场 5000+ A股与 ETF 最新代码，请保持网络通畅...", icon="🔄")
    except:
        pass
    print("🌐 正在拉取全市场股票与 ETF 列表... (请保持网络通畅)")

    # ================== 🚀 新增：动态拉取全市场 ETF ==================
    df_etf = pd.DataFrame()
    try:
        print("⏳ 尝试拉取全市场 ETF 列表...")
        # 调用东方财富 ETF 实时接口获取近 900+ 只 ETF
        df_etf_raw = ak.fund_etf_spot_em()
        if df_etf_raw is not None and not df_etf_raw.empty:
            df_etf = df_etf_raw[['代码', '名称']].rename(columns={'代码': 'symbol', '名称': 'name'})
            # 统一为字符串，防止代码前导零丢失
            df_etf['symbol'] = df_etf['symbol'].astype(str).str.zfill(6)
            # 给 ETF 名字加个标识后缀，方便在下拉框里直接搜 "ETF" 就能全列出来
            df_etf['name'] = df_etf['name'].apply(lambda x: x if 'ETF' in x.upper() else x + ' ETF')
    except Exception as e:
        print(f"⚠️ ETF 拉取失败，启用基础 ETF 备用列表: {e}")
        # 如果断网或接口抽风，提供 10 只高流动性备选 ETF
        etf_data = {
            'symbol': ['515220', '512880', '510300', '159915', '512100', '512690', '159928', '515030', '512400',
                       '515790'],
            'name': ['煤炭ETF', '证券ETF', '沪深300ETF', '创业板ETF', '中证1000ETF', '酒ETF', '消费ETF', '新能源车ETF',
                     '有色金属ETF', '光伏ETF']
        }
        df_etf = pd.DataFrame(etf_data)
    # =======================================================================

    df_a = None

    # 尝试数据源 1
    try:
        print("⏳ 尝试数据源 1 (基础 A 股列表接口)...")
        df_a = ak.stock_info_a_code_name()
        if df_a is not None and not df_a.empty:
            df_a = df_a.rename(columns={'code': 'symbol'})
            df_a['symbol'] = df_a['symbol'].astype(str).str.zfill(6)
    except Exception as e1:
        print(f"⚠️ 数据源 1 失败: {e1}")

    # 尝试数据源 2
    if df_a is None or len(df_a) < 1000:
        try:
            print("⏳ 尝试数据源 2 (东方财富 A 股实时库)...")
            df_em = ak.stock_zh_a_spot_em()
            if df_em is not None and not df_em.empty:
                df_a = df_em[['代码', '名称']].rename(columns={'代码': 'symbol', '名称': 'name'})
                df_a['symbol'] = df_a['symbol'].astype(str).str.zfill(6)
        except Exception as e2:
            print(f"⚠️ 数据源 2 失败: {e2}")

    # 检验成果并落盘
    if df_a is not None and len(df_a) > 1000:
        # 🚀 将 A 股和 ETF 数据无缝拼接
        df_all = pd.concat([df_a, df_etf], ignore_index=True)
        df_all = df_all.dropna(subset=['symbol', 'name'])
        # 去除可能由于数据源交叉导致的重复代码
        df_all = df_all.drop_duplicates(subset=['symbol'])

        df_all['display'] = df_all['name'].astype(str) + " (" + df_all['symbol'].astype(str) + ")"

        df_all.to_csv(CACHE_FILE, index=False, encoding='utf-8-sig')
        print(f"✅ 列表更新成功，共加载 {len(df_a)} 只 A 股和 {len(df_etf)} 只 ETF 至本地缓存。")
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
        'symbol': ['600519'] + df_etf['symbol'].tolist(),
        'name': ['贵州茅台'] + df_etf['name'].tolist()
    })
    fallback_df['display'] = fallback_df['name'] + " (" + fallback_df['symbol'] + ")"
    return fallback_df


@st.cache_data
def get_a_share_list_display():
    """获取用于前端下拉框显示的列表"""
    from utils.stock_info import get_a_share_list
    df = get_a_share_list()
    # 确保 display 列存在
    if 'display' not in df.columns:
        df['display'] = df['name'].astype(str) + " (" + df['symbol'].astype(str) + ")"
    return df['display'].tolist()