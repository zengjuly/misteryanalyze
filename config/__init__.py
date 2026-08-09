# config package
import yaml
import os

def load_config(config_path: str = "config/config.yaml") -> dict:
    """加载配置文件"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config
    except FileNotFoundError:
        # 如果配置文件不存在，返回默认配置
        return get_default_config()
    except Exception as e:
        print(f"加载配置文件异常: {e}")
        return get_default_config()

def get_default_config() -> dict:
    """获取默认配置"""
    return {
        'output_dir': 'output',
        'log_level': 'INFO',
        'stocks': [],
        'industries': [],
        'market_indices': ['sh000001', 'sz399001', 'sz399006'],
        'indicators': {
            'ma_periods': [5, 10, 20, 60, 250],
            'ema_periods': [12, 26]
        },
        'mystery': {
            'min_price': 5.0,
            'max_price': 1000.0,
            'min_volume': 1000000,
            'max_turnover_ratio': 0.15
        },
        'risk_control': {
            'stop_loss': {
                'enabled': True,
                'percentage': 0.08
            }
        }
    }

def save_config(config: dict, config_path: str = "config/config.yaml"):
    """保存配置文件"""
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        return True
    except Exception as e:
        print(f"保存配置文件异常: {e}")
        return False