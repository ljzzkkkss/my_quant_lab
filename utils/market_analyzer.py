import pandas as pd
import numpy as np


class MarketAnalyzer:
    """机构级盘口与形态诊断引擎"""

    @staticmethod
    def find_support_resistance(df: pd.DataFrame, window: int = 20) -> tuple:
        if len(df) < window: return None, None
        recent_data = df.tail(window * 3)
        recent_data['is_high'] = recent_data['最高'] == recent_data['最高'].rolling(window, center=True).max()
        recent_data['is_low'] = recent_data['最低'] == recent_data['最低'].rolling(window, center=True).min()
        highs = recent_data[recent_data['is_high']]['最高'].values
        lows = recent_data[recent_data['is_low']]['最低'].values
        current_price = df['收盘'].iloc[-1]
        resistances = [h for h in highs if h > current_price]
        supports = [l for l in lows if l < current_price]
        return min(resistances) if resistances else df['最高'].max(), max(supports) if supports else df['最低'].min()

    @staticmethod
    def analyze_volume_price(df: pd.DataFrame) -> dict:
        if len(df) < 60: return {"status": "数据不足", "desc": "无法诊断"}
        price_trend = df['收盘'].iloc[-1] / df['收盘'].iloc[-6] - 1
        vol_ratio = df['成交量'].tail(5).mean() / df['成交量'].tail(60).mean() if df['成交量'].tail(
            60).mean() > 0 else 1

        if price_trend > 0.03 and vol_ratio > 1.5:
            return {"status": "🔥 放量突破", "desc": "主力抢筹，量价齐升", "color": "red"}
        elif price_trend > 0.03 and vol_ratio < 0.8:
            return {"status": "⚠️ 缩量诱多", "desc": "无量空涨，防范出货", "color": "orange"}
        elif price_trend < -0.03 and vol_ratio > 1.5:
            return {"status": "🌋 恐慌杀跌", "desc": "放量暴跌，切勿抄底", "color": "green"}
        elif price_trend < -0.03 and vol_ratio < 0.8:
            return {"status": "💧 缩量洗盘", "desc": "抛压极轻，或为洗盘", "color": "orange"}
        else:
            return {"status": "⚖️ 随波逐流", "desc": "量价平庸，无明显异动", "color": "gray"}

    @staticmethod
    def detect_kline_patterns(df: pd.DataFrame) -> list:
        """🚀 高级形态雷达：识别 K线组合与均线异动"""
        patterns = []
        if len(df) < 20: return patterns

        today = df.iloc[-1]
        yest = df.iloc[-2]

        # 1. 跳空缺口检测 (Gap)
        if today['最低'] > yest['最高'] * 1.005:
            patterns.append(
                {"name": "🚀 向上跳空缺口", "desc": f"在 {yest['最高']:.2f}-{today['最低']:.2f} 形成多头缺口，极强支撑。",
                 "color": "red"})
        elif today['最高'] < yest['最低'] * 0.995:
            patterns.append(
                {"name": "🕳️ 向下跳空缺口", "desc": f"在 {today['最高']:.2f}-{yest['最低']:.2f} 形成空头缺口，沉重抛压。",
                 "color": "green"})

        # 2. 长影线极端形态识别 (实体与影线比例)
        body = abs(today['收盘'] - today['开盘'])
        upper_shadow = today['最高'] - max(today['收盘'], today['开盘'])
        lower_shadow = min(today['收盘'], today['开盘']) - today['最低']
        ma20 = df['收盘'].rolling(20).mean().iloc[-1]

        if upper_shadow > body * 2.5 and today['收盘'] > ma20:
            patterns.append(
                {"name": "🌩️ 高位避雷针", "desc": "长上影线且处于均线上方，警惕主力拉高出货。", "color": "green"})
        if lower_shadow > body * 2.5 and today['收盘'] < ma20:
            patterns.append(
                {"name": "🔨 底部探海神针", "desc": "长下影线且处于均线下方，下方买盘承接极强。", "color": "red"})

        # 3. 均线密集缠绕突破 (游资最爱的主升浪起爆点)
        ma5 = df['收盘'].rolling(5).mean().iloc[-1]
        ma10 = df['收盘'].rolling(10).mean().iloc[-1]

        max_ma = max(ma5, ma10, ma20)
        min_ma = min(ma5, ma10, ma20)
        ma_spread = (max_ma - min_ma) / min_ma

        if ma_spread < 0.02 and today['收盘'] > max_ma and today['成交量'] > df['成交量'].rolling(20).mean().iloc[
            -1] * 1.5:
            patterns.append(
                {"name": "🌪️ 均线黏合放量突破", "desc": "短期中期均线极度收敛后放量向上开花，极大概率开启主升浪！",
                 "color": "red"})

        return patterns

    @staticmethod
    def generate_diagnostic_report(df: pd.DataFrame) -> dict:
        if df is None or df.empty or len(df) < 60: return None
        current_price = df['收盘'].iloc[-1]
        sup, res = MarketAnalyzer.find_support_resistance(df)
        vp_analysis = MarketAnalyzer.analyze_volume_price(df)
        patterns = MarketAnalyzer.detect_kline_patterns(df)  # 🚀 挂载形态雷达

        ma20 = df['收盘'].rolling(20).mean().iloc[-1]
        ma60 = df['收盘'].rolling(60).mean().iloc[-1]
        score = sum(
            [40 if current_price > ma20 else -40, 30 if current_price > ma60 else -30, 30 if ma20 > ma60 else -30])

        return {
            "current_price": current_price, "support": sup, "resistance": res,
            "vp_status": vp_analysis["status"], "vp_desc": vp_analysis["desc"], "vp_color": vp_analysis["color"],
            "trend_score": score,
            "patterns": patterns  # 🚀 返回形态结果
        }