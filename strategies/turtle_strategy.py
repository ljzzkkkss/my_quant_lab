"""
海龟交易法则 (唐奇安通道突破)

策略逻辑:
    - 入场：收盘价突破过去 N 天的最高价 (创阶段新高)
    - 离场：收盘价跌破过去 M 天的最低价 (破阶段新低)

适用场景：捕捉大牛市、大宗商品或妖股，真正做到“截断亏损，让利润奔跑”
风险点：震荡市会被两头打脸，胜率通常偏低(约 35%-40%)，全靠高盈亏比赚钱
"""
import pandas as pd
import numpy as np
from .base import Strategy, auto_register


@auto_register
class TurtleStrategy(Strategy):
    def __init__(self, entry_window=20, exit_window=10):
        super().__init__()

        self.register_param(
            name='entry_window', default=20, min_val=5, max_val=60, step=5,
            description='入场突破周期(唐奇安上轨)',
            impact='调小(如10)：进场极快，能吃到完整鱼头，但震荡市会频繁高位站岗（假突破）；调大(如55)：确认绝对大趋势才进场，胜率极高，但会错过底部启动的第一波利润。'
        )
        self.register_param(
            name='exit_window', default=10, min_val=2, max_val=30, step=2,
            description='离场跌破周期(唐奇安下轨)',
            impact='决定你的持仓底气。调小(如5)：利润保护极好，一旦回调立刻落袋为安，但极容易被主力的洗盘动作震出局；调大(如20)：能扛住剧烈洗盘死拿长牛，但趋势破裂时会回吐大量浮盈。'
        )

    @property
    def name(self) -> str: return "海龟交易法则 (通道突破)"

    @property
    def description(self) -> str: return "追逐绝对趋势，胜率偏低但盈亏比极大；震荡市易被打脸"

    def generate_signals(self, df: pd.DataFrame, **kwargs) -> pd.DataFrame:
        ew = int(kwargs.get('entry_window', 20))
        xw = int(kwargs.get('exit_window', 10))
        data = df.copy()

        # 计算唐奇安通道 (注意：要用 shift(1) 避免用到当天的未来函数)
        data['Donchian_High'] = data['最高'].shift(1).rolling(window=ew).max()
        data['Donchian_Low'] = data['最低'].shift(1).rolling(window=xw).min()

        data['signal_state'] = np.nan
        # 突破上轨做多
        data.loc[data['收盘'] > data['Donchian_High'], 'signal_state'] = 1.0
        # 跌破下轨平仓
        data.loc[data['收盘'] < data['Donchian_Low'], 'signal_state'] = 0.0

        data['signal'] = data['signal_state'].ffill().fillna(0)
        data['position_diff'] = data['signal'].diff().fillna(0)

        # 借用字段名，为了让主界面的图表自动画出通道线
        data['SMA_short'] = data['Donchian_High']
        data['SMA_long'] = data['Donchian_Low']

        return data