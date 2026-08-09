# utils package
import logging
import os
from datetime import datetime

def setup_logging(log_dir: str = "logs", log_level: str = "INFO"):
    """设置日志系统"""
    # 创建日志目录
    os.makedirs(log_dir, exist_ok=True)
    
    # 设置日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 文件处理器
    log_file = os.path.join(log_dir, f'stock_analysis_{datetime.now().strftime("%Y%m%d")}.log')
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(getattr(logging, log_level.upper()))
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    
    # 配置根日志记录器
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        handlers=[file_handler, console_handler]
    )

def ensure_directory(path: str):
    """确保目录存在"""
    os.makedirs(path, exist_ok=True)

def format_number(number: float, decimal_places: int = 2) -> str:
    """格式化数字"""
    if number is None:
        return "N/A"
    return f"{number:.{decimal_places}f}"

def format_percentage(number: float, decimal_places: int = 2) -> str:
    """格式化百分比"""
    if number is None:
        return "N/A"
    return f"{number:.{decimal_places}%}"

def safe_division(numerator: float, denominator: float, default: float = 0.0) -> float:
    """安全除法"""
    if denominator == 0:
        return default
    return numerator / denominator

def build_report_filename(analysis_results: dict, report_type: str = "股票分析报告",
                          ext: str = ".xlsx") -> str:
    """
    构建报告文件名
    规则：
    - 单只股票：{report_type}_{股票名称}_{时间戳}.{ext}
    - 多只股票（每日分析）：每日{report_type}_{时间戳}.{ext}
    :param analysis_results: 分析结果字典
    :param report_type: 报告类型前缀（如"股票分析报告"）
    :param ext: 文件扩展名（含点）
    :return: 文件名
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if len(analysis_results) == 1:
        # 单只股票：取股票名称
        stock_name = "个股"
        for result in analysis_results.values():
            if isinstance(result, dict):
                name = result.get('股票名称', '')
                if name and name != '未知':
                    stock_name = str(name)
                break
        return f"{report_type}_{stock_name}_{timestamp}{ext}"
    else:
        # 多只股票：每日分析
        return f"每日{report_type}_{timestamp}{ext}"