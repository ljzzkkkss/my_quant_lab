"""
数据获取模块

从 Baostock 获取 A 股历史行情数据，支持增量缓存和重试机制。
"""
import os
import json
import time
import pandas as pd
import streamlit as st
import baostock as bs
from datetime import datetime, timedelta
from typing import Optional
import logging
from configs.settings import get_data_config
data_conf = get_data_config()

logger = logging.getLogger(__name__)


def format_baostock_code(symbol: str) -> str:
    """转换股票代码为 Baostock 格式"""
    symbol = str(symbol).strip()
    if symbol.startswith(('6', '5')):
        return f"sh.{symbol}"
    elif symbol.startswith(('0', '3', '1')):
        return f"sz.{symbol}"
    elif symbol.startswith(('8', '4')):
        return f"bj.{symbol}"
    return symbol


def format_baostock_date(date_str) -> str:
    """格式化日期为 Baostock 要求的格式"""
    if isinstance(date_str, str) and len(date_str) == 8 and "-" not in date_str:
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    if isinstance(date_str, pd.Timestamp) or isinstance(date_str, datetime):
        return date_str.strftime("%Y-%m-%d")
    return date_str


def _fetch_with_adjustflag(bs_code: str, bs_start: str, bs_end: str) -> Optional[pd.DataFrame]:
    """
    执行 Baostock 请求，支持 ETF 复权降级

    参数:
        bs_code: Baostock 格式的代码
        bs_start: 开始日期
        bs_end: 结束日期

    返回:
        DataFrame 或 None
    """
    lg = bs.login()
    if lg.error_code != '0':
        return None

    data_list = []

    # 【第一次尝试】：请求前复权数据 (A 股适用)
    rs = bs.query_history_k_data_plus(
        bs_code, "date,open,close,high,low,volume",
        start_date=bs_start, end_date=bs_end, frequency="d", adjustflag="2"
    )

    if rs.error_code == '0':
        while rs.next():
            data_list.append(rs.get_row_data())

    # 【第二次尝试】：如果拿不到数据 (ETF 通常不支持复权)，改用不复权重新请求！
    if not data_list:
        rs = bs.query_history_k_data_plus(
            bs_code, "date,open,close,high,low,volume",
            start_date=bs_start, end_date=bs_end, frequency="d", adjustflag="3"
        )
        if rs.error_code == '0':
            while rs.next():
                data_list.append(rs.get_row_data())

    bs.logout()

    if not data_list:
        return None

    df = pd.DataFrame(data_list, columns=rs.fields)
    df.rename(
        columns={'date': '日期', 'open': '开盘', 'close': '收盘', 'high': '最高', 'low': '最低', 'volume': '成交量'},
        inplace=True)
    df['日期'] = pd.to_datetime(df['日期'])
    df.set_index('日期', inplace=True)
    cols = ['开盘', '收盘', '最高', '最低', '成交量']
    df[cols] = df[cols].apply(pd.to_numeric, errors='coerce')

    return df


def fetch_from_baostock(symbol: str, start_date, end_date, max_retries: int = 3) -> pd.DataFrame:
    """
    获取数据（带重试机制）

    参数:
        symbol: 股票代码
        start_date: 开始日期
        end_date: 结束日期
        max_retries: 最大重试次数

    返回:
        DataFrame 或空 DataFrame
    """
    bs_code = format_baostock_code(symbol)
    bs_start = format_baostock_date(start_date)
    bs_end = format_baostock_date(end_date)

    # 重试机制：指数退避
    for attempt in range(max_retries):
        try:
            result = _fetch_with_adjustflag(bs_code, bs_start, bs_end)
            if result is not None and not result.empty:
                return result
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 1s, 2s, 4s...
                logger.warning(f"获取 {symbol} 数据失败 (尝试 {attempt+1}/{max_retries}): {e}，{wait_time}秒后重试...")
                time.sleep(wait_time)
            else:
                logger.error(f"获取 {symbol} 数据失败，已重试 {max_retries} 次：{e}")

    return pd.DataFrame()


def get_daily_hfq_data(symbol: str, start_date: str, end_date: str, cache_dir: str = data_conf.CACHE_DIR) -> Optional[pd.DataFrame]:
    """
    获取前复权数据（带缓存）

    参数:
        symbol: 股票代码
        start_date: 开始日期 (YYYYMMDD)
        end_date: 结束日期 (YYYYMMDD)
        cache_dir: 缓存目录

    返回:
        DataFrame 或 None
    """
    # ==========================================
    # 🛡️ 防火墙 1 & 2：时间旅行纠正与盘中拦截
    # ==========================================
    now = datetime.now()
    today_dt = pd.to_datetime(now.strftime('%Y-%m-%d'))

    req_start_dt = pd.to_datetime(start_date)
    req_end_dt = pd.to_datetime(end_date)

    # 1. 拦截未来时间：最高只能请求到今天
    if req_end_dt > today_dt:
        req_end_dt = today_dt

    # 2. 拦截盘中时间：如果是今天，且当前时间早于 15:30 (收盘数据未清算完)，强制退回昨天
    if req_end_dt == today_dt:
        if now.hour < data_conf.DATA_REFRESH_HOUR or \
                (now.hour == data_conf.DATA_REFRESH_HOUR and now.minute < data_conf.DATA_REFRESH_MINUTE):
            req_end_dt = today_dt - timedelta(days=1)

    # 修正后如果 start 大于 end (例如在长假期间被拦截)，直接返回空
    if req_start_dt > req_end_dt:
        return None

    # ==========================================
    # 💾 读取本地台账与缓存
    # ==========================================
    os.makedirs(cache_dir, exist_ok=True)

    file_path = os.path.join(cache_dir, f"{symbol}.csv")
    meta_path = os.path.join(cache_dir, f"{symbol}_meta.json")

    meta = {"start": "2099-01-01", "end": "1970-01-01"}
    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
        except Exception:
            pass

    local_df = pd.DataFrame()
    if os.path.exists(file_path):
        try:
            local_df = pd.read_csv(file_path, index_col='日期', parse_dates=True)
        except Exception:
            pass  # 防止 CSV 损坏

    # ==========================================
    # 🌐 场景 A：首次拉取
    # ==========================================
    if local_df.empty:
        try:
            st.toast(f"📥 首次发现标的 {symbol}，正在从云端下载全量历史数据，请稍候...", icon="☁️")
        except:
            pass
        print(f"🌐 未发现 {symbol} 的本地数据库，执行首次拉取...")
        local_df = fetch_from_baostock(symbol, req_start_dt.strftime('%Y%m%d'), req_end_dt.strftime('%Y%m%d'))

        # 🚨 防火墙 3：如果首次拉取彻底没数据（断网或退市），绝对不要生成空台账，直接抛弃！
        if local_df is None or local_df.empty:
            print(f"❌ {symbol} 彻底无数据 (可能停牌或网络错误)，跳过台账建立。")
            return None

        # 只有真正拿到数据，才建立安全台账
        meta['start'] = req_start_dt.strftime("%Y-%m-%d")
        meta['end'] = req_end_dt.strftime("%Y-%m-%d")
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f)

        local_df.to_csv(file_path, encoding='utf-8-sig')
        print(f"✅ 首次拉取成功，建立台账：{meta_path}")

        mask = (local_df.index >= req_start_dt) & (local_df.index <= req_end_dt)
        return local_df.loc[mask]

    # ==========================================
    # 🔄 场景 B：增量更新
    # ==========================================
    cache_start_cal = pd.to_datetime(meta['start'])
    cache_end_cal = pd.to_datetime(meta['end'])
    needs_update = False

    # 1. 向前补齐历史
    if req_start_dt < cache_start_cal:
        fetch_end = (cache_start_cal - timedelta(days=1)).strftime("%Y%m%d")
        try:
            st.toast(f"📥 正在为 {symbol} 补齐更早的历史数据...", icon="⏳")
        except:
            pass
        print(f"🌐 增量补齐历史：{req_start_dt.strftime('%Y%m%d')} 至 {fetch_end}...")
        older_df = fetch_from_baostock(symbol, req_start_dt.strftime('%Y%m%d'), fetch_end)

        if not older_df.empty:
            local_df = pd.concat([older_df, local_df])
            needs_update = True

        # 无论有没有补到历史数据（可能那会儿还没上市），都把台账往前推，防止每次查都重复请求
        meta['start'] = req_start_dt.strftime("%Y-%m-%d")

    # 2. 向后同步最新
    if req_end_dt > cache_end_cal:
        fetch_start = (cache_end_cal + timedelta(days=1)).strftime("%Y%m%d")
        try:
            st.toast(f"📥 正在同步 {symbol} 最新的日线行情...", icon="⏳")
        except:
            pass
        print(f"🌐 增量同步最新：{fetch_start} 至 {req_end_dt.strftime('%Y%m%d')}...")
        newer_df = fetch_from_baostock(symbol, fetch_start, req_end_dt.strftime('%Y%m%d'))

        if not newer_df.empty:
            local_df = pd.concat([local_df, newer_df])
            needs_update = True

        # 💡 核心逻辑：因为我们有防火墙 1&2，这里的 req_end_dt 绝对是安全且已收盘的日期。
        # 如果 newer_df 是空，只说明这两天是周末或节假日，我们理直气壮地把台账往后推！
        meta['end'] = req_end_dt.strftime("%Y-%m-%d")

    # ==========================================
    # 💾 数据落盘与切片返回
    # ==========================================
    if needs_update and not local_df.empty:
        local_df = local_df[~local_df.index.duplicated(keep='last')].sort_index()
        local_df.to_csv(file_path, encoding='utf-8-sig')

    # 只要台账日期有推进，就更新 JSON
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f)

    mask = (local_df.index >= req_start_dt) & (local_df.index <= req_end_dt)
    res_df = local_df.loc[mask]

    return res_df if not res_df.empty else None
