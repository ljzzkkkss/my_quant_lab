import pandas as pd
from typing import List, Dict, Optional
from utils.data_fetcher import get_daily_hfq_data
from configs.settings import get_backtest_config
from utils.logger import logger

bt_conf = get_backtest_config()


class DataContext:
    """数据中心上下文：统一管理内存中的个股、大盘与板块数据，拒绝重复IO消耗"""

    def __init__(self):
        self.index_data: Optional[pd.DataFrame] = None
        self.sector_data: Optional[pd.DataFrame] = None  # 板块缓存池
        self.macro_data = None  # 宏观缓存
        self.geo_data = None  # 地缘缓存
        self.stock_data: Dict[str, pd.DataFrame] = {}

    # 🚀 增加 use_sector 和 sector_code 参数
    def preload(self, symbols, start_date, end_date, use_index=False, use_sector=False, sector_code="",
                use_macro=False, macro_code="", use_geo=False, geo_code=""):
        logger.info(f"🔄 开始构建内存数据上下文，预加载 {len(symbols)} 只标的...")

        # 1. 预加载大盘数据
        if use_index:
            self.index_data = get_daily_hfq_data(bt_conf.BENCHMARK_CODE, start_date, end_date)
            if self.index_data is not None:
                logger.info(f"✅ 大盘基准 {bt_conf.BENCHMARK_CODE} 内存装载完毕.")

        # 🚀 2. 预加载板块 ETF 数据
        if use_sector and sector_code:
            self.sector_data = get_daily_hfq_data(sector_code, start_date, end_date)
            if self.sector_data is not None:
                logger.info(f"✅ 板块基准 {sector_code} 内存装载完毕.")

        # 3. 预加载个股数据
        for sym in symbols:
            clean_sym = sym.split('(')[-1].replace(')', '').strip() if '(' in sym else sym
            df = get_daily_hfq_data(clean_sym, start_date, end_date)
            if df is not None and not df.empty:
                self.stock_data[clean_sym] = df

        # 🚀 预加载宏观和地缘数据
        if use_macro and macro_code:
            self.macro_data = get_daily_hfq_data(macro_code, start_date, end_date)
        if use_geo and geo_code:
            self.geo_data = get_daily_hfq_data(geo_code, start_date, end_date)

        logger.info(f"✅ 数据上下文准备完毕，准备起飞 🚀")

    def get_stock(self, symbol: str) -> Optional[pd.DataFrame]:
        """0延迟内存级提取个股数据"""
        symbol = str(symbol)  # 🚀 强制转换保护
        clean_sym = symbol.split('(')[-1].replace(')', '').strip() if '(' in symbol else symbol
        return self.stock_data.get(clean_sym)