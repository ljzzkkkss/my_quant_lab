"""
双均线动能策略

策略逻辑:
    - 金叉买入：短期均线上穿长期均线
    - 死叉卖出：短期均线下穿长期均线
    - 可选 MACD 动能过滤：金叉时 MACD 必须在水上 (大于 0)

适用场景：捕捉大牛股主升浪
风险点：震荡市反复打脸
"""
import pandas as pd
import numpy as np
from .base import Strategy, auto_register
from configs.settings import get_filter_config
filter_conf = get_filter_config()


def apply_double_ma_strategy(
    df: pd.DataFrame,
    short_window: int = 5,
    long_window: int = 20,
    use_macd_filter: bool = True
) -> pd.DataFrame:
    """
    双均线 + MACD 动能过滤策略（函数式接口，保持向后兼容）

    参数:
        df: 包含 OHLCV 数据的 DataFrame
        short_window: 短期均线周期
        long_window: 长期均线周期
        use_macd_filter: 是否启用 MACD 过滤

    返回:
        包含信号列的 DataFrame
    """
    data = df.copy()

    # 1. 计算基础双均线
    data['SMA_short'] = data['收盘'].rolling(window=short_window).mean()
    data['SMA_long'] = data['收盘'].rolling(window=long_window).mean()

    # 2. 纯手工计算 MACD (经典参数：12, 26, 9)
    exp1 = data['收盘'].ewm(span=filter_conf.MACD_FAST, adjust=False).mean()
    exp2 = data['收盘'].ewm(span=filter_conf.MACD_SLOW, adjust=False).mean()
    data['DIF'] = exp1 - exp2
    data['DEA'] = data['DIF'].ewm(span=filter_conf.MACD_SIGNAL, adjust=False).mean()
    data['MACD'] = (data['DIF'] - data['DEA']) * 2  # MACD 柱子

    # 3. 产生原始的均线交叉状态
    data['ma_signal'] = 0.0
    data.loc[data['SMA_short'] > data['SMA_long'], 'ma_signal'] = 1.0
    data['ma_cross'] = data['ma_signal'].diff()

    # 4. MACD 过滤机制
    if use_macd_filter:
        buy_condition = (data['ma_cross'] == 1.0) & (data['MACD'] > 0)
        sell_condition = (data['ma_cross'] == -1.0)

        data['real_action'] = np.nan
        data.loc[buy_condition, 'real_action'] = 1.0
        data.loc[sell_condition, 'real_action'] = 0.0

        data['signal'] = data['real_action'].ffill().fillna(0)
        data['position_diff'] = data['signal'].diff()
    else:
        data['signal'] = data['ma_signal']
        data['position_diff'] = data['ma_cross']

    return data


@auto_register
class DoubleMaStrategy(Strategy):
    """双均线动能策略（面向对象版本）"""

    def __init__(
        self,
        short_window: int = 5,
        long_window: int = 20,
        use_macd_filter: bool = True
    ):
        super().__init__()
        self.short_window = short_window
        self.long_window = long_window
        self.use_macd_filter = use_macd_filter
        # 注册参数
        self.register_param(
            name='short_window',
            default=5,
            min_val=2,
            max_val=60,
            step=1,
            description='短期均线周期',
            impact='调小：反应极快，能吃到鱼头，但极易被骗线；调大：过滤震荡杂波，但入场滞后。'
        )
        self.register_param(
            name='long_window',
            default=20,
            min_val=10,
            max_val=250,
            step=5,
            description='长期均线周期',
            impact='作为多空分水岭。调小：交易频率大幅增加；调大：适合捕捉长牛，但可能承受极大的利润回撤。'
        )
        self.register_param(
            name='use_macd_filter',
            default=True,
            description='是否启用 MACD 动能过滤',
            impact='开启后可过滤 40% 的无效弱势震荡死叉，但可能在极速拉升的妖股上踏空。'
        )

    @property
    def name(self) -> str:
        return "双均线动能策略"

    @property
    def description(self) -> str:
        return "捕捉大牛股主升浪；震荡市反复打脸"

    def generate_signals(self, df: pd.DataFrame, **kwargs) -> pd.DataFrame:
        short_window = int(kwargs.get('short_window', self.short_window))
        long_window = int(kwargs.get('long_window', self.long_window))
        use_macd_filter = kwargs.get('use_macd_filter', self.use_macd_filter)

        return apply_double_ma_strategy(df, short_window, long_window, use_macd_filter)
