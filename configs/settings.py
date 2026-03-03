"""
全局配置管理模块 (极简解耦版)
"""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class MarketConfig:
    LIMIT_KC_CYB: float = 0.20
    LIMIT_BJ: float = 0.30
    LIMIT_MAIN: float = 0.10

@dataclass
class FilterConfig:
    VOL_MA_PERIOD: int = 5
    RSI_PERIOD: int = 14
    MA_SLOPE_PERIOD: int = 20
    MA_SLOPE_SHIFT: int = 3
    ATR_PERIOD: int = 14
    INDEX_MA_PERIOD: int = 20
    MACD_FAST: int = 12
    MACD_SLOW: int = 26
    MACD_SIGNAL: int = 9

@dataclass
class TradingConfig:
    BUY_FEE_RATE: float = 0.0003
    SELL_FEE_RATE: float = 0.0008
    MIN_COMMISSION: float = 5.0
    DEFAULT_SLIPPAGE: float = 0.001
    DEFAULT_TAKE_PROFIT: float = 0.15
    DEFAULT_STOP_LOSS: float = -0.08
    MIN_SHARES_MULTIPLE: int = 100
    # 🚀 新增：动态跟踪止损默认配置
    DEFAULT_USE_TRAILING_STOP: bool = False
    DEFAULT_TRAILING_ACTIVATION: float = 0.10  # 盈利 10% 激活
    DEFAULT_TRAILING_RATE: float = 0.05        # 从最高点回撤 5% 平仓

@dataclass
class DataConfig:
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    CACHE_DIR: str = os.getenv("CACHE_DIR", os.path.join(BASE_DIR, "data", "cache"))
    STOCK_LIST_CACHE: str = os.getenv("STOCK_LIST_CACHE", os.path.join(CACHE_DIR, "stock_list_cache.csv"))
    CACHE_TTL_DAYS: int = 7
    DEFAULT_SOURCE: str = "baostock"
    DATA_REFRESH_HOUR: int = 15
    DATA_REFRESH_MINUTE: int = 30

@dataclass
class BacktestConfig:
    BENCHMARK_CODE: str = os.getenv("BENCHMARK_CODE", "510300")
    TRADING_DAYS_PER_YEAR: int = 252
    RISK_FREE_RATE: float = 0.02

@dataclass
class UIConfig:
    PAGE_TITLE: str = "极客量化实验室"
    PAGE_ICON: str = "📈"
    LAYOUT_MODE: str = "wide"
    COLOR_UP: str = "red"
    COLOR_DOWN: str = "green"

class ConfigManager:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized: return
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

def get_trading_config() -> TradingConfig: return ConfigManager().trading
def get_data_config() -> DataConfig: return ConfigManager().data
def get_backtest_config() -> BacktestConfig: return ConfigManager().backtest
def get_ui_config() -> UIConfig: return ConfigManager().ui
def get_market_config() -> MarketConfig: return ConfigManager().market
def get_filter_config() -> FilterConfig: return ConfigManager().filter