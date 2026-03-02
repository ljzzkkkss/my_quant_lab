"""
全局配置管理模块 (工程化版)
"""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

# 加载项目根目录的 .env 文件
load_dotenv()

@dataclass
class TradingConfig:
    """交易配置"""
    BUY_FEE_RATE: float = 0.0003      # 买入佣金 万三
    SELL_FEE_RATE: float = 0.0008     # 卖出佣金 + 印花税 万八
    MIN_COMMISSION: float = 5.0       # 最低 5 元门槛
    DEFAULT_SLIPPAGE: float = 0.001   # 默认滑点 0.1%
    DEFAULT_TAKE_PROFIT: float = 0.15 # 默认止盈 15%
    DEFAULT_STOP_LOSS: float = -0.08  # 默认止损 -8%
    DEFAULT_POSITION_RATIO: float = 1.0 #最大仓位比例
    MIN_POSITION_RATIO: float = 0.1 #最小仓位比例
    MIN_SHARES_MULTIPLE: int = 100  #最小买入单位是多少股

@dataclass
class DataConfig:
    """数据配置"""
    # 从 .env 读取路径，如果没配置则使用默认值
    CACHE_DIR: str = os.getenv("CACHE_DIR", "data/cache")
    STOCK_LIST_CACHE: str = os.getenv("STOCK_LIST_CACHE", "data/cache/stock_list_cache.csv")
    CACHE_TTL_DAYS: int = 7 #缓存有效天数
    DEFAULT_SOURCE: str = "baostock" #默认数据源
    MARKET_OPEN_HOUR: int = 9
    MARKET_OPEN_MINUTE: int = 30
    MARKET_CLOSE_HOUR: int = 15
    MARKET_CLOSE_MINUTE: int = 0
    DATA_REFRESH_HOUR: int = 15
    DATA_REFRESH_MINUTE: int = 30

@dataclass
class BacktestConfig:
    """回测配置"""
    BENCHMARK_CODE: str = os.getenv("BENCHMARK_CODE", "510300")
    TRADING_DAYS_PER_YEAR: int = 252 #年交易日
    RISK_FREE_RATE: float = 0.02 #无风险利率
    ENABLE_SLIPPAGE: bool = True  #是否启用滑点
    ENABLECommission: bool = True #是否启用佣金

@dataclass
class UIConfig:
    """UI 配置"""
    PAGE_TITLE: str = "极客量化实验室"
    PAGE_ICON: str = "📈"
    LAYOUT_MODE: str = "wide"
    COLOR_BUY: str = "red"
    COLOR_SELL: str = "green"
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