import pandas as pd
import numpy as np
import warnings
from configs.settings import get_filter_config
from sklearn.linear_model import LogisticRegression

filter_conf = get_filter_config()
warnings.filterwarnings("ignore", category=UserWarning)


def apply_advanced_filters(df, params):
    """高级共振过滤器：技术面、大盘、板块、机器学习全维拦截"""
    df = df.copy()
    sector_df = params.get('sector_df')
    index_df = params.get('index_df')

    # 1. 基础指标：成交量放大倍数
    df['vol_ma'] = df['成交量'].rolling(filter_conf.VOL_MA_PERIOD).mean()
    df['volume_ratio'] = df['成交量'] / df['vol_ma'].shift(1)

    # 2. 相对强度：RSI
    delta = df['收盘'].diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1 / filter_conf.RSI_PERIOD, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1 / filter_conf.RSI_PERIOD, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    df['rsi'] = 100 - (100 / (1 + rs))

    # 3. 趋势斜率：计算MA20的斜率
    df['ma_slope'] = df['收盘'].rolling(filter_conf.MA_SLOPE_PERIOD).mean()
    df['slope'] = (df['ma_slope'] - df['ma_slope'].shift(filter_conf.MA_SLOPE_SHIFT)) / df['ma_slope'].shift(
        filter_conf.MA_SLOPE_SHIFT) * 100

    # 4. 波动率：ATR
    high_low = df['最高'] - df['最低']
    high_close = (df['最高'] - df['收盘'].shift()).abs()
    low_close = (df['最低'] - df['收盘'].shift()).abs()
    df['tr'] = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = df['tr'].rolling(filter_conf.ATR_PERIOD).mean()

    # 🚀 5. 修复版：大盘滤镜逻辑
    df['index_ok'] = True
    if params.get('use_index') and index_df is not None:
        if index_df.empty:
            from utils.logger import logger
            logger.error(
                "大盘数据为空！(提示: 个股接口无法拉取纯指数，请改用 ETF 代码如 '510300' 代替沪深300)。已临时放行大盘过滤。")
        else:
            idx_period = int(params.get('index_ma_period', filter_conf.INDEX_MA_PERIOD))
            index_ma = index_df['收盘'].rolling(idx_period).mean()

            # 比较价格与均线
            idx_signal = (index_df['收盘'] > index_ma)
            # 🌟 核心防误杀：均线未生成的前期（NaN），默认大盘安全，防止封杀早期交易
            idx_signal[index_ma.isna()] = True

            # 🌟 核心防错位：剥离所有时区信息，强制转化为纯日期索引对齐
            idx_signal.index = pd.to_datetime(idx_signal.index).tz_localize(None)
            target_index = pd.to_datetime(df.index).tz_localize(None)

            # 映射并对缺失的个别交易日进行前向填充
            df['index_ok'] = idx_signal.reindex(target_index, method='ffill').fillna(True).values

    # 🚀 6. 修复版：板块/行业共振过滤逻辑
    df['sector_ok'] = True
    if params.get('use_sector') and sector_df is not None:
        if sector_df.empty:
            from utils.logger import logger
            logger.error("板块数据为空！请检查板块代码。已临时放行板块过滤。")
        else:
            sec_period = int(params.get('sector_ma_period', 20))
            sector_ma = sector_df['收盘'].rolling(sec_period).mean()
            sec_signal = (sector_df['收盘'] > sector_ma)

            sec_signal[sector_ma.isna()] = True
            sec_signal.index = pd.to_datetime(sec_signal.index).tz_localize(None)
            target_index = pd.to_datetime(df.index).tz_localize(None)

            df['sector_ok'] = sec_signal.reindex(target_index, method='ffill').fillna(True).values

    # 🚀 7. 修复版：综合过滤条件
    # 🌟 使用 fillna() 填充各种指标前期的 NaN 值，使得早期合规的信号能够通过
    df['filter_pass'] = (
            (df['volume_ratio'].fillna(1.0) >= params.get('vol_ratio', 0)) &
            (df['rsi'].fillna(50) <= params.get('rsi_limit', 100)) &
            (df['slope'].fillna(0) >= params.get('slope_min', -999)) &
            (df['index_ok'] == True) &
            (df['sector_ok'] == True)
    )

    # 8. 机器学习 Meta-Labeling 拦截网
    if params.get('use_ml_filter', False):
        try:
            df['future_ret'] = df['收盘'].shift(-5) / df['收盘'] - 1
            df['target'] = (df['future_ret'] > 0).astype(int)

            features = ['rsi', 'volume_ratio', 'slope']

            macro_df = params.get('macro_df')
            if macro_df is not None and not macro_df.empty:
                macro_momentum = macro_df['收盘'].pct_change(periods=5)
                # 对齐索引
                macro_momentum.index = pd.to_datetime(macro_momentum.index).tz_localize(None)
                df['macro_momentum'] = macro_momentum.reindex(target_index).ffill().fillna(0).values
                features.append('macro_momentum')

            geo_df = params.get('geo_df')
            if geo_df is not None and not geo_df.empty:
                geo_returns = geo_df['收盘'].pct_change()
                geo_volatility = geo_returns.rolling(window=5).std()
                geo_volatility.index = pd.to_datetime(geo_volatility.index).tz_localize(None)
                df['geo_volatility'] = geo_volatility.reindex(target_index).ffill().fillna(0).values
                features.append('geo_volatility')

            ml_data = df[features + ['target']].dropna()

            if len(ml_data) > 50:
                model = LogisticRegression(class_weight='balanced')
                model.fit(ml_data[features], ml_data['target'])

                X_all = df[features].fillna(method='bfill').fillna(0)
                df['ml_prob'] = model.predict_proba(X_all)[:, 1]

                ml_threshold = params.get('ml_threshold', 0.50)
                df['ml_ok'] = df['ml_prob'] >= ml_threshold

                df['filter_pass'] = df['filter_pass'] & df['ml_ok']
        except Exception as e:
            from utils.logger import logger
            logger.error(f"❌ 机器学习引擎运行异常: {e}")

    return df