#!/usr/bin/env python3
# resonance_analyzer.py - 三振共振分析器
import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Optional, Tuple, Any

class ResonanceAnalyzer:
    """三振共振分析器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def analyze_market_trend(self, index_data: pd.DataFrame) -> Dict[str, Any]:
        """分析市场趋势（含位置评估，docs/3z.md）
        :return: 趋势方向/强度/MA20状态/MA60状态/position(高位/中位/低位)/近20日涨幅/详情
        """
        try:
            result = {'趋势方向': '未知', '强度': 0, 'MA20状态': '未知',
                      'MA60状态': '未知', 'position': '未知',
                      '近20日涨幅': None, '详情': []}
            if index_data is None or index_data.empty or len(index_data) < 60:
                result['详情'].append("数据不足，无法分析市场趋势")
                return result
            df = index_data.copy()
            if '收盘价' not in df.columns:
                result['详情'].append("缺少收盘价列")
                return result
            if 'MA20' not in df.columns:
                df['MA20'] = df['收盘价'].rolling(window=20).mean()
            if 'MA60' not in df.columns:
                df['MA60'] = df['收盘价'].rolling(window=60).mean()
            latest = df.iloc[-1]
            close = float(latest['收盘价'])
            ma20, ma60 = latest['MA20'], latest['MA60']
            if pd.notna(ma20):
                result['MA20状态'] = '上方' if close > ma20 else '下方'
            if pd.notna(ma60):
                result['MA60状态'] = '上方' if close > ma60 else '下方'
            if (result['MA20状态'] == '上方' and result['MA60状态'] == '上方'):
                result['趋势方向'] = '向上'
            elif (result['MA20状态'] == '下方' and result['MA60状态'] == '下方'):
                result['趋势方向'] = '向下'
            else:
                result['趋势方向'] = '震荡'
            # 趋势强度：近20日涨幅
            if len(df) >= 20:
                past = float(df['收盘价'].iloc[-20])
                if past > 0:
                    chg = (close / past - 1) * 100
                    result['近20日涨幅'] = round(chg, 2)
                    result['强度'] = min(abs(chg), 100.0)
            # 位置评估（近120日分位）：≥85% 高位，≤15% 低位
            if len(df) >= 120:
                high_120 = float(df['收盘价'].iloc[-120:].max())
                low_120 = float(df['收盘价'].iloc[-120:].min())
                if high_120 > low_120:
                    pos_pct = (close - low_120) / (high_120 - low_120)
                    if pos_pct >= 0.85:
                        result['position'] = '高位'
                    elif pos_pct <= 0.15:
                        result['position'] = '低位'
                    else:
                        result['position'] = '中位'
                    result['详情'].append(f"近120日位置 {pos_pct:.0%}")
            self.logger.info(f"📊 市场趋势: {result['趋势方向']}, "
                             f"位置={result['position']}, 强度={result['强度']:.1f}")
            return result
        except Exception as e:
            self.logger.error(f"❌ 分析市场趋势异常: {e}")
            return {'趋势方向': '异常', '详情': [f"分析异常: {e}"]}
    
    def analyze_industry_trend(self, industry_data: Dict[str, pd.DataFrame],
                               lookback: int = 10) -> Dict[str, Any]:
        """优化后的行业趋势判断（docs/3z.md）
        每行业评分(-2~+3): MA20偏离bias + 近N日涨幅change_n + 成交额放大amount_score
        输入: {行业名: DataFrame}，需含 收盘价（成交额可选）
        输出: 整体趋势/强度/强势弱势中性数量/最强行业top_industries/详情
        """
        empty_result = {'强势行业': [], '弱势行业': [], '中性行业': [],
                        '整体趋势': '未知', '强度': 0,
                        'strong_count': 0, 'weak_count': 0, 'neutral_count': 0,
                        'detail': '无行业数据', 'top_industries': [],
                        'top_detail': [], '详情': ['无行业数据']}
        try:
            if not industry_data:
                return empty_result
            strong, weak, neutral = [], [], []
            industry_scores = []
            close_col, amount_col = '收盘价', '成交额'
            for name, df in industry_data.items():
                if df is None or df.empty or len(df) < 5:
                    continue
                df = df.copy()
                if close_col not in df.columns:
                    continue
                if 'MA20' not in df.columns:
                    df['MA20'] = df[close_col].rolling(window=20).mean()
                latest = df.iloc[-1]
                close = float(latest[close_col])
                # 1. MA20 偏离（bias）
                bias = 0.0
                ma20 = latest.get('MA20')
                if pd.notna(ma20) and ma20 > 0:
                    bias = (close / float(ma20) - 1) * 100
                # 2. 近N日涨幅（持续性）
                change_n = 0.0
                if len(df) >= lookback:
                    past = float(df[close_col].iloc[-lookback])
                    if past > 0:
                        change_n = (close / past - 1) * 100
                # 3. 成交额变化（资金维度，可选）
                amount_score = 0
                if amount_col in df.columns and len(df) >= 6:
                    amount_ma = df[amount_col].iloc[-6:-1].mean()
                    if amount_ma and amount_ma > 0:
                        amount_ratio = float(latest[amount_col]) / amount_ma
                        if amount_ratio >= 1.5:
                            amount_score = 1
                # 综合评分（-2 ~ +3）
                # 注意: 远端分支先判断（bias<-5 同时满足 <-2，顺序不能反）
                score = 0
                if bias < -5:
                    score = -2
                elif bias < -2:
                    score = -1
                elif bias > 5 and change_n > 3:
                    score = 2 + amount_score          # 强势
                elif bias > 2 and change_n > 0:
                    score = 1 + amount_score          # 偏强
                if score >= 2:
                    strong.append(name)
                elif score <= -2:
                    weak.append(name)
                else:
                    neutral.append(name)
                industry_scores.append({
                    'name': name, 'score': score, 'bias': round(bias, 2),
                    'change_n': round(change_n, 2), 'amount_score': amount_score})
            strong_cnt, weak_cnt = len(strong), len(weak)
            total = max(strong_cnt + weak_cnt + len(neutral), 1)
            # 整体趋势：强势/弱势数量差 + 最少数量过滤（避免个别行业脉冲）
            if (strong_cnt >= weak_cnt + 2
                    and strong_cnt >= max(3, int(total * 0.25))):
                trend = '向上'
                strength = min(100, int(strong_cnt / total * 100) + 20)
            elif (weak_cnt >= strong_cnt + 2
                  and weak_cnt >= max(3, int(total * 0.25))):
                trend = '向下'
                strength = min(100, int(weak_cnt / total * 100) + 20)
            else:
                trend = '震荡'
                strength = 30
            # 最强行业（供报告展示）
            top_detail = sorted(
                [x for x in industry_scores if x['score'] >= 2],
                key=lambda x: (x['score'], x['change_n']),
                reverse=True)[:5]
            result = {'强势行业': strong, '弱势行业': weak, '中性行业': neutral,
                      '整体趋势': trend, '强度': strength,
                      'strong_count': strong_cnt, 'weak_count': weak_cnt,
                      'neutral_count': len(neutral),
                      'detail': f'强势{strong_cnt} / 弱势{weak_cnt} / 中性{len(neutral)}',
                      'top_industries': [x['name'] for x in top_detail],
                      'top_detail': top_detail,
                      '详情': [f'强势{strong_cnt} / 弱势{weak_cnt} / 中性{len(neutral)}',
                               f'最强: {[x["name"] for x in top_detail[:3]]}']}
            self.logger.info(f"🏢 行业趋势: {trend}, "
                             f"强势{strong_cnt}/弱势{weak_cnt}/中性{len(neutral)}")
            return result
        except Exception as e:
            self.logger.error(f"❌ 分析行业趋势异常: {e}")
            return {**empty_result, '详情': [f"分析异常: {e}"]}

    def calculate_industry_score_from_sector(
            self, sector_code: str, db_path: str = None,
            marketdb_df: pd.DataFrame = None) -> float:
        """真实板块指数行业趋势分（docs/082202.md 阶段二，满分25）
        基于 sector_kline 真实指数（非个股抽样）：
          MA20偏离×0.4(10分) + 近10日涨幅×0.3(7.5分) + 成交额放大×0.3(7.5分)
        :param sector_code: 板块代码（ths_881155）
        :param db_path: SQLite 路径（默认 db_manager 生产库）
        :param marketdb_df: 可选已读的板块K线（避免重复查询）
        :return: 0~25 分；数据不足20根返回 12.5 中位基准分
        """
        try:
            df = marketdb_df
            if df is None:
                if db_path is None:
                    from data.db_manager import MysteryDB
                    db_path = MysteryDB().db_path
                import sqlite3
                conn = sqlite3.connect(db_path)
                try:
                    rows = conn.execute(
                        "SELECT close, amount FROM sector_kline "
                        "WHERE sector_code=? ORDER BY trade_date DESC LIMIT 60",
                        (sector_code,)).fetchall()
                finally:
                    conn.close()
                if len(rows) < 20:
                    return 12.5
                closes = [r[0] for r in rows][::-1]
                amounts = [r[1] for r in rows][::-1]
            else:
                closes = df['收盘价'].astype(float).tolist()[-60:]
                amounts = df['成交额'].astype(float).tolist()[-60:] \
                    if '成交额' in df.columns else [0.0] * len(closes)
                if len(closes) < 20:
                    return 12.5

            import numpy as np
            closes = np.array(closes, dtype=float)
            amounts = np.array(amounts, dtype=float)
            cur = closes[-1]
            ma20 = closes[-20:].mean()
            # A: MA20 偏离（Max 10）
            bias = (cur - ma20) / ma20 if ma20 > 0 else 0
            bias_score = min(10.0, max(0.0, bias * 100 + 5.0))
            # B: 近10日涨幅（Max 7.5）
            ret10 = (closes[-1] - closes[-10]) / closes[-10] \
                if closes[-10] > 0 else 0
            ret_score = min(7.5, max(0.0, ret10 * 100 + 3.75))
            # C: 成交额放大（Max 7.5）
            recent_amt = amounts[-5:].mean()
            hist_amt = amounts[-20:].mean()
            ratio = recent_amt / (hist_amt + 1e-6)
            vol_score = min(7.5, max(0.0, ratio * 3.75))
            return float(round(bias_score + ret_score + vol_score, 2))
        except Exception as e:
            self.logger.error(f"❌ 行业指数趋势分异常({sector_code}): {e}")
            return 12.5

    def analyze_capital_flow(self, stock_data: Optional[pd.DataFrame]) -> Dict[str, Any]:
        """资金活跃度判断（docs/3z.md，区分真三振的关键）
        量比(≥1.8→+12, ≥1.5→+8) + 成交额(≥1.6→+5) + 换手率(≥3%→+3)，满分20
        返回: active/score/volume_ratio/detail
        """
        empty = {'active': False, 'score': 0, 'volume_ratio': 0.0,
                 'detail': '资金平淡'}
        try:
            if stock_data is None or stock_data.empty or len(stock_data) < 6:
                return empty
            df = stock_data.copy()
            latest = df.iloc[-1]
            vol_col = '成交量' if '成交量' in df.columns else 'volume'
            amount_col = '成交额' if '成交额' in df.columns else 'amount'
            turn_col = '换手率' if '换手率' in df.columns else None
            if vol_col not in df.columns:
                return empty
            vol_ma5 = float(df[vol_col].iloc[-6:-1].mean())
            volume_ratio = float(latest[vol_col]) / (vol_ma5 + 1e-8)
            score = 0
            reasons = []
            if volume_ratio >= 1.8:
                score += 12
                reasons.append(f"量比{volume_ratio:.1f}")
            elif volume_ratio >= 1.5:
                score += 8
                reasons.append(f"量比{volume_ratio:.1f}")
            if amount_col in df.columns and len(df) >= 6:
                amount_ma5 = df[amount_col].iloc[-6:-1].mean()
                if amount_ma5 and amount_ma5 > 0:
                    amount_ratio = float(latest[amount_col]) / amount_ma5
                    if amount_ratio >= 1.6:
                        score += 5
                        reasons.append("成交额放大")
            if turn_col and turn_col in df.columns:
                turnover = float(latest[turn_col]) if pd.notna(latest[turn_col]) else 0.0
                if turnover >= 3.0:
                    score += 3
                    reasons.append(f"换手{turnover:.1f}%")
            score = min(score, 20)
            active = score >= 8 or volume_ratio >= 1.5
            return {'active': active, 'score': score,
                    'volume_ratio': round(volume_ratio, 2),
                    'detail': ' | '.join(reasons) if reasons else '资金平淡'}
        except Exception as e:
            self.logger.error(f"❌ 资金活跃度分析异常: {e}")
            return empty

    def calculate_resonance_score(self, individual_result: Dict, market_result: Dict,
                                 industry_result: Dict,
                                 capital_result: Optional[Dict] = None) -> Dict[str, Any]:
        """四维共振评分（docs/3z.md）
        个股30 + 大盘25 + 行业25 + 资金20 = 100；大盘高位惩罚-15
        真三振: score≥85 且 资金活跃 且 大盘/行业向上 且 个股OK
        返回: 旧字段(个股共振/市场共振/行业共振/总共振评分/共振级别)兼容
              + 新字段(score/level/advice/is_true_three_strike/details/
                capital_active/industry_top/market_position)
        """
        try:
            score = 0.0
            details = []
            # 1. 个股趋势（30）
            stock_ok = bool(individual_result.get('基础过滤', False)) and \
                       bool(individual_result.get('均线多头', False))
            if stock_ok:
                score += 30
                details.append("个股趋势✓(+30)")
            else:
                details.append("个股趋势✗")
            # 2. 大盘趋势（25）
            market_trend = market_result.get('趋势方向', market_result.get('trend', '未知'))
            if market_trend == '向上':
                score += 25
                details.append("大盘向上✓(+25)")
            else:
                details.append(f"大盘{market_trend}")
            # 3. 行业趋势（25）
            industry_trend = industry_result.get('整体趋势', industry_result.get('trend', '未知'))
            if industry_trend == '向上':
                score += 25
                details.append(f"行业向上✓(+25) [{industry_result.get('detail', '')}]")
            else:
                details.append(f"行业{industry_trend}")
            # 4. 资金确认（20）
            capital_score = 0
            capital_active = False
            if capital_result:
                capital_score = float(capital_result.get('score', 0) or 0)
                capital_active = bool(capital_result.get('active', False))
                score += capital_score
                details.append(f"资金(+{capital_score:.0f}) {capital_result.get('detail', '')}")
            # 高位惩罚（15）
            market_position = market_result.get('position', '未知')
            if market_position == '高位':
                score = max(0.0, score - 15)
                details.append("大盘高位惩罚(-15)")
            # 最终定级
            is_true = (score >= 85 and capital_active
                       and market_trend == '向上' and industry_trend == '向上'
                       and stock_ok)
            if is_true:
                level = '真三振（三级）'
                advice = '强烈建议关注！可能是大级别行情启动窗口，大资金跨层级共振'
            elif score >= 70:
                level = '二级共振'
                advice = '可关注，需持续观察资金与板块持续性'
            elif score >= 45:
                level = '一级共振'
                advice = '观望为主，等待更明确的资金与板块信号'
            else:
                level = '无共振'
                advice = '建议观望，留住本金，等待真正的三振机会'
            # 兼容旧字段：个股/市场/行业共振 + 总评分
            result = {
                '个股共振': 30 if stock_ok else 0,
                '市场共振': 25 if market_trend == '向上' else 0,
                '行业共振': 25 if industry_trend == '向上' else 0,
                '总共振评分': round(score, 1),
                '共振级别': level,
                'score': round(score, 1), 'level': level, 'advice': advice,
                'is_true_three_strike': is_true, 'details': details,
                'capital_active': capital_active,
                'industry_top': industry_result.get('top_industries', []),
                'market_position': market_position,
                '详情': details,
            }
            self.logger.info(f"🎯 四维共振评分: {score:.0f}, 级别={level}")
            return result
        except Exception as e:
            self.logger.error(f"❌ 计算共振评分异常: {e}")
            return {'总共振评分': 0, '共振级别': '异常',
                    'score': 0, 'level': '异常',
                    'is_true_three_strike': False, '详情': [f"分析异常: {e}"]}
    
    def generate_resonance_report(self, stock_code: str, individual_result: Dict, 
                                 market_result: Dict, industry_result: Dict, 
                                 resonance_score: Dict) -> Dict[str, Any]:
        """
        生成共振分析报告
        :param stock_code: 股票代码
        :param individual_result: 个股分析结果
        :param market_result: 市场分析结果
        :param industry_result: 行业分析结果
        :param resonance_score: 共振评分结果
        :return: 共振分析报告
        """
        try:
            report = {
                '股票代码': stock_code,
                '分析时间': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
                '个股状态': self._format_individual_status(individual_result),
                '市场状态': self._format_market_status(market_result),
                '行业状态': self._format_industry_status(industry_result),
                '共振分析': resonance_score,
                '投资建议': self._generate_investment_advice(resonance_score),
                '风险提示': self._generate_risk_warning(individual_result, market_result, industry_result)
            }
            
            self.logger.info(f"📋 生成共振分析报告: {stock_code}")
            return report
            
        except Exception as e:
            self.logger.error(f"❌ 生成共振报告异常: {e}")
            return {'股票代码': stock_code, '错误': f"生成报告异常: {e}"}
    
    def _format_individual_status(self, individual_result: Dict) -> str:
        """格式化个股状态"""
        if individual_result.get('基础过滤', False):
            return "✅ 基础条件满足"
        else:
            return "❌ 基础条件不满足"
    
    def _format_market_status(self, market_result: Dict) -> str:
        """格式化市场状态"""
        trend = market_result.get('趋势方向', '未知')
        strength = market_result.get('强度', 0)
        return f"📊 {trend} (强度: {strength:.1f})"
    
    def _format_industry_status(self, industry_result: Dict) -> str:
        """格式化行业状态"""
        trend = industry_result.get('整体趋势', '未知')
        strong_count = len(industry_result.get('强势行业', []))
        weak_count = len(industry_result.get('弱势行业', []))
        return f"🏢 {trend} (强势: {strong_count}, 弱势: {weak_count})"
    
    def _generate_investment_advice(self, resonance_score: Dict) -> str:
        """生成投资建议"""
        score = resonance_score.get('总共振评分', 0)
        level = resonance_score.get('共振级别', '无共振')
        
        if level == '三级共振':
            return "强烈建议买入，把握共振机会"
        elif level == '二级共振':
            return "建议买入，关注共振机会"
        elif level == '一级共振':
            return "可以关注，等待更好的共振机会"
        else:
            return "建议观望，等待共振机会"
    
    def _generate_risk_warning(self, individual_result: Dict, market_result: Dict, 
                              industry_result: Dict) -> List[str]:
        """生成风险提示"""
        warnings = []
        
        # 个股风险
        if not individual_result.get('基础过滤', False):
            warnings.append("个股基础条件不满足，存在风险")
        
        # 市场风险
        if market_result.get('趋势方向') == '向下':
            warnings.append("市场趋势向下，系统性风险较高")
        
        # 行业风险
        if industry_result.get('整体趋势') == '向下':
            warnings.append("行业趋势向下，行业风险较高")
        
        if not warnings:
            warnings.append("暂无明显风险提示")
        
        return warnings
