# 🚀 极客量化实验室

<div align="center">

一个专业级的 A 股量化回测与策略优化系统

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.54.0+-red.svg)](https://streamlit.io/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

</div>

---

## 📖 项目简介

**极客量化实验室** 是一款面向 A 股市场的全维度量化策略回测系统，集成了：

- 📊 **手动回测看板** - 单标的精细化分析与实盘体检
- 🤖 **机器参数寻优** - 全维网格搜索 + 样本外盲测防过拟合
- 📡 **雷达全场扫描** - 批量策略回测与牛股筛选
- 🧺 **组合轮动实战** - 多股轮动 + 动态资金分配

系统采用 **Baostock** 作为数据源，支持 **9 种经典量化策略**，配备机构级回测引擎和可视化分析工具。

---

## ✨ 核心特性

### 🎯 策略矩阵

| 策略名称 | 类型 | 适用场景 |
|---------|------|---------|
| MACD | 趋势跟踪 | 震荡上行行情 |
| RSI 反转 | 均值回归 | 超买超卖区间 |
| KDJ | 随机指标 | 短线波动捕捉 |
| 双均线交叉 | 趋势跟踪 | 中长期趋势 |
| 布林带 | 波动率 | 区间震荡行情 |
| 海龟交易 | 趋势突破 | 大趋势行情 |
| 网格交易 | 震荡套利 | 横盘震荡 |
| OBV 动量 | 成交量 | 资金流向追踪 |
| 高级过滤 | 多因子 | 综合选股 |

### 🛡️ 风控引擎

- **硬性止盈止损** - 固定比例触发
- **动态追踪止损** - 盈利达标后自动启用回撤保护
- **大盘择时过滤** - 沪深 300 均线择时
- **板块共振过滤** - 行业 ETF 联动分析
- **量比/RSI/斜率** - 多维技术面过滤

### 🤖 AI 机器学习引擎

- **Meta-Labeling 智能拦截** - 一票否决防骗线系统
- **宏观情绪探针** - 黄金 ETF、标普 500、国债 ETF
- **地缘恐慌探针** - 原油 ETF、军工 ETF
- **胜率预测** - 逻辑回归预测未来 5 天上涨概率

### 💰 交易成本模型

| 项目 | 默认值 | 说明 |
|------|--------|------|
| 买入佣金 | 万分之三 | 券商佣金 |
| 卖出佣金 + 印花税 | 万分之八 | 含 0.05% 印花税 |
| 最低手续费 | 5 元 | 不足 5 元按 5 元收取 |
| 滑点 | 0.1% | 模拟成交价偏差 |

---

## 🏗️ 系统架构

```
my_quant_lab/
├── main.py                 # Streamlit 主入口
├── strategies/             # 策略模块
│   ├── base.py            # 策略基类与注册中心
│   ├── macd_strategy.py   # MACD 策略
│   ├── rsi_reversal.py    # RSI 反转策略
│   ├── kdj_strategy.py    # KDJ 策略
│   ├── double_ma.py       # 双均线策略
│   ├── bollinger_bands.py # 布林带策略
│   ├── turtle_strategy.py # 海龟交易
│   ├── grid_trading.py    # 网格交易
│   ├── obv_momentum.py    # OBV 动量
│   └── advanced_filter.py # 高级过滤
├── backtest/               # 回测引擎
│   ├── engine.py          # 单机/组合回测核心
│   └── optimizer.py       # 参数寻优与过滤
├── views/                  # UI 视图层
│   ├── tab_manual.py      # 手动回测
│   ├── tab_auto.py        # 参数寻优
│   ├── tab_batch.py       # 批量扫描
│   └── tab_portfolio.py   # 组合轮动
├── utils/                  # 工具函数
│   ├── data_fetcher.py    # 数据获取 (Baostock)
│   ├── data_context.py    # 内存数据缓存
│   ├── data_filters.py    # 技术面过滤器
│   ├── market_analyzer.py # 市场分析
│   ├── ui_helpers.py      # UI 辅助工具
│   ├── logger.py          # 日志系统
│   └── workspace.py       # 工作区存档
├── configs/                # 配置中心
│   └── settings.py        # 全局配置管理
├── components/             # 可复用组件
│   └── charts.py          # K 线图表组件
└── requirements.txt        # 依赖清单
```

---

## 🚀 快速开始

### 1. 环境要求

- Python 3.10+
- Windows 10+ / Linux / macOS

### 2. 安装依赖

```bash
# 克隆或进入项目目录
cd my_quant_lab

# 创建虚拟环境（推荐）
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置数据源（可选）

项目默认使用 **Baostock** 免费数据源，无需额外配置。

如需自定义配置，创建 `.env` 文件：

```bash
# 基准指数代码（默认沪深 300ETF）
BENCHMARK_CODE=510300

# 数据缓存路径
CACHE_DIR=D:/quant_data/cache
```

### 4. 启动应用

```bash
streamlit run main.py
```

浏览器自动打开 `http://localhost:8501`

---

## 📋 使用指南

### 标签页 1：📊 手动回测看板

**适用场景**: 深度分析单只股票

1. 选择策略模型（如 MACD）
2. 选择股票代码（如 贵州茅台 600519）
3. 调整策略参数（可选）
4. 点击 "🚀 执行完整回测"
5. 查看：
   - 策略收益 vs 基准收益
   - 夏普比率、胜率、盈亏比
   - 交易信号分布图
   - 净值曲线对比

**特色功能**: 🩺 实盘深度体检报告
- 趋势共振得分
- 资金动能检测
- 阻力位/支撑位分析
- K 线异动形态雷达

---

### 标签页 2：🤖 机器参数寻优

**适用场景**: 策略参数全维扫描

1. 选择策略和股票
2. 勾选参与寻优的参数
3. 设置搜索范围和步长
4. 开启样本外盲测（OOS）- 防过拟合
5. 查看：
   - Top 5 六边形能力雷达图
   - 二维参数收益热力图
   - 多维平行坐标图
   - OOS 盲测排行榜

**机构级评判标准**:
- 盲测夏普比率 > 0.5
- 盲测跑赢大盘（超额 Alpha）
- 训练集/测试集衰减 < 50%

---

### 标签页 3：📡 雷达全场扫描

**适用场景**: 全市场批量回测

1. 选择策略
2. 设置股票池（支持全选）
3. 一键扫描全市场
4. 导出 Top 20 牛股排行榜

**输出指标**:
- 年化收益率
- 夏普比率
- 最大回撤
- 胜率
- 盈亏比

---

### 标签页 4：🧺 组合轮动实战

**适用场景**: 多股轮动 + 资金分配

1. 选取轮动池（5-20 只）
2. 设置最大持仓数（1-10）
3. 选择资金分配模型:
   - **等权资金模型** - 每只等额买入
   - **ATR 风险平价模型** - 按波动率分配
4. 开启动态复利（收益再投资）
5. 查看:
   - 组合净值雪球曲线
   - 动态回撤分布
   - 每日持仓饼图
   - 历史交易流水

---

## ⚙️ 全局设置（侧边栏）

### 资金管理与防守纪律

| 参数 | 默认值 | 说明 |
|------|--------|------|
| 硬性止盈 | 30% | 达到即平仓 |
| 绝对止损 | -8% | 触及即止损 |
| 动态跟踪止损 | 关闭 | 盈利 10% 后激活，回撤 5% 平仓 |

### 过滤引擎

| 过滤器 | 默认值 | 说明 |
|--------|--------|------|
| 大盘择时 | 关闭 | 沪深 300 均线过滤 |
| 板块共振 | 关闭 | 行业 ETF 联动过滤 |
| 量比 | 0.0 | 成交量放大倍数 |
| RSI 超买拦截 | 90 | 超过则禁止买入 |
| 趋势斜率 | -0.2 | 最小向上斜率 |

### AI 机器学习引擎

| 参数 | 默认值 | 说明 |
|------|--------|------|
| 智能胜率预测 | 关闭 | Meta-Labeling 拦截 |
| 最低胜率阈值 | 50% | 放行门槛 |
| 宏观探针 | 可选 | 黄金/标普/国债 ETF |
| 地缘探针 | 可选 | 原油/军工 ETF |

### 交易成本

| 项目 | 默认值 | 可调范围 |
|------|--------|----------|
| 买入费率 | 万三 | 0-30 万 |
| 卖出费率 | 万八 | 0-50 万 |
| 最低手续费 | 5 元 | 0-50 元 |
| 滑点 | 1‰ | 0-10‰ |

---

## 🧠 策略库详解

### MACD 趋势跟踪

```python
# 核心逻辑
DIF = EMA(close, 12) - EMA(close, 26)
DEA = EMA(DIF, 9)
MACD = (DIF - DEA) * 2

# 买入：DIF 上穿 DEA（金叉）
# 卖出：DIF 下穿 DEA（死叉）
```

**参数**:
- `fast_period`: 快线周期 (默认 12)
- `slow_period`: 慢线周期 (默认 26)
- `signal_period`: 信号线周期 (默认 9)

---

### RSI 反转策略

```python
# 核心逻辑
RS = 平均涨幅 / 平均跌幅
RSI = 100 - 100 / (1 + RS)

# 买入：RSI < 30 (超卖)
# 卖出：RSI > 70 (超买)
```

**参数**:
- `rsi_period`: RSI 周期 (默认 14)
- `oversold`: 超卖线 (默认 30)
- `overbought`: 超买线 (默认 70)

---

### KDJ 随机指标

```python
# 核心逻辑
RSV = (收盘价 - N 日最低) / (N 日最高 - N 日最低) * 100
K = SMA(RSV, 3)
D = SMA(K, 3)
J = 3 * K - 2 * D

# 买入：J 从负值上穿 0（极度超卖反弹）
# 卖出：J 从 100 以上跌破 100（极度超买回落）
```

**参数**:
- `n_period`: N 日周期 (默认 9)
- `m1`: K 线平滑 (默认 3)
- `m2`: D 线平滑 (默认 3)

---

### 双均线交叉

```python
# 核心逻辑
SMA_short = SMA(close, 5)
SMA_long = SMA(close, 20)

# 买入：短均线上穿长均线（金叉）
# 卖出：短均线下穿长均线（死叉）
```

**参数**:
- `short_window`: 短周期 (默认 5)
- `long_window`: 长周期 (默认 20)

---

### 布林带策略

```python
# 核心逻辑
MA = SMA(close, 20)
STD = STD(close, 20)
Upper = MA + 2 * STD
Lower = MA - 2 * STD

# 买入：跌破下轨后回升（超卖反弹）
# 卖出：突破上轨后回落（超买回调）
```

**参数**:
- `window`: 周期 (默认 20)
- `std_dev`: 标准差倍数 (默认 2)

---

### 海龟交易法则

```python
# 核心逻辑
Donchian Upper = N 日最高价
Donchian Lower = N 日最低价

# 买入：突破上轨（20 日新高）
# 卖出：跌破下轨（10 日新低）
```

**参数**:
- `entry_window`: 入场周期 (默认 20)
- `exit_window`: 出场周期 (默认 10)

---

### 网格交易

```python
# 核心逻辑
baseline = SMA(close, 20)
grid_down = 5%  # 网格间距
grid_up = 5%

# 买入：跌破基准线 5%/10%/15%...分批建仓
# 卖出：突破基准线 5%/10%/15%...分批平仓
```

**参数**:
- `baseline`: 基准线周期 (默认 20)
- `grid_down`: 下跌网格间距 (默认 5%)
- `grid_up`: 上涨网格间距 (默认 5%)

---

### OBV 动量策略

```python
# 核心逻辑
OBV = 累积成交量（上涨日加，下跌日减）
OBV_MA = SMA(OBV, 30)

# 买入：OBV 上穿均线（资金流入）
# 卖出：价格跌破均线 或 OBV 下穿
```

**参数**:
- `obv_ma`: OBV 均线周期 (默认 30)
- `price_ma`: 价格均线周期 (默认 20)

---

## 🔧 高级功能

### 1. 工作区存档

侧边栏提供：
- **💾 保存当前配置** - 永久保存参数到本地
- **🔄 恢复默认值** - 清空所有设置
- **♻️ 自动恢复** - 启动时自动加载上次配置

### 2. 股票代码库更新

侧边栏点击 "🔄 强制更新股票代码库" 可清除缓存重新拉取全市场 5000+ A 股与 ETF

### 3. 日志查看

运行日志保存在 `logs/` 目录，按日期分割

---

## 📊 性能指标说明

| 指标 | 公式 | 说明 |
|------|------|------|
| 累计收益率 | (最终净值/初始资金) - 1 | 总收益 |
| 年化收益率 | (1+ 累计收益)^(252/天数) - 1 | 年化复利 |
| 夏普比率 | (日收益 - 无风险利率) / 标准差 | 风险调整收益 |
| 最大回撤 | (净值 - cummax)/cummax 的最小值 | 最大亏损幅度 |
| 卡玛比率 | 年化收益 / |最大回撤| | 抗回撤能力 |
| 胜率 | 盈利交易数 / 总交易数 | 成功概率 |
| 盈亏比 | 平均盈利 / 平均亏损 | 赔率 |

---

## 🛠️ 开发指南

### 添加新策略

1. 继承 `Strategy` 基类：

```python
# strategies/my_strategy.py
from strategies.base import Strategy, auto_register

@auto_register
class MyStrategy(Strategy):
    @property
    def name(self) -> str:
        return "我的策略"

    @property
    def description(self) -> str:
        return "策略描述"

    def __init__(self):
        super().__init__()
        self.register_param(
            name="window",
            default=20,
            min_val=5,
            max_val=60,
            step=1,
            description="窗口周期",
            impact="影响信号灵敏度"
        )

    def generate_signals(self, df: pd.DataFrame, **kwargs) -> pd.DataFrame:
        # 实现策略逻辑
        return df
```

2. 在 `strategies/__init__.py` 中导入即可自动注册：

```python
from .my_strategy import MyStrategy
```

---

## ❓ 常见问题

### Q: 数据获取失败怎么办？

A: 检查网络连接，Baostock 需要联网。可点击侧边栏 "🔄 强制更新股票代码库" 清除缓存。

### Q: 回测结果为空？

A: 可能原因：
- 时间范围太短，未产生交易信号
- 过滤条件过严（如 RSI 超买线设得太低）
- 股票停牌或数据缺失

### Q: 如何提高回测速度？

A:
- 减少扫描股票数量
- 缩小参数寻优范围
- 关闭 OOS 盲测

### Q: 追踪止损如何工作？

A:
1. 盈利达到"激活门槛"（默认 10%）后启用
2. 记录持仓期间最高价
3. 当价格从最高价回撤超过"回撤红线"（默认 5%）时平仓
4. 让利润奔跑，同时保护浮盈

### Q: AI 机器学习引擎如何使用？

A:
1. 开启"智能胜率预测拦截"开关
2. 设定"最低胜率放行阈值"（震荡市建议 55%-60%）
3. 可选添加宏观/地缘探针 ETF 作为特征
4. AI 会对每个传统策略信号进行 Meta-Labeling 预测

---

## 📄 许可证

MIT License

---

## 🙏 致谢

- 数据源：[Baostock](http://baostock.com/)
- UI 框架：[Streamlit](https://streamlit.io/)
- 图表库：[Plotly](https://plotly.com/)
- 数据处理：[Pandas](https://pandas.pydata.org/)
- 数值计算：[NumPy](https://numpy.org/)
- 机器学习：[scikit-learn](https://scikit-learn.org/)

---

## 📬 联系方式

如有问题或建议，欢迎提交 Issue。

---

<div align="center">

**🚀 极客量化实验室** - 让每一笔交易都有据可依

Made with ❤️ by Quant Geek Lab

</div>
