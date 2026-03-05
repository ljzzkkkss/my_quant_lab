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
        """🚀 高级形态雷达：识别 K线组合与游资盘口"""
        patterns = []
        if len(df) < 20: return patterns

        today = df.iloc[-1]
        yest = df.iloc[-2]
        yest2 = df.iloc[-3]

        # 实体与影线计算
        body = today['收盘'] - today['开盘']
        abs_body = abs(body)
        upper_shadow = today['最高'] - max(today['收盘'], today['开盘'])
        lower_shadow = min(today['收盘'], today['开盘']) - today['最低']

        body_yest = yest['收盘'] - yest['开盘']

        ma5 = df['收盘'].rolling(5).mean().iloc[-1]
        ma10 = df['收盘'].rolling(10).mean().iloc[-1]
        ma20 = df['收盘'].rolling(20).mean().iloc[-1]
        max_ma = max(ma5, ma10, ma20)
        min_ma = min(ma5, ma10, ma20)

        # 1. 🪓 断头铡刀 (极度看空)
        # 开盘在所有均线之上，收盘砸穿所有均线，且跌幅 > 4%
        if today['开盘'] > max_ma and today['收盘'] < min_ma and today['收盘'] < yest['收盘'] * 0.96:
            patterns.append({"name": "🪓 断头铡刀", "desc": "大阴线直接斩断多根中短期均线，上升趋势彻底破裂，极度危险！",
                             "color": "green", "type": "fatal_sell"})

        # 2. 🌩️ 乌云盖顶 (阶段见顶)
        # 昨天大阳线，今天高开低走，收盘价跌破昨天实体的一半
        if body_yest > yest['开盘'] * 0.03:
            if today['开盘'] > yest['最高'] and today['收盘'] < (yest['开盘'] + yest['收盘']) / 2:
                patterns.append({"name": "🌩️ 乌云盖顶", "desc": "高开低走，空头强势反扑并吞噬昨日大阳线，短期见顶信号。",
                                 "color": "green", "type": "warning_sell"})

        # 3. ☀️ 底部红三兵 (稳步看多)
        # 连续三天阳线，收盘价稳步推高，且站上 20 日均线
        body_yest2 = yest2['收盘'] - yest2['开盘']
        if body > 0 and body_yest > 0 and body_yest2 > 0 and today['收盘'] > yest['收盘'] > yest2['收盘']:
            if today['收盘'] > ma20 and today['收盘'] < ma20 * 1.1:
                patterns.append({"name": "☀️ 底部红三兵", "desc": "连续三根阳线稳步推高，多头力量蓄势待发，右侧建仓良机。",
                                 "color": "red", "type": "strong_buy"})

        # 4. 长影线探底/摸顶
        if upper_shadow > abs_body * 2.5 and upper_shadow > today['收盘'] * 0.03 and today['收盘'] > ma20:
            patterns.append(
                {"name": "🌩️ 高位避雷针", "desc": "长上影线且处于均线上方，上方抛压极重，主力极可能在拉高出货。",
                 "color": "green", "type": "warning_sell"})
        if lower_shadow > abs_body * 2.5 and lower_shadow > today['收盘'] * 0.03 and today['收盘'] < ma20:
            patterns.append(
                {"name": "🔨 底部探海神针", "desc": "长下影线且处于均线下方，下方买盘承接极强，可能是阶段性大底。",
                 "color": "red", "type": "strong_buy"})

        # 5. 跳空缺口检测
        if today['最低'] > yest['最高'] * 1.005:
            patterns.append(
                {"name": "🚀 向上跳空缺口", "desc": f"在 {yest['最高']:.2f}-{today['最低']:.2f} 形成多头缺口，极强支撑。",
                 "color": "red", "type": "support"})
        elif today['最高'] < yest['最低'] * 0.995:
            patterns.append(
                {"name": "🕳️ 向下跳空缺口", "desc": f"在 {today['最高']:.2f}-{yest['最低']:.2f} 形成空头缺口，沉重抛压。",
                 "color": "green", "type": "resistance"})

        # 6. 均线密集缠绕突破 (游资打板最爱)
        ma_spread = (max_ma - min_ma) / min_ma
        vol_ma20 = df['成交量'].rolling(20).mean().iloc[-1]
        if ma_spread < 0.02 and today['收盘'] > max_ma and today['成交量'] > vol_ma20 * 1.5 and today['收盘'] > yest[
            '收盘'] * 1.03:
            patterns.append(
                {"name": "🌪️ 均线黏合放量突破", "desc": "短期中期均线极度收敛后放量大涨，极大概率开启主升浪！",
                 "color": "red", "type": "strong_buy"})

        return patterns

    @staticmethod
    def analyze_external_env(env_filters: dict) -> dict:
        """🌍 解析外部环境探针数据"""
        env_res = {}
        if not env_filters: return env_res

        # 1. 板块共振分析
        if env_filters.get('use_sector') and env_filters.get('sector_df') is not None:
            sdf = env_filters['sector_df']
            if len(sdf) >= 20:
                ma20 = sdf['收盘'].rolling(20).mean().iloc[-1]
                price = sdf['收盘'].iloc[-1]
                if price > ma20:
                    env_res['sector'] = {"status": "🌊 板块顺风", "desc": "行业处于多头趋势，具有上行共振动能",
                                         "color": "#ff4b4b"}  # 红色
                else:
                    env_res['sector'] = {"status": "🚧 板块逆风", "desc": "行业处于空头趋势，个股上涨阻力较大",
                                         "color": "#00b050"}  # 绿色

        # 2. 宏观情绪分析 (黄金)
        if env_filters.get('use_macro') and env_filters.get('macro_df') is not None:
            mdf = env_filters['macro_df']
            if len(mdf) >= 5:
                ret5 = mdf['收盘'].pct_change(5).iloc[-1]
                if ret5 > 0.015:
                    env_res['macro'] = {"status": "🛡️ 避险升温", "desc": f"宏观探针近5日异动上涨 {ret5 * 100:.1f}%",
                                        "color": "orange"}
                elif ret5 < -0.015:
                    env_res['macro'] = {"status": "💸 偏好修复", "desc": f"宏观探针近5日回落 {ret5 * 100:.1f}%",
                                        "color": "gray"}
                else:
                    env_res['macro'] = {"status": "☕ 宏观平稳", "desc": "宏观探针近期无明显异动", "color": "gray"}

        # 3. 地缘恐慌分析 (原油波动率)
        if env_filters.get('use_geo') and env_filters.get('geo_df') is not None:
            gdf = env_filters['geo_df']
            if len(gdf) >= 5:
                vol = gdf['收盘'].pct_change().rolling(5).std().iloc[-1]
                if vol > 0.015:  # 针对 ETF 的波动率阈值
                    env_res['geo'] = {"status": "🔥 地缘动荡",
                                      "desc": f"地缘探针波动率放大至 {vol * 100:.1f}%，警惕突发事件", "color": "orange"}
                else:
                    env_res['geo'] = {"status": "🕊️ 局势平稳", "desc": "地缘探针近期波动率处于正常水平",
                                      "color": "gray"}

        return env_res

    @staticmethod
    def generate_diagnostic_report(df: pd.DataFrame, env_filters: dict = None) -> dict:
        if df is None or df.empty or len(df) < 60: return None
        current_price = df['收盘'].iloc[-1]
        res, sup = MarketAnalyzer.find_support_resistance(df)
        vp_analysis = MarketAnalyzer.analyze_volume_price(df)
        patterns = MarketAnalyzer.detect_kline_patterns(df)

        ma20 = df['收盘'].rolling(20).mean().iloc[-1]
        ma60 = df['收盘'].rolling(60).mean().iloc[-1]
        score = sum(
            [40 if current_price > ma20 else -40, 30 if current_price > ma60 else -30, 30 if ma20 > ma60 else -30])

        # 🚀 新增：调用外部环境诊断
        env_analysis = MarketAnalyzer.analyze_external_env(env_filters)

        return {
            "current_price": current_price, "support": sup, "resistance": res,
            "vp_status": vp_analysis["status"], "vp_desc": vp_analysis["desc"], "vp_color": vp_analysis["color"],
            "trend_score": score,
            "patterns": patterns,
            "env_analysis": env_analysis  # 🚀 将外部环境诊断结果打包返回
        }