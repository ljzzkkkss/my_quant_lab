"""
量价共振策略 (OBV 动能)

策略逻辑:
    - OBV (能量潮)：上涨日的成交量加，下跌日的成交量减，代表主力资金净流入流出
    - 买入：资金面向上 (OBV > OBV均线) 且 技术面向上 (收盘价 > 价格均线)
    - 卖出：只要资金面或技术面任意一个破位，立刻卖出

适用场景：提前埋伏主力资金介入的潜力股，防范无量空涨的陷阱
"""
import pandas as pd
import numpy as np
from .base import Strategy, auto_register


@auto_register
class OBVMomentumStrategy(Strategy):
    def __init__(self, obv_ma=30, price_ma=20):
        super().__init__()

        self.register_param(
            name='obv_ma', default=30, min_val=5, max_val=120, step=5,
            description='OBV 资金均线周期',
            impact='监测主力资金流向的照妖镜。调小(如10)：对游资的短线突击极其敏感，但容易被“对倒放量”骗进场；调大(如60)：只抓大机构的长期建仓期，极其稳健，但买入信号严重滞后。'
        )
        self.register_param(
            name='price_ma', default=20, min_val=5, max_val=120, step=5,
            description='价格均线周期',
            impact='技术面的防线。调小：一旦资金涌入立刻跟随，适合做超短打板；调大：要求股票不仅有资金，还必须走出明确的右侧上升通道才买入。'
        )


    @property
    def name(self) -> str: return "量价共振策略 (OBV动能)"

    @property
    def description(self) -> str: return "资金先行，量价齐升时买入；缩量下跌或资金背离时卖出"

    def generate_signals(self, df: pd.DataFrame, **kwargs) -> pd.DataFrame:
        om = kwargs.get('obv_ma', 30)
        pm = kwargs.get('price_ma', 20)
        data = df.copy()

        # 1. 计算 OBV (能量潮指标)
        direction = np.sign(data['收盘'].diff()).fillna(0)
        data['OBV'] = (data['成交量'] * direction).cumsum()
        data['OBV_MA'] = data['OBV'].rolling(window=om).mean()

        # 2. 计算价格均线
        data['Price_MA'] = data['收盘'].rolling(window=pm).mean()

        # 3. 信号生成
        data['signal_state'] = np.nan
        # 双重共振：资金流入 + 价格多头
        buy_cond = (data['OBV'] > data['OBV_MA']) & (data['收盘'] > data['Price_MA'])
        # 任意破位：资金流出 或 价格跌破均线
        sell_cond = (data['OBV'] < data['OBV_MA']) | (data['收盘'] < data['Price_MA'])

        data.loc[buy_cond, 'signal_state'] = 1.0
        data.loc[sell_cond, 'signal_state'] = 0.0

        data['signal'] = data['signal_state'].ffill().fillna(0)
        data['position_diff'] = data['signal'].diff().fillna(0)

        # UI 图表兼容
        data['SMA_short'] = data['Price_MA']

        return data