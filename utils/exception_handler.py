#!/usr/bin/env python3
# exception_handler.py - 异常处理系统
import logging
import traceback
from datetime import datetime
from typing import Dict, Any, Optional
import os
import sys
from functools import wraps

class StockAnalysisException(Exception):
    """股票分析系统基础异常类"""
    def __init__(self, message: str, error_code: str = "UNKNOWN", details: Dict = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.timestamp = datetime.now()

class DataFetchException(StockAnalysisException):
    """数据获取异常"""
    def __init__(self, message: str, source: str = "baostock"):
        super().__init__(message, "DATA_FETCH", {"source": source})

class IndicatorCalculationException(StockAnalysisException):
    """技术指标计算异常"""
    def __init__(self, message: str, indicator_name: str):
        super().__init__(message, "INDICATOR_CALC", {"indicator_name": indicator_name})

class AnalysisException(StockAnalysisException):
    """分析逻辑异常"""
    def __init__(self, message: str, analysis_type: str):
        super().__init__(message, "ANALYSIS", {"analysis_type": analysis_type})

class OutputGenerationException(StockAnalysisException):
    """输出生成异常"""
    def __init__(self, message: str, output_type: str):
        super().__init__(message, "OUTPUT_GENERATION", {"output_type": output_type})

class ConfigurationException(StockAnalysisException):
    """配置异常"""
    def __init__(self, message: str, config_key: str):
        super().__init__(message, "CONFIG", {"config_key": config_key})

class NetworkException(StockAnalysisException):
    """网络异常"""
    def __init__(self, message: str, url: str = ""):
        super().__init__(message, "NETWORK", {"url": url})

class ResourceException(StockAnalysisException):
    """资源异常"""
    def __init__(self, message: str, resource_type: str):
        super().__init__(message, "RESOURCE", {"resource_type": resource_type})

class ExceptionHandler:
    """异常处理器"""
    
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = log_dir
        self.error_log_path = os.path.join(log_dir, "errors.log")
        self.performance_log_path = os.path.join(log_dir, "performance.log")
        
        # 确保日志目录存在
        os.makedirs(log_dir, exist_ok=True)
        
        # 设置错误日志
        self.error_logger = logging.getLogger("error_handler")
        self.error_logger.setLevel(logging.ERROR)
        
        if not self.error_logger.handlers:
            error_handler = logging.FileHandler(self.error_log_path, encoding='utf-8')
            error_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            self.error_logger.addHandler(error_handler)
        
        # 设置性能日志
        self.performance_logger = logging.getLogger("performance_handler")
        self.performance_logger.setLevel(logging.INFO)
        
        if not self.performance_logger.handlers:
            perf_handler = logging.FileHandler(self.performance_log_path, encoding='utf-8')
            perf_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            self.performance_logger.addHandler(perf_handler)
    
    def handle_exception(self, exception: Exception, context: Dict = None):
        """处理异常"""
        try:
            if isinstance(exception, StockAnalysisException):
                # 处理系统异常
                error_info = {
                    'error_type': type(exception).__name__,
                    'error_code': exception.error_code,
                    'message': exception.message,
                    'details': exception.details,
                    'timestamp': exception.timestamp,
                    'context': context or {}
                }
                
                # 记录错误日志
                self.error_logger.error(
                    f"系统异常: {exception.message} | "
                    f"错误代码: {exception.error_code} | "
                    f"详情: {exception.details} | "
                    f"上下文: {context}"
                )
                
                # 根据异常类型进行特殊处理
                self._handle_specific_exception(exception, context)
                
                return error_info
                
            else:
                # 处理普通异常
                error_info = {
                    'error_type': type(exception).__name__,
                    'message': str(exception),
                    'traceback': traceback.format_exc(),
                    'timestamp': datetime.now(),
                    'context': context or {}
                }
                
                self.error_logger.error(
                    f"未处理异常: {exception} | "
                    f"上下文: {context} | "
                    f"堆栈: {traceback.format_exc()}"
                )
                
                return error_info
                
        except Exception as e:
            # 异常处理过程中发生异常
            critical_error = {
                'error_type': 'CRITICAL_ERROR',
                'message': f"异常处理失败: {e}",
                'original_error': str(exception),
                'timestamp': datetime.now(),
                'context': context or {}
            }
            
            self.error_logger.critical(
                f"异常处理失败: {e} | "
                f"原始异常: {exception} | "
                f"上下文: {context}"
            )
            
            return critical_error
    
    def _handle_specific_exception(self, exception: StockAnalysisException, context: Dict):
        """处理特定类型的异常"""
        if isinstance(exception, DataFetchException):
            self._handle_data_fetch_exception(exception, context)
        elif isinstance(exception, IndicatorCalculationException):
            self._handle_indicator_calculation_exception(exception, context)
        elif isinstance(exception, AnalysisException):
            self._handle_analysis_exception(exception, context)
        elif isinstance(exception, OutputGenerationException):
            self._handle_output_generation_exception(exception, context)
        elif isinstance(exception, ConfigurationException):
            self._handle_configuration_exception(exception, context)
        elif isinstance(exception, NetworkException):
            self._handle_network_exception(exception, context)
        elif isinstance(exception, ResourceException):
            self._handle_resource_exception(exception, context)
    
    def _handle_data_fetch_exception(self, exception: DataFetchException, context: Dict):
        """处理数据获取异常"""
        # 记录数据源状态
        self.error_logger.warning(
            f"数据源异常: {exception.source} | "
            f"建议检查网络连接和数据源状态"
        )
        
        # 如果是baostock异常，尝试切换数据源
        if exception.source == "baostock":
            self.error_logger.info("尝试切换备用数据源...")
    
    def _handle_indicator_calculation_exception(self, exception: IndicatorCalculationException, context: Dict):
        """处理技术指标计算异常"""
        self.error_logger.warning(
            f"技术指标计算异常: {exception.indicator_name} | "
            f"建议检查数据完整性和参数设置"
        )
    
    def _handle_analysis_exception(self, exception: AnalysisException, context: Dict):
        """处理分析逻辑异常"""
        self.error_logger.warning(
            f"分析逻辑异常: {exception.analysis_type} | "
            f"建议检查分析算法和输入数据"
        )
    
    def _handle_output_generation_exception(self, exception: OutputGenerationException, context: Dict):
        """处理输出生成异常"""
        self.error_logger.warning(
            f"输出生成异常: {exception.output_type} | "
            f"建议检查输出格式和文件权限"
        )
    
    def _handle_configuration_exception(self, exception: ConfigurationException, context: Dict):
        """处理配置异常"""
        self.error_logger.warning(
            f"配置异常: {exception.config_key} | "
            f"建议检查配置文件和参数设置"
        )
    
    def _handle_network_exception(self, exception: NetworkException, context: Dict):
        """处理网络异常"""
        self.error_logger.warning(
            f"网络异常: {exception.url} | "
            f"建议检查网络连接和服务器状态"
        )
    
    def _handle_resource_exception(self, exception: ResourceException, context: Dict):
        """处理资源异常"""
        self.error_logger.warning(
            f"资源异常: {exception.resource_type} | "
            f"建议检查系统资源和磁盘空间"
        )
    
    def log_performance(self, operation: str, duration: float, details: Dict = None):
        """记录性能日志"""
        try:
            performance_info = {
                'operation': operation,
                'duration': duration,
                'details': details or {},
                'timestamp': datetime.now()
            }
            
            self.performance_logger.info(
                f"性能日志: {operation} | "
                f"耗时: {duration:.2f}秒 | "
                f"详情: {details}"
            )
            
            return performance_info
            
        except Exception as e:
            self.error_logger.error(f"性能日志记录失败: {e}")
            return None
    
    def get_error_statistics(self) -> Dict:
        """获取错误统计信息"""
        try:
            stats = {
                'total_errors': 0,
                'error_types': {},
                'error_codes': {},
                'recent_errors': []
            }
            
            # 读取错误日志文件
            if os.path.exists(self.error_log_path):
                with open(self.error_log_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    
                stats['total_errors'] = len(lines)
                
                # 分析最近100条错误
                recent_lines = lines[-100:] if len(lines) > 100 else lines
                
                for line in recent_lines:
                    if '系统异常:' in line:
                        # 提取错误类型
                        if '错误代码:' in line:
                            error_code = line.split('错误代码:')[1].split('|')[0].strip()
                            stats['error_codes'][error_code] = stats['error_codes'].get(error_code, 0) + 1
                        
                        # 提取错误类型
                        if '系统异常:' in line:
                            error_type = line.split('系统异常:')[1].split('|')[0].strip()
                            stats['error_types'][error_type] = stats['error_types'].get(error_type, 0) + 1
                
                # 获取最近的错误
                stats['recent_errors'] = recent_lines[-10:] if len(recent_lines) > 10 else recent_lines
            
            return stats
            
        except Exception as e:
            self.error_logger.error(f"获取错误统计失败: {e}")
            return {'error': str(e)}
    
    def clear_old_logs(self, days: int = 30):
        """清理旧的日志文件"""
        try:
            cutoff_time = datetime.now().timestamp() - (days * 24 * 60 * 60)
            
            for log_file in [self.error_log_path, self.performance_log_path]:
                if os.path.exists(log_file):
                    file_time = os.path.getmtime(log_file)
                    if file_time < cutoff_time:
                        os.remove(log_file)
                        self.error_logger.info(f"清理旧日志文件: {log_file}")
            
        except Exception as e:
            self.error_logger.error(f"清理旧日志文件失败: {e}")

def exception_handler(context: Dict = None):
    """异常处理装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except StockAnalysisException as e:
                # 处理系统异常
                handler = ExceptionHandler()
                error_info = handler.handle_exception(e, context)
                raise e
            except Exception as e:
                # 处理普通异常
                handler = ExceptionHandler()
                error_info = handler.handle_exception(e, context)
                raise StockAnalysisException(str(e), "UNKNOWN", context)
        return wrapper
    return decorator

def retry_on_failure(max_retries: int = 3, delay: float = 1.0, exceptions: tuple = (Exception,)):
    """重试装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(delay * (2 ** attempt))  # 指数退避
                    else:
                        raise
            raise last_exception
        return wrapper
    return decorator