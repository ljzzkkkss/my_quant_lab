"""
数据质量过滤模块

提供涨跌停检测、停牌检测等数据质量过滤功能。
"""
import pandas as pd
import numpy as np
from typing import Tuple, Optional


def detect_suspended_days(df: pd.DataFrame, volume_threshold: float = 0) -> pd.Series:
    """
    检测停牌日

    参数:
        df: 包含成交量的 DataFrame
        volume_threshold: 成交量阈值，低于此值视为停牌

    返回:
        布尔 Series，True 表示停牌
    """
    if '成交量' not in df.columns:
        return pd.Series(False, index=df.index)

    # 成交量为 0 或极低视为停牌
    suspended = df['成交量'] <= volume_threshold
    return suspended


def detect_price_limit(
    df: pd.DataFrame,
    code: str,
    threshold: float = 0.01
) -> Tuple[pd.Series, pd.Series]:
    """
    检测涨跌停

    参数:
        df: 包含收盘价数据的 DataFrame
        code: 股票代码
        threshold: 容差（防止浮点误差）

    返回:
        (涨停 Series, 跌停 Series)
    """
    if '收盘' not in df.columns:
        return pd.Series(False, index=df.index), pd.Series(False, index=df.index)

    # 确定涨跌停幅度
    if code.startswith(('3', '68')):  # 创业板/科创板 20%
        limit_rate = 0.20
    elif code.startswith(('8', '4')):  # 北交所 30%
        limit_rate = 0.30
    elif code.startswith(('1')):  # ETF 通常 10% 或无限制
        limit_rate = 0.10
    else:  # 主板 10%
        limit_rate = 0.10

    # 计算涨跌幅
    pct_change = df['收盘'].pct_change()

    # 检测涨停（接近涨幅上限）
    limit_up = pct_change > (limit_rate - threshold)

    # 检测跌停（接近跌幅下限）
    limit_down = pct_change < (-limit_rate + threshold)

    return limit_up, limit_down


def detect_limit_and_suspended(
    df: pd.DataFrame,
    code: str
) -> pd.DataFrame:
    """
    综合检测涨跌停和停牌

    参数:
        df: OHLCV 数据
        code: 股票代码

    返回:
        添加了 limit_up, limit_down, suspended, tradable 列的 DataFrame
    """
    result = df.copy()

    # 检测停牌
    result['suspended'] = detect_suspended_days(result)

    # 检测涨跌停
    result['limit_up'], result['limit_down'] = detect_price_limit(result, code)

    # 可交易日 = 非停牌且非涨停且非跌停
    result['tradable'] = ~(result['suspended'] | result['limit_up'] | result['limit_down'])

    return result


def filter_non_tradable_days(
    df: pd.DataFrame,
    code: str,
    filter_limit_up: bool = False,
    filter_limit_down: bool = False
) -> pd.DataFrame:
    """
    过滤不可交易日

    参数:
        df: OHLCV 数据
        code: 股票代码
        filter_limit_up: 是否过滤涨停日（涨停买不进）
        filter_limit_down: 是否过滤跌停日（跌停卖不出）

    返回:
        过滤后的 DataFrame
    """
    result = detect_limit_and_suspended(df, code)

    # 基础过滤：停牌日必须过滤
    mask = ~result['suspended']

    # 可选：过滤涨停日（回测时涨停日无法买入）
    if filter_limit_up:
        mask = mask & ~result['limit_up']

    # 可选：过滤跌停日（回测时跌停日无法卖出）
    if filter_limit_down:
        mask = mask & ~result['limit_down']

    return result[mask].copy()


def check_data_quality(df: pd.DataFrame) -> dict:
    """
    检查数据质量

    参数:
        df: OHLCV 数据

    返回:
        质量问题字典
    """
    issues = {
        'missing_open': False,
        'missing_close': False,
        'missing_high': False,
        'missing_low': False,
        'missing_volume': False,
        'zero_volume_days': 0,
        'negative_price_days': 0,
        'duplicate_dates': 0,
        'price_anomaly_days': 0
    }

    # 检查必要列
    if '开盘' not in df.columns:
        issues['missing_open'] = True
    if '收盘' not in df.columns:
        issues['missing_close'] = True
    if '最高' not in df.columns:
        issues['missing_high'] = True
    if '最低' not in df.columns:
        issues['missing_low'] = True
    if '成交量' not in df.columns:
        issues['missing_volume'] = True

    # 检查零成交量
    if '成交量' in df.columns:
        issues['zero_volume_days'] = int((df['成交量'] == 0).sum())

    # 检查负价格
    for col in ['开盘', '收盘', '最高', '最低']:
        if col in df.columns:
            issues['negative_price_days'] += int((df[col] < 0).sum())

    # 检查重复日期
    issues['duplicate_dates'] = int(df.index.duplicated().sum())

    # 检查价格异常（涨跌幅超过 50%）
    if '收盘' in df.columns:
        pct_change = df['收盘'].pct_change().abs()
        issues['price_anomaly_days'] = int((pct_change > 0.5).sum())

    return issues


def validate_ohlcv_data(df: pd.DataFrame, code: str = "") -> Tuple[bool, str]:
    """
    验证 OHLCV 数据有效性

    参数:
        df: OHLCV 数据
        code: 股票代码（用于错误信息）

    返回:
        (是否有效，错误/警告信息)
    """
    if df.empty:
        return False, f"{code}: 数据为空"

    # 检查必要列
    required_cols = ['开盘', '收盘', '最高', '最低']
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        return False, f"{code}: 缺少必要列：{missing}"

    # 检查数据质量
    issues = check_data_quality(df)

    warnings = []

    if issues['duplicate_dates'] > 0:
        warnings.append(f"存在 {issues['duplicate_dates']} 个重复日期")

    if issues['negative_price_days'] > 0:
        return False, f"{code}: 存在 {issues['negative_price_days']} 个负价格日"

    if issues['price_anomaly_days'] > 0:
        warnings.append(f"存在 {issues['price_anomaly_days']} 个异常涨跌幅日（>50%）")

    if issues['zero_volume_days'] > len(df) * 0.1:
        warnings.append(f"存在 {issues['zero_volume_days']} 个零成交量日（占比{issues['zero_volume_days']/len(df)*100:.1f}%）")

    if warnings:
        return True, f"{code}: " + "; ".join(warnings)

    return True, f"{code}: 数据正常"
