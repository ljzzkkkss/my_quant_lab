"""
参数寻优模块 - 支持并行计算

提供策略参数暴力扫描和贝叶斯优化功能。
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Any, Optional, Callable
from multiprocessing import cpu_count
from functools import partial
from concurrent.futures import ProcessPoolExecutor, as_completed
import warnings

from strategies.double_ma import apply_double_ma_strategy
from strategies.bollinger_bands import apply_bollinger_strategy
from strategies.rsi_reversal import apply_rsi_strategy
from strategies.macd_strategy import apply_macd_strategy
from strategies.kdj_strategy import apply_kdj_strategy
from backtest.engine import run_backtest
from configs.settings import get_trading_config
from configs.settings import get_backtest_config
bt_conf = get_backtest_config()
trade_conf = get_trading_config()


def apply_advanced_filters(df: pd.DataFrame, index_df: Optional[pd.DataFrame], filters: Dict) -> pd.DataFrame:
    """
    应用高级过滤条件

    参数:
        df: 策略信号 DataFrame
        index_df: 大盘指数 DataFrame
        filters: 过滤器配置

    返回:
        添加 filter_pass 列的 DataFrame
    """
    # 计算 RSI
    delta = df['收盘'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    # 计算量比
    df['vol_ma5'] = df['成交量'].rolling(5).mean()
    df['volume_ratio'] = df['成交量'] / df['vol_ma5'].shift(1)

    # 计算均线斜率
    ma20 = df['收盘'].rolling(20).mean()
    df['slope'] = (ma20 - ma20.shift(3)) / ma20.shift(3) * 100

    # 大盘择时过滤
    df['index_ok'] = True
    if filters.get('use_index') and index_df is not None:
        idx_ma20 = index_df['收盘'].rolling(20).mean()
        index_status = (index_df['收盘'] > idx_ma20)
        df['index_ok'] = index_status.reindex(df.index, method='ffill').fillna(False)

    # 综合过滤
    df['filter_pass'] = (
        (df['volume_ratio'] >= filters.get('vol_ratio', 0)) &
        (df['rsi'] <= filters.get('rsi_limit', 100)) &
        (df['slope'] >= filters.get('slope_min', -999)) &
        (df['index_ok'] == True)
    )
    return df


def _evaluate_single_param(
        params: Tuple,
        strategy_type: str,
        raw_data: pd.DataFrame,
        index_data: Optional[pd.DataFrame],
        global_filters: Dict,
        initial_capital: float,
        position_ratio: float
) -> Dict[str, Any]:
    v1, v2 = params
    warnings.filterwarnings('ignore')

    try:
        if strategy_type == "双均线动能策略":
            strat_df = apply_double_ma_strategy(raw_data, int(v1), int(v2), global_filters.get('use_macd', False))
        elif strategy_type == "布林带突破策略":
            strat_df = apply_bollinger_strategy(raw_data, int(v1), float(v2))
        elif strategy_type == "RSI极值反转策略":
            strat_df = apply_rsi_strategy(raw_data, int(v1), int(v2))
        elif strategy_type == "MACD趋势策略":
            strat_df = apply_macd_strategy(raw_data, int(v1), int(v2))
        elif strategy_type == "KDJ震荡策略":
            strat_df = apply_kdj_strategy(raw_data, int(v1), int(v2))
        else:
            return None

        # 🚨 核心逻辑修复：过滤器只能用来拦截买入(入场)，不能强行平掉已有的持仓
        strat_df = apply_advanced_filters(strat_df, index_data, global_filters)

        # 获取原始的建仓和平仓动作
        if 'position_diff' not in strat_df.columns:
            strat_df['position_diff'] = strat_df['signal'].diff().fillna(0)

        strat_df['valid_buy'] = (strat_df['position_diff'] == 1) & strat_df['filter_pass']
        strat_df['valid_sell'] = (strat_df['position_diff'] == -1)

        # 重建正确信号状态
        strat_df['action'] = np.nan
        strat_df.loc[strat_df['valid_buy'], 'action'] = 1
        strat_df.loc[strat_df['valid_sell'], 'action'] = 0
        strat_df['final_signal'] = strat_df['action'].ffill().fillna(0)
        strat_df['position_diff'] = strat_df['final_signal'].diff().fillna(0)

        bt_results = run_backtest(
            strat_df, initial_capital, position_ratio,
            take_profit=global_filters.get('tp', trade_conf.DEFAULT_TAKE_PROFIT),
            stop_loss=global_filters.get('sl', trade_conf.DEFAULT_STOP_LOSS)
        )

        return {
            'p1': v1, 'p2': v2,
            '收益率 (%)': round((bt_results['strategy_equity'].iloc[-1] / initial_capital - 1) * 100, 2),
            '最大回撤 (%)': bt_results.attrs.get('max_drawdown', 0),
            '夏普比率': bt_results.attrs.get('sharpe_ratio', 0),
            '胜率 (%)': bt_results.attrs.get('win_rate', 0),
            '盈亏比': bt_results.attrs.get('pl_ratio', 0),
            '交易次数': bt_results.attrs.get('trade_count', 0)
        }
    except Exception as e:
        return None
def optimize_strategy(
    raw_data: pd.DataFrame, strategy_type: str, initial_capital: float,
    global_filters: Dict, position_ratio: float, p1_range: Tuple[int, int, int],
    p2_range: Tuple[int, int, float], start_date: str, end_date: str,
    use_parallel: bool = True, max_workers: Optional[int] = None,
    progress_callback: Optional[Callable[[float], None]] = None  # 👈 新增进度回调参数
) -> Tuple[Optional[pd.DataFrame], str, str]:
    from utils.data_fetcher import get_daily_hfq_data

    index_data = get_daily_hfq_data(bt_conf.BENCHMARK_CODE, start_date, end_date) if global_filters.get('use_index') else None
    param_grid, la, lb = _build_param_grid(strategy_type, p1_range, p2_range)

    if not param_grid:
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
            futures = {executor.submit(eval_func, params): params for params in param_grid}
            total = len(futures)
            for i, future in enumerate(as_completed(futures)):
                result = future.result()
                if result: results.append(result)
                if progress_callback: progress_callback((i + 1) / total) # 👈 触发进度更新
    else:
        total = len(param_grid)
        for i, (v1, v2) in enumerate(param_grid):
            result = _evaluate_single_param((v1, v2), strategy_type, raw_data, index_data, global_filters, initial_capital, position_ratio)
            if result: results.append(result)
            if progress_callback: progress_callback((i + 1) / total)

    if not results:
        return pd.DataFrame(columns=['p1', 'p2', '收益率 (%)', '最大回撤 (%)', '夏普比率', '胜率 (%)', '盈亏比', '交易次数']), la, lb

    result_df = pd.DataFrame(results).fillna(0).rename(columns={'p1': la, 'p2': lb})
    return result_df, la, lb
def _build_param_grid(strategy_type: str, p1_range: Tuple, p2_range: Tuple) -> Tuple[List[Tuple], str, str]:
    if strategy_type == "双均线动能策略":
        return [(s, l) for s in range(p1_range[0], p1_range[1] + 1, p1_range[2]) for l in range(p2_range[0], p2_range[1] + 1, p2_range[2]) if s < l], "短期均线", "长期均线"
    elif strategy_type == "布林带突破策略":
        return [(w, round(float(s), 2)) for w in range(p1_range[0], p1_range[1] + 1, p1_range[2]) for s in np.arange(p2_range[0], p2_range[1] + 0.01, p2_range[2])], "计算周期", "标准差倍数"
    elif strategy_type == "RSI极值反转策略":
        return [(lower, upper) for lower in range(p1_range[0], p1_range[1] + 1, p1_range[2]) for upper in range(p2_range[0], p2_range[1] + 1, p2_range[2]) if lower < upper], "抄底阈值", "逃顶阈值"
    elif strategy_type == "MACD趋势策略":
        return [(fast, slow) for fast in range(p1_range[0], p1_range[1] + 1, p1_range[2]) for slow in range(p2_range[0], p2_range[1] + 1, p2_range[2]) if fast < slow], "快线周期", "慢线周期"
    elif strategy_type == "KDJ震荡策略":
        return [(buy, sell) for buy in range(p1_range[0], p1_range[1] + 1, p1_range[2]) for sell in range(p2_range[0], p2_range[1] + 1, p2_range[2]) if buy < sell], "超卖买入线", "超买卖出线"
    return [], "未知", "未知"

def optimize_strategy_sequential(
    raw_data: pd.DataFrame,
    strategy_type: str,
    initial_capital: float,
    global_filters: Dict,
    position_ratio: float,
    p1_range: Tuple[int, int, int],
    p2_range: Tuple[int, int, float],
    start_date: str,
    end_date: str
) -> Tuple[Optional[pd.DataFrame], str, str]:
    """
    策略参数寻优 - 串行版本（保持向后兼容，用于 Streamlit 进度条显示）

    这是原 optimize_strategy 函数的直接保留版本，用于需要显示进度的场景。
    """
    return optimize_strategy(
        raw_data, strategy_type, initial_capital, global_filters, position_ratio,
        p1_range, p2_range, start_date, end_date, use_parallel=False
    )
