"""
参数寻优模块 - 动态解耦并行计算版
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Any, Optional, Callable
from multiprocessing import cpu_count
from functools import partial
from concurrent.futures import ProcessPoolExecutor, as_completed
import warnings
import itertools

from backtest.engine import run_backtest
from configs.settings import get_trading_config, get_backtest_config, get_filter_config

# 🚀 核心引入：注册表
from strategies.base import StrategyRegistry

bt_conf = get_backtest_config()
trade_conf = get_trading_config()

def apply_advanced_filters(df: pd.DataFrame, index_df: Optional[pd.DataFrame], filters: Dict) -> pd.DataFrame:
    """应用高级过滤条件 (动态读取周期配置)"""
    filter_conf = get_filter_config()

    delta = df['收盘'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(filter_conf.RSI_PERIOD).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(filter_conf.RSI_PERIOD).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    df['vol_ma'] = df['成交量'].rolling(filter_conf.VOL_MA_PERIOD).mean()
    df['volume_ratio'] = df['成交量'] / df['vol_ma'].shift(1)

    ma_slope = df['收盘'].rolling(filter_conf.MA_SLOPE_PERIOD).mean()
    df['slope'] = (ma_slope - ma_slope.shift(filter_conf.MA_SLOPE_SHIFT)) / ma_slope.shift(filter_conf.MA_SLOPE_SHIFT) * 100

    df['index_ok'] = True
    if filters.get('use_index') and index_df is not None:
        idx_ma = index_df['收盘'].rolling(filter_conf.INDEX_MA_PERIOD).mean()
        df['index_ok'] = (index_df['收盘'] > idx_ma).reindex(df.index, method='ffill').fillna(False)

    df['filter_pass'] = (
        (df['volume_ratio'] >= filters.get('vol_ratio', 0)) &
        (df['rsi'] <= filters.get('rsi_limit', 100)) &
        (df['slope'] >= filters.get('slope_min', -999)) &
        (df['index_ok'] == True)
    )
    return df

def _evaluate_single_param(
        param_dict: Dict[str, Any],
        strategy_type: str,
        raw_data: pd.DataFrame,
        index_data: Optional[pd.DataFrame],
        global_filters: Dict,
        initial_capital: float,
        position_ratio: float
) -> Dict[str, Any]:
    warnings.filterwarnings('ignore')
    try:
        # 🚀 1. 动态获取策略实例
        strategy = StrategyRegistry.get(strategy_type)
        if not strategy: return None

        # 🚀 2. 动态生成信号，彻底干掉 if/elif
        strat_df = strategy.generate_signals(raw_data, **param_dict)
        strat_df = apply_advanced_filters(strat_df, index_data, global_filters)

        if 'position_diff' not in strat_df.columns:
            strat_df['position_diff'] = strat_df['signal'].diff().fillna(0)

        strat_df['valid_buy'] = (strat_df['position_diff'] == 1) & strat_df['filter_pass']
        strat_df['valid_sell'] = (strat_df['position_diff'] == -1)

        strat_df['action'] = np.nan
        strat_df.loc[strat_df['valid_buy'], 'action'] = 1
        strat_df.loc[strat_df['valid_sell'], 'action'] = 0
        strat_df['final_signal'] = strat_df['action'].ffill().fillna(0)
        strat_df['position_diff'] = strat_df['final_signal'].diff().fillna(0)

        bt_results = run_backtest(strat_df, initial_capital, position_ratio, global_filters)

        # 动态拼接结果字典
        res = param_dict.copy()
        res.update({
            '收益率 (%)': round((bt_results['strategy_equity'].iloc[-1] / initial_capital - 1) * 100, 2),
            '最大回撤 (%)': bt_results.attrs.get('max_drawdown', 0),
            '夏普比率': bt_results.attrs.get('sharpe_ratio', 0),
            '胜率 (%)': bt_results.attrs.get('win_rate', 0),
            '盈亏比': bt_results.attrs.get('pl_ratio', 0),
            '交易次数': bt_results.attrs.get('trade_count', 0)
        })
        return res
    except Exception:
        return None

def optimize_strategy(
    raw_data: pd.DataFrame, strategy_type: str, initial_capital: float,
    global_filters: Dict, position_ratio: float,
    param_grid_keys: List[str], param_grid_values: List[List[Any]],
    start_date: str, end_date: str,
    use_parallel: bool = True, max_workers: Optional[int] = None,
    progress_callback: Optional[Callable[[float], None]] = None
) -> Tuple[Optional[pd.DataFrame], str, str]:
    from utils.data_fetcher import get_daily_hfq_data

    index_data = get_daily_hfq_data(bt_conf.BENCHMARK_CODE, start_date, end_date) if global_filters.get('use_index') else None

    # 🚀 动态生成网格空间 (支持任意维度)
    combinations = list(itertools.product(*param_grid_values))

    # 获取需要作图的两个坐标系名称
    la = StrategyRegistry.get(strategy_type).params[param_grid_keys[0]].description or param_grid_keys[0]
    lb = StrategyRegistry.get(strategy_type).params[param_grid_keys[1]].description or param_grid_keys[1]

    # 添加基础的过滤规则：如果是同一类型的参数(如长短期)，通常要求前者 < 后者
    valid_combinations = []
    for combo in combinations:
        # 如果是经典两参数，且默认值有大小区分，则应用大小拦截过滤（如快线<慢线）
        if len(combo) == 2:
            default_1 = StrategyRegistry.get(strategy_type).params[param_grid_keys[0]].default
            default_2 = StrategyRegistry.get(strategy_type).params[param_grid_keys[1]].default
            if default_1 < default_2 and combo[0] >= combo[1]:
                continue
        valid_combinations.append({param_grid_keys[i]: val for i, val in enumerate(combo)})

    if not valid_combinations:
        return None, la, lb

    results = []

    if use_parallel:
        num_workers = max_workers or (cpu_count() - 1) or 1
        eval_func = partial(
            _evaluate_single_param, strategy_type=strategy_type, raw_data=raw_data,
            index_data=index_data, global_filters=global_filters,
            initial_capital=initial_capital, position_ratio=position_ratio
        )

        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            futures = {executor.submit(eval_func, p_dict): p_dict for p_dict in valid_combinations}
            total = len(futures)
            for i, future in enumerate(as_completed(futures)):
                result = future.result()
                if result: results.append(result)
                if progress_callback: progress_callback((i + 1) / total)
    else:
        total = len(valid_combinations)
        for i, p_dict in enumerate(valid_combinations):
            result = _evaluate_single_param(p_dict, strategy_type, raw_data, index_data, global_filters, initial_capital, position_ratio)
            if result: results.append(result)
            if progress_callback: progress_callback((i + 1) / total)

    if not results:
        return pd.DataFrame(), la, lb

    result_df = pd.DataFrame(results).fillna(0)
    # 替换列名为中文描述以便于展示
    result_df = result_df.rename(columns={param_grid_keys[0]: la, param_grid_keys[1]: lb})
    return result_df, la, lb

def optimize_strategy_sequential(
    raw_data: pd.DataFrame, strategy_type: str, initial_capital: float,
    global_filters: Dict, position_ratio: float, param_grid_keys: List[str], param_grid_values: List[List[Any]],
    start_date: str, end_date: str
) -> Tuple[Optional[pd.DataFrame], str, str]:
    return optimize_strategy(
        raw_data, strategy_type, initial_capital, global_filters, position_ratio,
        param_grid_keys, param_grid_values, start_date, end_date, use_parallel=False
    )