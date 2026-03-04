import pandas as pd
import numpy as np
import warnings
from configs.settings import get_filter_config
from sklearn.linear_model import LogisticRegression

filter_conf = get_filter_config()
warnings.filterwarnings("ignore", category=UserWarning) # 忽略模型训练的无害警告
def apply_advanced_filters(df, params):
    """
    params 包含:
    - vol_ratio (成交量放大倍数)
    - rsi_limit (RSI超买阈值)
    - slope_min (均线最小斜率)
    - atr_period (ATR周期)
    - use_index (是否开启大盘过滤)
    - use_sector (是否开启板块/行业共振过滤)
    """
    #从 params 字典中安全地提取大盘和板块数据
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
        idx_period = params.get('index_ma_period', filter_conf.INDEX_MA_PERIOD)
        index_ma = index_df['收盘'].rolling(idx_period).mean()
        df['index_ok'] = (index_df['收盘'] > index_ma).reindex(df.index, method='ffill').fillna(False)

    # 🚀 6. 新增：板块/行业共振过滤逻辑
    df['sector_ok'] = True
    if params.get('use_sector') and sector_df is not None:
        sec_period = params.get('sector_ma_period', 20)
        sector_ma = sector_df['收盘'].rolling(sec_period).mean()
        df['sector_ok'] = (sector_df['收盘'] > sector_ma).reindex(df.index, method='ffill').fillna(False)

    # 🚀 7. 综合过滤条件（增加 & (df['sector_ok'] == True)）
    df['filter_pass'] = (
            (df['volume_ratio'] >= params.get('vol_ratio', 0)) &
            (df['rsi'] <= params.get('rsi_limit', 100)) &
            (df['slope'] >= params.get('slope_min', -999)) &
            (df['index_ok'] == True) &
            (df['sector_ok'] == True)
    )
    # 🚀 8. 全新降维打击：轻量级机器学习 Meta-Labeling
    if params.get('use_ml_filter', False):
        try:
            # 目标定义(Labeling)：定义未来 5 天收益率为正视为“成功(1)”，否则为“失败(0)”
            df['future_ret'] = df['收盘'].shift(-5) / df['收盘'] - 1
            df['target'] = (df['future_ret'] > 0).astype(int)

            # 特征选择(Features)：告诉模型重点看哪些技术指标
            features = ['rsi', 'volume_ratio', 'slope']

            # 🌍 1. 注入宏观情绪动能 (5日涨跌幅)
            macro_df = params.get('macro_df')
            if macro_df is not None and not macro_df.empty:
                macro_momentum = macro_df['收盘'].pct_change(periods=5)
                df['macro_momentum'] = macro_momentum.reindex(df.index).fillna(0)
                features.append('macro_momentum')

            # 🔥 2. 注入地缘恐慌波动率 (5日收益率标准差)
            geo_df = params.get('geo_df')
            if geo_df is not None and not geo_df.empty:
                geo_returns = geo_df['收盘'].pct_change()
                geo_volatility = geo_returns.rolling(window=5).std()
                df['geo_volatility'] = geo_volatility.reindex(df.index).fillna(0)
                features.append('geo_volatility')

            # 清洗数据用于训练：丢掉最后5天(因为没有未来收益)以及含有NaN的行
            ml_data = df[features + ['target']].dropna()

            if len(ml_data) > 50:  # 只有当这只股票历史数据足够时才进行训练
                # 使用逻辑回归：占用内存极小，速度为毫秒级，且天生具备概率输出
                # class_weight='balanced' 用于解决牛熊市样本不均衡问题
                model = LogisticRegression(class_weight='balanced')

                # 训练模型：让它去领悟这只股票特有的“股性”
                model.fit(ml_data[features], ml_data['target'])

                # 推理预测：将所有历史日期的技术指标喂给模型，吐出当天的上涨概率
                X_all = df[features].fillna(method='bfill').fillna(0)
                df['ml_prob'] = model.predict_proba(X_all)[:, 1]  # 提取标签为 1(上涨) 的概率

                # 动态裁决：如果上涨概率低于设定的阈值，即使 MACD 金叉也强行拦截
                ml_threshold = params.get('ml_threshold', 0.50)
                df['ml_ok'] = df['ml_prob'] >= ml_threshold

                # 将机器学习裁决结果与技术面结果进行最后求与(&)
                df['filter_pass'] = df['filter_pass'] & df['ml_ok']
        except Exception as e:
            from utils.logger import logger
            logger.error(f"❌ 机器学习引擎运行异常: {e}")

    return df