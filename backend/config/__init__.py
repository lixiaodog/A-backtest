"""
配置模块

提供统一的配置管理功能
"""
from .data_source_config import DataSourceConfig, get_data_source_config

__all__ = ['DataSourceConfig', 'get_data_source_config']
