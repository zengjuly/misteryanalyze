#!/usr/bin/env python3
# baostock_client.py - 基于Baostock的股票数据获取模块
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import logging
import re
import threading
from typing import List, Dict, Optional, Tuple

try:
    import baostock as bs
    BAOSTOCK_AVAILABLE = True
except ImportError:
    BAOSTOCK_AVAILABLE = False
    logging.warning("⚠️ baostock 未安装，将使用模拟数据源")

# baostock 全局单socket连接，多线程并发调用会导致数据包交错/utf-8解码错误
# 模块级锁：所有 baostock 网络请求必须串行化（线程安全）
BAOSTOCK_LOCK = threading.Lock()

# pandas 3.0 移除了 DataFrame.append，baostock 旧版本仍在使用
# 添加兼容层避免 'DataFrame' object has no attribute 'append'
if not hasattr(pd.DataFrame, 'append'):
    def _append_compat(self, other, ignore_index=False, **kwargs):
        """pandas 3.0 兼容：DataFrame.append 替代实现"""
        return pd.concat([self, other], ignore_index=ignore_index)
    pd.DataFrame.append = _append_compat
    logging.debug("已为 pandas 3.0 添加 DataFrame.append 兼容层")

class BaostockClient:
    """Baostock数据获取客户端"""
    
    @staticmethod
    def normalize_stock_code(stock_code: str) -> str:
        """
        标准化股票代码为baostock格式（9位，如sh.600000）
        支持输入格式: sh600150 / sh.600150 / 600150 / 000001
        :param stock_code: 原始股票代码
        :return: 标准化后的代码
        """
        code = str(stock_code).strip().lower()
        
        # 已经是标准格式 sh.600000 / sz.000001
        if re.match(r'^(sh|sz|bj)\.\d{6}$', code):
            return code
        
        # 带前缀无点号格式 sh600150 / sz000001
        if re.match(r'^(sh|sz|bj)\d{6}$', code):
            return f"{code[:2]}.{code[2:]}"
        
        # 纯数字格式 600150 / 000001
        if re.match(r'^\d{6}$', code):
            if code.startswith(('60', '68', '90')):
                return f"sh.{code}"
            else:
                return f"sz.{code}"
        
        # 无法识别的格式，原样返回（让baostock报错）
        return str(stock_code)
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.login_success = False
        
    def login(self) -> bool:
        """登录Baostock"""
        try:
            lg = bs.login()
            if lg.error_code == '0':
                self.login_success = True
                self.logger.info("✅ Baostock登录成功")
                return True
            else:
                self.logger.error(f"❌ Baostock登录失败: {lg.error_msg}")
                return False
        except Exception as e:
            self.logger.error(f"❌ Baostock登录异常: {e}")
            return False
    
    def logout(self):
        """退出Baostock"""
        if self.login_success:
            bs.logout()
            self.logger.info("👋 Baostock已退出登录")

    def _relogin_if_network_error(self, error: Exception) -> None:
        """
        网络错误自愈：检测到解码/接收错误时重新登录重建socket连接
        baostock 全局单连接，数据包损坏后必须重建连接才能恢复
        """
        err_str = str(error)
        if any(k in err_str for k in ['codec', 'decode', '接收', '网络',
                                      'socket', 'Connection', 'connection',
                                      'timed out', 'Socket']):
            try:
                self.logger.warning("⚠️ 检测到网络异常，重新登录重建连接...")
                try:
                    bs.logout()
                except Exception:
                    pass
                self.login_success = False
                time.sleep(1.0)
                self.login()
            except Exception as e:
                self.logger.error(f"❌ 重新登录失败: {e}")
    
    def get_stock_name(self, stock_code: str) -> str:
        """
        获取股票名称
        :param stock_code: 股票代码（支持多种格式）
        :return: 股票名称，获取失败返回股票代码
        """
        try:
            stock_code = self.normalize_stock_code(stock_code)
            result = bs.query_stock_basic(code=stock_code)
            if result.error_code == '0':
                data = result.get_data()
                if data is not None and not data.empty and 'code_name' in data.columns:
                    name = str(data.iloc[0]['code_name'])
                    if name and name != 'nan':
                        return name
            self.logger.warning(f"⚠️ 获取 {stock_code} 股票名称失败: {result.error_msg}")
        except Exception as e:
            self.logger.warning(f"⚠️ 获取 {stock_code} 股票名称异常: {e}")
        return str(stock_code)
    
    def get_stock_list(self) -> pd.DataFrame:
        """获取A股股票列表"""
        try:
            result = bs.query_stock_basic()
            if result.error_code == '0':
                stock_list = result.get_data()
                self.logger.info(f"📋 获取到 {len(stock_list)} 只A股")
                return stock_list
            else:
                self.logger.error(f"❌ 获取股票列表失败: {result.error_msg}")
                return pd.DataFrame()
        except Exception as e:
            self.logger.error(f"❌ 获取股票列表异常: {e}")
            return pd.DataFrame()
    
    def get_daily_data(self, stock_code: str, start_date: str, end_date: str, 
                     adjustflag: str = '3') -> pd.DataFrame:
        """
        获取日线数据
        :param stock_code: 股票代码，支持sh600000/sh.600000/600000等格式
        :param start_date: 开始日期，格式如'2023-01-01'
        :param end_date: 结束日期，格式如'2023-12-31'
        :param adjustflag: 复权类型，默认'3'为后复权
        :return: 日线数据DataFrame
        """
        # 标准化股票代码
        stock_code = self.normalize_stock_code(stock_code)
        try:
            result = bs.query_history_k_data_plus(
                stock_code, 
                "date,code,open,high,low,close,volume,amount,turn,tradestatus,pctChg,isST",
                start_date=start_date, 
                end_date=end_date,
                frequency="d",
                adjustflag=adjustflag
            )
            
            if result.error_code == '0':
                data = result.get_data()
                if not data.empty:
                    # 数据类型转换
                    numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount', 'turn', 'pctChg']
                    for col in numeric_cols:
                        if col in data.columns:
                            data[col] = pd.to_numeric(data[col], errors='coerce')
                    
                    # 标准化列名
                    data = data.rename(columns={
                        'code': '代码',
                        'open': '开盘价',
                        'high': '最高价', 
                        'low': '最低价',
                        'close': '收盘价',
                        'volume': '成交量',
                        'amount': '成交额',
                        'turn': '换手率',
                        'pctChg': '涨跌幅',
                        'isST': '是否ST'
                    })
                    
                    # 过滤ST股票
                    data = data[data['是否ST'] != 'ST']
                    
                    self.logger.info(f"📈 获取 {stock_code} 日线数据: {len(data)} 条记录")
                    return data
                else:
                    self.logger.warning(f"⚠️ {stock_code} 无日线数据")
                    return pd.DataFrame()
            else:
                self.logger.error(f"❌ 获取 {stock_code} 日线数据失败: {result.error_msg}")
                return pd.DataFrame()
                
        except Exception as e:
            self.logger.error(f"❌ 获取 {stock_code} 日线数据异常: {e}")
            self._relogin_if_network_error(e)  # 网络错误自愈
            return pd.DataFrame()
    
    def get_weekly_data(self, stock_code: str, start_date: str, end_date: str,
                       adjustflag: str = '3') -> pd.DataFrame:
        """获取周线数据"""
        # 标准化股票代码
        stock_code = self.normalize_stock_code(stock_code)
        try:
            result = bs.query_history_k_data_plus(
                stock_code,
                "date,code,open,high,low,close,volume,amount,turn,pctChg",
                start_date=start_date,
                end_date=end_date,
                frequency="w",
                adjustflag=adjustflag
            )
            
            if result.error_code == '0':
                data = result.get_data()
                if not data.empty:
                    numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount', 'turn', 'pctChg']
                    for col in numeric_cols:
                        if col in data.columns:
                            data[col] = pd.to_numeric(data[col], errors='coerce')
                    
                    data = data.rename(columns={
                        'code': '代码',
                        'open': '开盘价',
                        'high': '最高价',
                        'low': '最低价', 
                        'close': '收盘价',
                        'volume': '成交量',
                        'amount': '成交额',
                        'turn': '换手率',
                        'pctChg': '涨跌幅',
                        'isST': '是否ST'
                    })
                    
                    # 过滤ST股票（仅当存在该列时）
                    if '是否ST' in data.columns:
                        data = data[data['是否ST'] != 'ST']
                    
                    self.logger.info(f"📊 获取 {stock_code} 周线数据: {len(data)} 条记录")
                    return data
                else:
                    self.logger.warning(f"⚠️ {stock_code} 无周线数据")
                    return pd.DataFrame()
            else:
                self.logger.error(f"❌ 获取 {stock_code} 周线数据失败: {result.error_msg}")
                return pd.DataFrame()
                
        except Exception as e:
            self.logger.error(f"❌ 获取 {stock_code} 周线数据异常: {e}")
            self._relogin_if_network_error(e)  # 网络错误自愈
            return pd.DataFrame()
    
    def get_monthly_data(self, stock_code: str, start_date: str, end_date: str,
                        adjustflag: str = '3') -> pd.DataFrame:
        """获取月线数据"""
        # 标准化股票代码
        stock_code = self.normalize_stock_code(stock_code)
        try:
            result = bs.query_history_k_data_plus(
                stock_code,
                "date,code,open,high,low,close,volume,amount,turn,pctChg",
                start_date=start_date,
                end_date=end_date,
                frequency="m",
                adjustflag=adjustflag
            )
            
            if result.error_code == '0':
                data = result.get_data()
                if not data.empty:
                    numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount', 'turn', 'pctChg']
                    for col in numeric_cols:
                        if col in data.columns:
                            data[col] = pd.to_numeric(data[col], errors='coerce')
                    
                    data = data.rename(columns={
                        'code': '代码',
                        'open': '开盘价',
                        'high': '最高价',
                        'low': '最低价',
                        'close': '收盘价',
                        'volume': '成交量',
                        'amount': '成交额',
                        'turn': '换手率',
                        'pctChg': '涨跌幅',
                        'isST': '是否ST'
                    })
                    
                    # 过滤ST股票（仅当存在该列时）
                    if '是否ST' in data.columns:
                        data = data[data['是否ST'] != 'ST']
                    
                    self.logger.info(f"📅 获取 {stock_code} 月线数据: {len(data)} 条记录")
                    return data
                else:
                    self.logger.warning(f"⚠️ {stock_code} 无月线数据")
                    return pd.DataFrame()
            else:
                self.logger.error(f"❌ 获取 {stock_code} 月线数据失败: {result.error_msg}")
                return pd.DataFrame()
                
        except Exception as e:
            self.logger.error(f"❌ 获取 {stock_code} 月线数据异常: {e}")
            self._relogin_if_network_error(e)  # 网络错误自愈
            return pd.DataFrame()
    
    def get_financial_data(self, stock_code: str, current_price: float = None) -> Dict:
        """
        获取财务数据（ROE/EPS/PE/PB/股息率）
        :param stock_code: 股票代码
        :param current_price: 当前股价（用于计算PE/PB/股息率）
        :return: 财务数据字典
        """
        try:
            # 标准化股票代码
            stock_code = self.normalize_stock_code(stock_code)
            
            financial_data = {
                'ROE': None, 'EPS': None, 'PE': None, 'PB': None,
                '股息率': None, '每股股息': None, '报告期': None
            }
            
            # 获取盈利能力指标（自动查询最新报告期）
            profit_df = pd.DataFrame()
            for year, quarter in [(2026, 1), (2025, 4), (2025, 3)]:
                try:
                    profit_data = bs.query_profit_data(code=stock_code, year=year, quarter=quarter)
                    if profit_data.error_code == '0':
                        tmp_df = profit_data.get_data()
                        if not tmp_df.empty:
                            profit_df = tmp_df
                            break
                except Exception:
                    continue
            
            if not profit_df.empty:
                row = profit_df.iloc[-1]
                financial_data['ROE'] = float(row.get('roeAvg', 0)) if pd.notna(row.get('roeAvg', None)) else None
                financial_data['EPS'] = float(row.get('epsTTM', 0)) if pd.notna(row.get('epsTTM', None)) else None
                financial_data['报告期'] = str(row.get('statDate', ''))
            
            # 获取分红数据（最近年度，计算股息率）
            try:
                dividend_data = bs.query_dividend_data(code=stock_code, year='2025', yearType='report')
                if dividend_data.error_code == '0':
                    dividend_df = dividend_data.get_data()
                    if not dividend_df.empty:
                        # 取最近一次分红
                        div_row = dividend_df.iloc[0]
                        cash_ps = div_row.get('dividCashPsBeforeTax', None)
                        try:
                            financial_data['每股股息'] = float(cash_ps) if pd.notna(cash_ps) else None
                        except (TypeError, ValueError):
                            financial_data['每股股息'] = None
            except Exception:
                pass
            
            # 计算PE/PB/股息率（需要当前股价）
            if current_price and current_price > 0:
                if financial_data['EPS']:
                    financial_data['PE'] = round(current_price / financial_data['EPS'], 2)
                if financial_data['ROE'] and financial_data['EPS']:
                    # PB = 股价 / 每股净资产；每股净资产 = EPS / ROE
                    bps = financial_data['EPS'] / financial_data['ROE'] if financial_data['ROE'] > 0 else None
                    if bps:
                        financial_data['PB'] = round(current_price / bps, 2)
                if financial_data['每股股息']:
                    financial_data['股息率'] = round(financial_data['每股股息'] / current_price * 100, 2)
            
            self.logger.info(f"💹 获取 {stock_code} 财务数据: ROE={financial_data['ROE']}, EPS={financial_data['EPS']}, PE={financial_data['PE']}, PB={financial_data['PB']}")
            return financial_data
            
        except Exception as e:
            self.logger.error(f"❌ 获取 {stock_code} 财务数据异常: {e}")
            return {'ROE': None, 'EPS': None, 'PE': None, 'PB': None, '股息率': None, '每股股息': None, '报告期': None}
    
    def get_industry_data(self) -> pd.DataFrame:
        """获取行业板块数据（baostock query_stock_industry）
        注意: 不能直接用 rs.get_data()——baostock 0.9.3 内部翻页用
        DataFrame.append（pandas 3.0 已移除）→ 多页数据崩溃；
        手动翻页: 先消费当前页（cur_row_num=len(data)）再 rs.next() 请求下一页，
        否则 next() 因当前页未消费恒返回 True 造成死循环；页数上限 8 页防异常
        """
        try:
            rs = bs.query_stock_industry()
            if rs.error_code != '0':
                self.logger.error(f"❌ 获取行业板块数据失败: {rs.error_msg}")
                return pd.DataFrame()
            frames = []
            page = 0
            while rs.error_code == '0' and page < 8:
                if rs.data:
                    frames.append(pd.DataFrame(rs.data, columns=rs.fields))
                page += 1
                rs.cur_row_num = len(rs.data)  # 消费当前页 → next() 走翻页分支
                if not rs.next():
                    break
            if frames:
                df = pd.concat(frames, ignore_index=True)
                self.logger.info(f"🏢 获取到 {len(df)} 个行业板块记录"
                                 f"（{page} 页）")
                return df
            return pd.DataFrame()
        except Exception as e:
            # baostock 部分版本存在兼容性问题，行业数据失败不影响主分析流程
            self.logger.warning(f"⚠️ 获取行业板块数据异常（不影响主分析）: {e}")
            return pd.DataFrame()
    
    def get_index_data(self, index_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取指数数据（用于大盘分析）"""
        # 标准化指数代码（指数也使用 sh.000001 格式）
        index_code = self.normalize_stock_code(index_code)
        try:
            result = bs.query_history_k_data_plus(
                index_code,
                "date,code,open,high,low,close,volume,amount,turn,pctChg",
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag="3"
            )
            
            if result.error_code == '0':
                data = result.get_data()
                if not data.empty:
                    numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount', 'turn', 'pctChg']
                    for col in numeric_cols:
                        if col in data.columns:
                            data[col] = pd.to_numeric(data[col], errors='coerce')
                    
                    data = data.rename(columns={
                        'code': '代码',
                        'open': '开盘价',
                        'high': '最高价',
                        'low': '最低价',
                        'close': '收盘价',
                        'volume': '成交量',
                        'amount': '成交额',
                        'turn': '换手率',
                        'pctChg': '涨跌幅'
                    })
                    
                    self.logger.info(f"📊 获取 {index_code} 指数数据: {len(data)} 条记录")
                    return data
                else:
                    self.logger.warning(f"⚠️ {index_code} 无指数数据")
                    return pd.DataFrame()
            else:
                self.logger.error(f"❌ 获取 {index_code} 指数数据失败: {result.error_msg}")
                return pd.DataFrame()
                
        except Exception as e:
            self.logger.error(f"❌ 获取 {index_code} 指数数据异常: {e}")
            return pd.DataFrame()