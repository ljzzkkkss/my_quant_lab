"""
回测模块

提供回测引擎、参数寻优和组合回测功能。
"""
from .engine import (
    run_backtest,
    run_portfolio_backtest,
    plot_equity_curve
)
from .optimizer import (
    apply_advanced_filters,
    optimize_strategy,
    optimize_strategy_sequential
)

__all__ = [

    # 回测引擎
    'run_backtest',
    'run_portfolio_backtest',
    'plot_equity_curve',

    # 寻优
    'apply_advanced_filters',
    'optimize_strategy',
    'optimize_strategy_sequential',
]
