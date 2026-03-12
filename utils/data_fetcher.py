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
import akshare as ak
from datetime import datetime, timedelta
from utils.logger import logger
from typing import Optional
import pytz
from configs.settings import get_data_config
data_conf = get_data_config()


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


def fetch_from_akshare(symbol: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    """尝试使用 AkShare 获取前复权数据"""
    try:
        # Akshare 需要纯数字代码，例如 '600519'，而不用带 'sh.' 或 'sz.'
        clean_symbol = symbol.split('.')[-1] if '.' in symbol else symbol

        # 调用 AkShare 的东方财富 A 股历史行情接口 (自带前复权)
        df = ak.stock_zh_a_hist(
            symbol=clean_symbol,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="qfq"
        )

        if df is None or df.empty:
            return None

        # 标准化列名和索引，与 Baostock 格式保持一致
        if '日期' in df.columns:
            df['日期'] = pd.to_datetime(df['日期'])
            df.set_index('日期', inplace=True)

        cols_to_keep = ['开盘', '收盘', '最高', '最低', '成交量']

        # 容错：确保拿到的数据包含必须的列
        if not all(col in df.columns for col in cols_to_keep):
            return None

        df = df[cols_to_keep]
        # 强转数值型，防止部分接口返回字符串
        df[cols_to_keep] = df[cols_to_keep].apply(pd.to_numeric, errors='coerce')

        return df
    except Exception as e:
        logger.warning(f"⚠️ AkShare 获取 {symbol} 失败: {e}")
        return None


def fetch_data_with_fallback(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """容灾双通道：优先 AkShare，失败则回退 Baostock"""
    # 尝试主引擎
    print(f"⚡ 尝试主引擎 (AkShare) 拉取 {symbol}: {start_date}-{end_date}...")
    df = fetch_from_akshare(symbol, start_date, end_date)

    if df is not None and not df.empty:
        print(f"✅ 主引擎 (AkShare) 获取成功！")
        return df

    # 主引擎失败，启动备用引擎
    print(f"♻️ 主引擎无数据或超时，启动备用引擎 (Baostock)...")
    return fetch_from_baostock(symbol, start_date, end_date)

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
    tz_shanghai = pytz.timezone('Asia/Shanghai')
    now = datetime.now(tz_shanghai)
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

    file_path = os.path.join(cache_dir, f"{symbol}.parquet")
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
            # Parquet 天然支持保留索引和日期类型，读取极其迅速
            local_df = pd.read_parquet(file_path, engine='pyarrow')
        except Exception as e:
            logger.warning(f"读取 Parquet 缓存失败，可能文件损坏: {e}")

    # ==========================================
    # 🌐 场景 A：首次拉取
    # ==========================================
    if local_df.empty:
        try:
            st.toast(f"📥 首次发现标的 {symbol}，正在从云端下载全量历史数据，请稍候...", icon="☁️")
        except:
            pass
        print(f"🌐 未发现 {symbol} 的本地数据库，执行首次拉取...")
        local_df = fetch_data_with_fallback(symbol, req_start_dt.strftime('%Y%m%d'), req_end_dt.strftime('%Y%m%d'))

        # 🚨 防火墙 3：如果首次拉取彻底没数据（断网或退市），绝对不要生成空台账，直接抛弃！
        if local_df is None or local_df.empty:
            print(f"❌ {symbol} 彻底无数据 (可能停牌或网络错误)，跳过台账建立。")
            return None

        # 只有真正拿到数据，才建立安全台账
        meta['start'] = req_start_dt.strftime("%Y-%m-%d")
        meta['end'] = req_end_dt.strftime("%Y-%m-%d")
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f)

        local_df.to_parquet(file_path, engine='pyarrow')
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
        older_df = fetch_data_with_fallback(symbol, req_start_dt.strftime('%Y%m%d'), fetch_end)

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
        newer_df = fetch_data_with_fallback(symbol, fetch_start, req_end_dt.strftime('%Y%m%d'))

        if not newer_df.empty:
            local_df = pd.concat([local_df, newer_df])
            needs_update = True
            # 🚀 修复点 1：只有真正拿到数据，才把台账更新为拿到的最新数据的日期！
            meta['end'] = newer_df.index.max().strftime("%Y-%m-%d")
        else:
            # 🚀 修复点 2：拿不到数据说明可能是节假日，也可能是数据源延迟。
            # 我们绝对不能“理直气壮地把台账往后推”，而是保持 meta['end'] 不变，明天继续尝试拉取！
            print(f"⚠️ 未获取到 {fetch_start} 之后的数据，暂不推进台账日期。")

    # ==========================================
    # 💾 数据落盘与切片返回
    # ==========================================
    if needs_update and not local_df.empty:
        local_df = local_df[~local_df.index.duplicated(keep='last')].sort_index()
        local_df.to_parquet(file_path, engine='pyarrow')

    # 只要台账日期有推进，就更新 JSON
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f)

    mask = (local_df.index >= req_start_dt) & (local_df.index <= req_end_dt)
    res_df = local_df.loc[mask]

    return res_df if not res_df.empty else None


def get_realtime_stitched_data(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    终极实战数据拉取：历史日线 + 盘中实时快照缝合
    """
    # 1. 拉取历史数据（这里调用你原有的 get_daily_hfq_data 方法）
    # 注意：在 14:50 时，这个接口返回的数据最后一天通常是昨天
    df = get_daily_hfq_data(symbol, start_date, end_date)

    if df is None or df.empty:
        return df

    # 2. 判断今天是否在交易时间（此处为简化版判断，实盘需严格判断交易日）
    today_str = datetime.now().strftime('%Y-%m-%d')
    current_hour = datetime.now().hour

    # 只有在盘中（比如9点到15点），且今天的数据还没生成时，才进行缝合
    if today_str not in df.index and 9 <= current_hour <= 15:
        try:
            # 🚀 瞬间拉取全市场 5000 只股票的实时切片（耗时不到1秒）
            spot_df = ak.stock_zh_a_spot_em()

            # 提取纯数字代码匹配 (如 '600522')
            clean_sym = symbol.split('(')[-1].replace(')', '').strip()
            stock_spot = spot_df[spot_df['代码'] == clean_sym]

            if not stock_spot.empty:
                # 提取实时五要素
                current_price = stock_spot['最新价'].values[0]
                open_price = stock_spot['今开'].values[0]
                high_price = stock_spot['最高'].values[0]
                low_price = stock_spot['最低'].values[0]
                volume = stock_spot['成交量'].values[0]

                # 如果停牌或未开盘，价格可能为 NaN
                if pd.notna(current_price):
                    # 🧵 组装出“今天”的虚拟 K 线
                    today_bar = pd.DataFrame({
                        '开盘': [open_price],
                        '收盘': [current_price],  # 用最新价代替今天的收盘价
                        '最高': [high_price],
                        '最低': [low_price],
                        '成交量': [volume]
                    }, index=[pd.to_datetime(today_str)])

                    # 将这根实时 K 线缝合到历史 DataFrame 的尾部
                    df = pd.concat([df, today_bar])
                    logger.info(f"🧵 成功缝合 {symbol} 实时数据: 当前价 {current_price}")

        except Exception as e:
            logger.error(f"❌ 实时数据缝合失败: {e}")

    return df
