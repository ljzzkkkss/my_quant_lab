"""
全局配置管理模块 (工程化版)
"""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

# 加载项目根目录的 .env 文件
load_dotenv()

@dataclass
class MarketConfig:
    """市场规则配置"""
    LIMIT_KC_CYB: float = 0.20      # 科创板、创业板涨跌停 20%
    LIMIT_BJ: float = 0.30          # 北交所涨跌停 30%
    LIMIT_MAIN: float = 0.10        # 主板及ETF涨跌停 10%

@dataclass
class FilterConfig:
    """高级过滤器与底层指标的默认计算周期"""
    VOL_MA_PERIOD: int = 5          # 量比计算的均线周期
    RSI_PERIOD: int = 14            # RSI计算周期
    MA_SLOPE_PERIOD: int = 20       # 趋势斜率计算周期
    MA_SLOPE_SHIFT: int = 3         # 趋势斜率位移周期
    ATR_PERIOD: int = 14            # ATR计算周期
    INDEX_MA_PERIOD: int = 20       # 大盘计算周期
    MACD_FAST: int = 12             # MACD 快线
    MACD_SLOW: int = 26             # MACD 慢线
    MACD_SIGNAL: int = 9            # MACD 信号线

@dataclass
class TradingConfig:
    """交易配置"""
    BUY_FEE_RATE: float = 0.0003      # 买入佣金 万三
    SELL_FEE_RATE: float = 0.0008     # 卖出佣金 + 印花税 万八
    MIN_COMMISSION: float = 5.0       # 最低 5 元门槛
    DEFAULT_SLIPPAGE: float = 0.001   # 默认滑点 0.1%
    DEFAULT_TAKE_PROFIT: float = 0.15 # 默认止盈 15%
    DEFAULT_STOP_LOSS: float = -0.08  # 默认止损 -8%
    MIN_SHARES_MULTIPLE: int = 100  #最小买入单位是多少股

@dataclass
class DataConfig:
    """数据配置"""
    # 从 .env 读取路径，如果没配置则使用默认值
    CACHE_DIR: str = os.getenv("CACHE_DIR", "data/cache")
    STOCK_LIST_CACHE: str = os.getenv("STOCK_LIST_CACHE", "data/cache/stock_list_cache.csv")
    CACHE_TTL_DAYS: int = 7 #缓存有效天数
    DEFAULT_SOURCE: str = "baostock" #默认数据源
    DATA_REFRESH_HOUR: int = 15
    DATA_REFRESH_MINUTE: int = 30

@dataclass
class BacktestConfig:
    """回测配置"""
    BENCHMARK_CODE: str = os.getenv("BENCHMARK_CODE", "510300")
    TRADING_DAYS_PER_YEAR: int = 252 #年交易日
    RISK_FREE_RATE: float = 0.02 #无风险利率

@dataclass
class UIConfig:
    """UI 配置"""
    PAGE_TITLE: str = "极客量化实验室"
    PAGE_ICON: str = "📈"
    LAYOUT_MODE: str = "wide"
    COLOR_UP: str = "red"
    COLOR_DOWN: str = "green"

class ConfigManager:
    """配置管理器 (单例模式)"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.trading = TradingConfig()
        self.data = DataConfig()
        self.backtest = BacktestConfig()
        self.ui = UIConfig()
        self.market = MarketConfig()
        self.filter = FilterConfig()
        self._initialized = True

    @classmethod
    def get_instance(cls) -> 'ConfigManager':
        return cls()

# 快捷访问函数
def get_trading_config() -> TradingConfig:
    return ConfigManager.get_instance().trading

def get_data_config() -> DataConfig:
    return ConfigManager.get_instance().data

def get_backtest_config() -> BacktestConfig:
    return ConfigManager.get_instance().backtest

def get_ui_config() -> UIConfig:
    return ConfigManager.get_instance().ui

def get_market_config() -> MarketConfig:
    return ConfigManager.get_instance().market

def get_filter_config() -> FilterConfig:
    return ConfigManager.get_instance().filter