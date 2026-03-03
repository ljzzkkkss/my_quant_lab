from abc import ABC, abstractmethod
import pandas as pd
from typing import Dict, Any, List
from dataclasses import dataclass
import warnings

@dataclass
class StrategyParam:
    name: str
    default: Any
    min_val: Any = None
    max_val: Any = None
    step: Any = None
    description: str = ""
    impact: str = "" 

@dataclass
class StrategyResult:
    signals: pd.DataFrame
    metrics: Dict[str, float]

class Strategy(ABC):
    def __init__(self):
        self._params: Dict[str, StrategyParam] = {}

    def register_param(self, name: str, default: Any, min_val: Any=None, max_val: Any=None, step: Any=None, description: str="", impact: str=""):
        self._params[name] = StrategyParam(name, default, min_val, max_val, step, description, impact)

    @property
    def params(self) -> Dict[str, StrategyParam]:
        return self._params

    # 🚀 核心升维：智能参数获取与自动类型强转！
    def get_param(self, name: str, kwargs: Dict[str, Any]) -> Any:
        """
        统一参数获取接口。
        不仅负责读取，还会根据 register_param 中定义的 default 值的类型，
        自动将 kwargs 传来的值强制转型（如 float 强转为 int），彻底消灭 Pandas 报错！
        """
        if name not in self._params:
            warnings.warn(f"警告: 参数 '{name}' 未在策略中注册。")
            return kwargs.get(name)

        param_def = self._params[name]
        raw_val = kwargs.get(name, param_def.default)
        
        # 智能类型推导与强转防弹衣
        expected_type = type(param_def.default)
        if expected_type in (int, float, bool, str):
            try:
                # 针对 Pandas 里的 np.float64 等特殊类型进行安全转换
                if expected_type is int:
                    return int(float(raw_val))
                return expected_type(raw_val)
            except (ValueError, TypeError):
                from utils.logger import logger
                logger.error(f"参数类型转换失败：期望 {expected_type}，实际传入 {raw_val}。已回退到默认值。")
                return param_def.default
                
        return raw_val

    @property
    @abstractmethod
    def name(self) -> str: pass

    @property
    @abstractmethod
    def description(self) -> str: pass

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame, **kwargs) -> pd.DataFrame: pass

class _StrategyRegistry:
    def __init__(self):
        self._strategies: Dict[str, type] = {}

    def register(self, strategy_class: type):
        if not issubclass(strategy_class, Strategy):
            raise TypeError("必须继承自 Strategy 基类")
        temp_instance = strategy_class()
        self._strategies[temp_instance.name] = strategy_class

    def get(self, name: str) -> Strategy:
        if name not in self._strategies:
            raise ValueError(f"策略 {name} 未注册")
        return self._strategies[name]()

    def list_strategies(self) -> List[str]:
        return list(self._strategies.keys())

StrategyRegistry = _StrategyRegistry()

def auto_register(cls):
    StrategyRegistry.register(cls)
    return cls