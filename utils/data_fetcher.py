import os
import json
import pandas as pd
import baostock as bs
from datetime import datetime, timedelta


def format_baostock_code(symbol: str):
    symbol = str(symbol).strip()
    if symbol.startswith(('6', '5')):
        return f"sh.{symbol}"
    elif symbol.startswith(('0', '3', '1')):
        return f"sz.{symbol}"
    elif symbol.startswith(('8', '4')):
        return f"bj.{symbol}"
    return symbol


def format_baostock_date(date_str):
    if isinstance(date_str, str) and len(date_str) == 8 and "-" not in date_str:
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    if isinstance(date_str, pd.Timestamp) or isinstance(date_str, datetime):
        return date_str.strftime("%Y-%m-%d")
    return date_str


def fetch_from_baostock(symbol, start_date, end_date):
    """内部核心网络请求函数：增加了 ETF 的复权智能降级"""
    bs_code = format_baostock_code(symbol)
    bs_start = format_baostock_date(start_date)
    bs_end = format_baostock_date(end_date)

    lg = bs.login()
    if lg.error_code != '0':
        return pd.DataFrame()

    # 【第一次尝试】：请求前复权数据 (A股适用)
    rs = bs.query_history_k_data_plus(
        bs_code, "date,open,close,high,low,volume",
        start_date=bs_start, end_date=bs_end, frequency="d", adjustflag="2"
    )

    data_list = []
    if rs.error_code == '0':
        while rs.next():
            data_list.append(rs.get_row_data())

    # 【第二次尝试(核心修复)】：如果拿不到数据(ETF通常不支持复权)，改用不复权重新请求！
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
        print(f"⚠️ 查无数据 (可能不支持该标的或停牌): {symbol}")
        return pd.DataFrame()

    df = pd.DataFrame(data_list, columns=rs.fields)
    df.rename(
        columns={'date': '日期', 'open': '开盘', 'close': '收盘', 'high': '最高', 'low': '最低', 'volume': '成交量'},
        inplace=True)
    df['日期'] = pd.to_datetime(df['日期'])
    df.set_index('日期', inplace=True)
    cols = ['开盘', '收盘', '最高', '最低', '成交量']
    df[cols] = df[cols].apply(pd.to_numeric, errors='coerce')

    return df


def get_daily_hfq_data(symbol: str, start_date: str, end_date: str, cache_dir: str = "data"):
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)

    file_path = os.path.join(cache_dir, f"{symbol}.csv")
    meta_path = os.path.join(cache_dir, f"{symbol}_meta.json")

    req_start = pd.to_datetime(start_date)
    req_end = pd.to_datetime(end_date)

    meta = {"start": "2099-01-01", "end": "1970-01-01"}
    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
        except Exception:
            pass

    local_df = pd.DataFrame()
    if os.path.exists(file_path):
        local_df = pd.read_csv(file_path, index_col='日期', parse_dates=True)

    if local_df.empty:
        print(f"🌐 未发现 {symbol} 的本地数据库，执行首次拉取...")
        local_df = fetch_from_baostock(symbol, start_date, end_date)

        # 【核心修复】：无论是否拉到数据，都要写台账！防止下次又被当成“没拉过”而无限重试
        meta['start'] = req_start.strftime("%Y-%m-%d")
        meta['end'] = req_end.strftime("%Y-%m-%d")
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f)

        if not local_df.empty:
            local_df.to_csv(file_path, encoding='utf-8-sig')
            print(f"✅ 首次拉取成功，建立台账：{meta_path}")
        else:
            print(f"❌ {symbol} 彻底无数据，已记录为空台账，跳过后续重复拉取。")

        return local_df.loc[req_start:req_end] if not local_df.empty else None

    cache_start_cal = pd.to_datetime(meta['start'])
    cache_end_cal = pd.to_datetime(meta['end'])
    needs_update = False

    if req_start < cache_start_cal:
        fetch_end = (cache_start_cal - timedelta(days=1)).strftime("%Y%m%d")
        print(f"🌐 增量补齐历史: {req_start.strftime('%Y%m%d')} 至 {fetch_end}...")
        older_df = fetch_from_baostock(symbol, req_start.strftime('%Y%m%d'), fetch_end)
        if not older_df.empty:
            local_df = pd.concat([older_df, local_df])
            needs_update = True
        meta['start'] = req_start.strftime("%Y-%m-%d")

    if req_end > cache_end_cal:
        fetch_start = (cache_end_cal + timedelta(days=1)).strftime("%Y%m%d")
        print(f"🌐 增量同步最新: {fetch_start} 至 {req_end.strftime('%Y%m%d')}...")
        newer_df = fetch_from_baostock(symbol, fetch_start, req_end.strftime('%Y%m%d'))
        if not newer_df.empty:
            local_df = pd.concat([local_df, newer_df])
            needs_update = True
        meta['end'] = req_end.strftime("%Y-%m-%d")

    if needs_update and not local_df.empty:
        local_df = local_df[~local_df.index.duplicated(keep='last')].sort_index()
        local_df.to_csv(file_path, encoding='utf-8-sig')

    # 只要有写操作，就保存台账
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f)

    return local_df.loc[req_start:req_end] if not local_df.empty else None