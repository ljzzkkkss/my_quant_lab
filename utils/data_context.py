import pandas as pd
from typing import List, Dict, Optional
from utils.data_fetcher import get_daily_hfq_data
from configs.settings import get_backtest_config
from utils.logger import logger

bt_conf = get_backtest_config()


class DataContext:
    """数据中心上下文：统一管理内存中的个股与大盘数据，拒绝重复IO消耗"""

    def __init__(self):
        self.index_data: Optional[pd.DataFrame] = None
        self.stock_data: Dict[str, pd.DataFrame] = {}

    def preload(self, symbols: List[str], start_date: str, end_date: str, use_index: bool = False):
        logger.info(f"🔄 开始构建内存数据上下文，预加载 {len(symbols)} 只标的...")

        # 1. 预加载大盘数据 (多股轮动时，只读1次，而不是重复读50次)
        if use_index:
            self.index_data = get_daily_hfq_data(bt_conf.BENCHMARK_CODE, start_date, end_date)
            if self.index_data is not None:
                logger.info(f"✅ 大盘基准 {bt_conf.BENCHMARK_CODE} 内存装载完毕.")

        # 2. 预加载个股数据
        for sym in symbols:
            # 兼容前端带有名称的格式，如 "贵州茅台 (600519)"
            clean_sym = sym.split('(')[-1].replace(')', '').strip() if '(' in sym else sym
            df = get_daily_hfq_data(clean_sym, start_date, end_date)
            if df is not None and not df.empty:
                self.stock_data[clean_sym] = df

        logger.info(f"✅ 数据上下文准备完毕，已缓存 {len(self.stock_data)} 只标的，准备起飞 🚀")

    def get_stock(self, symbol: str) -> Optional[pd.DataFrame]:
        """0延迟内存级提取个股数据"""
        symbol = str(symbol)  # 🚀 强制转换保护
        clean_sym = symbol.split('(')[-1].replace(')', '').strip() if '(' in symbol else symbol
        return self.stock_data.get(clean_sym)