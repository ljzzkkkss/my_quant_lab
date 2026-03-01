import pandas as pd
import numpy as np


def apply_advanced_filters(df, index_df, params):
    """
    params 包含:
    - vol_ratio (成交量放大倍数)
    - rsi_limit (RSI超买阈值)
    - slope_min (均线最小斜率)
    - atr_period (ATR周期)
    - use_index (是否开启大盘过滤)
    """
    # 1. 基础指标：成交量放大倍数
    df['vol_ma5'] = df['成交量'].rolling(5).mean()
    df['volume_ratio'] = df['成交量'] / df['vol_ma5'].shift(1)

    # 2. 相对强度：RSI
    delta = df['收盘'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    # 3. 趋势斜率：计算MA20的斜率 (使用变动率近似)
    df['ma20'] = df['收盘'].rolling(20).mean()
    df['slope'] = (df['ma20'] - df['ma20'].shift(3)) / df['ma20'].shift(3) * 100

    # 4. 波动率：ATR
    high_low = df['最高'] - df['最低']
    high_close = (df['最高'] - df['收盘'].shift()).abs()
    low_close = (df['最低'] - df['收盘'].shift()).abs()
    df['tr'] = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = df['tr'].rolling(14).mean()

    # 5. 大盘滤镜逻辑
    df['index_ok'] = True
    if params.get('use_index') and index_df is not None:
        index_ma = index_df['收盘'].rolling(20).mean()
        # 将大盘状态对齐到个股日期
        df['index_ok'] = (index_df['收盘'] > index_ma).reindex(df.index, method='ffill')

    # 综合过滤条件
    df['filter_pass'] = (
            (df['volume_ratio'] >= params.get('vol_ratio', 0)) &
            (df['rsi'] <= params.get('rsi_limit', 100)) &
            (df['slope'] >= params.get('slope_min', -999)) &
            (df['index_ok'] == True)
    )
    return df