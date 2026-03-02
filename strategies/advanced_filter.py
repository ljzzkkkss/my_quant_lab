import pandas as pd
import numpy as np
from configs.settings import get_filter_config

filter_conf = get_filter_config()
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
    df['vol_ma'] = df['成交量'].rolling(filter_conf.VOL_MA_PERIOD).mean()
    df['volume_ratio'] = df['成交量'] / df['vol_ma'].shift(1)

    # 2. 相对强度：RSI
    delta = df['收盘'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(filter_conf.RSI_PERIOD).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(filter_conf.RSI_PERIOD).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    # 3. 趋势斜率：计算MA20的斜率 (使用变动率近似)
    df['ma_slope'] = df['收盘'].rolling(filter_conf.MA_SLOPE_PERIOD).mean()
    df['slope'] = (df['ma_slope'] - df['ma_slope'].shift(filter_conf.MA_SLOPE_SHIFT)) / df['ma_slope'].shift(
        filter_conf.MA_SLOPE_SHIFT) * 100

    # 4. 波动率：ATR
    high_low = df['最高'] - df['最低']
    high_close = (df['最高'] - df['收盘'].shift()).abs()
    low_close = (df['最低'] - df['收盘'].shift()).abs()
    df['tr'] = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = df['tr'].rolling(filter_conf.ATR_PERIOD).mean()

    # 5. 大盘滤镜逻辑
    df['index_ok'] = True
    if params.get('use_index') and index_df is not None:
        # 🚀 动态读取前端传来的均线周期
        idx_period = params.get('index_ma_period', filter_conf.INDEX_MA_PERIOD)
        index_ma = index_df['收盘'].rolling(idx_period).mean()

        # 🚀 核心修复Bug：原来缺失了这一行，导致大盘择时结果没有被真正应用！
        df['index_ok'] = (index_df['收盘'] > index_ma).reindex(df.index, method='ffill').fillna(False)

    # 综合过滤条件
    df['filter_pass'] = (
            (df['volume_ratio'] >= params.get('vol_ratio', 0)) &
            (df['rsi'] <= params.get('rsi_limit', 100)) &
            (df['slope'] >= params.get('slope_min', -999)) &
            (df['index_ok'] == True)
    )
    return df