"""
动态网格波段策略 (Swing Grid)

策略逻辑:
    - 动态计算基准中枢（如 20日均线）
    - 收盘价跌破基准中枢的 X%：恐慌抄底
    - 收盘价突破基准中枢的 Y%：贪婪高抛

适用场景：极度适合宽基 ETF (如沪深300) 和大盘蓝筹股的长期震荡抽血
风险点：单边暴跌大熊市容易深套
"""
import pandas as pd
import numpy as np
from .base import Strategy, auto_register


@auto_register
class SwingGridStrategy(Strategy):
    def __init__(self, baseline=20, grid_down=5.0, grid_up=5.0):
        super().__init__()

        self.register_param(
            name='baseline', default=20, min_val=5, max_val=120, step=5,
            description='网格中枢均线周期',
            impact='网格抛洒的基准锚点。调小：网格跟着价格剧烈上下窜动，变成了短线追涨杀跌；调大(如60)：中枢极稳，非常适合在大盘蓝筹或宽基ETF上做长期高抛低吸。'
        )
        self.register_param(
            name='grid_down', default=5.0, min_val=1.0, max_val=20.0, step=1.0,
            description='抄底跌幅网格 (%)',
            impact='调小(如2%)：稍有回调就买，交易极其频繁，牛市能买足仓位，但震荡市容易很快耗尽现金子弹；调大(如10%)：只在发生极端恐慌暴跌时才出手，安全垫极厚，但资金利用率极低。'
        )
        self.register_param(
            name='grid_up', default=5.0, min_val=1.0, max_val=20.0, step=1.0,
            description='止盈涨幅网格 (%)',
            impact='调小(如2%)：高频“捡钢镚”，胜率极高，每天都有微薄入账；调大(如10%)：试图吃尽大波段，但如果股票一直在窄幅箱体震荡，你将一无所获甚至坐过山车。'
        )

    @property
    def name(self) -> str: return "动态网格波段策略"

    @property
    def description(self) -> str: return "依托均线中枢高抛低吸，震荡市抽血机；单边大熊市易深套"

    def generate_signals(self, df: pd.DataFrame, **kwargs) -> pd.DataFrame:
        bl = kwargs.get('baseline', 20)
        gd = kwargs.get('grid_down', 5.0) / 100.0
        gu = kwargs.get('grid_up', 5.0) / 100.0
        data = df.copy()

        data['Baseline'] = data['收盘'].rolling(window=bl).mean()
        data['Lower_Grid'] = data['Baseline'] * (1 - gd)
        data['Upper_Grid'] = data['Baseline'] * (1 + gu)

        data['signal_state'] = np.nan
        data.loc[data['收盘'] < data['Lower_Grid'], 'signal_state'] = 1.0  # 跌破下轨，超跌抄底
        data.loc[data['收盘'] > data['Upper_Grid'], 'signal_state'] = 0.0  # 突破上轨，泡沫高抛

        data['signal'] = data['signal_state'].ffill().fillna(0)
        data['position_diff'] = data['signal'].diff().fillna(0)

        # UI 图表兼容 (红绿虚线显示网格范围)
        data['Upper'] = data['Upper_Grid']
        data['Lower'] = data['Lower_Grid']

        return data