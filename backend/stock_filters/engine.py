import json
import os
from typing import List, Dict, Any, Optional
from .models import StockFilter, FilterConfig
from .registry import FilterRegistry
from .storage import FilterStorage


class FilterEngine:
    def __init__(self, storage_path: str = None):
        self.storage = FilterStorage(storage_path)
        self.config: Optional[FilterConfig] = None
        self._stock_info: Dict[str, Dict] = {}
        self._load_config()
        self._load_stock_info()
    
    def _load_config(self):
        """加载配置"""
        self.config = self.storage.load()
    
    def _load_stock_info(self):
        """加载股票信息"""
        stock_info_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'STOCK_INFO.json')
        if os.path.exists(stock_info_path):
            try:
                with open(stock_info_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    content = content.replace(': NaN', ': null')
                    content = content.replace(':NaN', ':null')
                    data = json.loads(content)
                    if isinstance(data, dict):
                        self._stock_info = data
                    elif isinstance(data, list):
                        self._stock_info = {item.get('stock_code', ''): item for item in data}
                print(f"[FilterEngine] 加载股票信息: {len(self._stock_info)} 只")
            except Exception as e:
                print(f"[FilterEngine] 加载股票信息失败: {e}")
    
    def _save_config(self):
        """保存配置"""
        if self.config:
            self.storage.save(self.config)
    
    def reload_config(self):
        """重新加载配置"""
        self._load_config()
        self._load_stock_info()
    
    def get_stock_info(self, stock_code: str) -> Dict:
        """获取股票信息"""
        return self._stock_info.get(stock_code, {})
    
    def get_all_filters(self) -> List[StockFilter]:
        """获取所有条件"""
        if not self.config:
            return []
        return self.config.filters
    
    def get_enabled_filters(self) -> List[StockFilter]:
        """获取启用的条件"""
        if not self.config:
            return []
        return self.config.get_enabled_filters()
    
    def get_pre_filters(self) -> List[StockFilter]:
        """获取预筛选条件"""
        if not self.config:
            return []
        return self.config.get_pre_filters()
    
    def get_post_filters(self) -> List[StockFilter]:
        """获取后筛选条件"""
        if not self.config:
            return []
        return self.config.get_post_filters()
    
    def add_filter(self, stock_filter: StockFilter) -> bool:
        """添加条件"""
        if not self.config:
            self.config = FilterConfig()
        self.config.add_filter(stock_filter)
        self._save_config()
        return True
    
    def update_filter(self, filter_id: str, updates: Dict[str, Any]) -> bool:
        """更新条件"""
        if not self.config:
            return False
        
        stock_filter = self.config.get_filter(filter_id)
        if not stock_filter:
            return False
        
        for key, value in updates.items():
            if hasattr(stock_filter, key):
                setattr(stock_filter, key, value)
        
        self._save_config()
        return True
    
    def remove_filter(self, filter_id: str) -> bool:
        """删除条件"""
        if not self.config:
            return False
        
        self.config.remove_filter(filter_id)
        self._save_config()
        return True
    
    def toggle_filter(self, filter_id: str) -> bool:
        """切换条件启用状态"""
        if not self.config:
            return False
        
        stock_filter = self.config.get_filter(filter_id)
        if not stock_filter:
            return False
        
        stock_filter.enabled = not stock_filter.enabled
        self._save_config()
        return True
    
    def apply_filters(self, stock_list: List[str], market: str = None, period: str = '1d', 
                      predict_date: str = None, data_days: int = 100, data_provider=None) -> List[str]:
        """应用所有筛选条件（模型预测前）
        
        Args:
            stock_list: 股票代码列表
            market: 市场 (SH/SZ)
            period: 周期 (1d)
            predict_date: 预测日期
            data_days: 加载的天数
            data_provider: 数据提供者实例（可选）
            
        Returns:
            筛选后的股票列表
        """
        enabled_filters = self.get_enabled_filters()
        if not enabled_filters:
            return stock_list
        
        if data_provider is None:
            from backend.providers.local_provider import LocalDataProvider
            data_provider = LocalDataProvider(silent=True)
        
        import pandas as pd
        
        result = []
        for stock_code in stock_list:
            stock_info = self.get_stock_info(stock_code)
            
            stock_data = None
            try:
                df = data_provider.get_stock_data(
                    stock_code, 
                    market=market, 
                    period=period,
                    days=data_days,
                    end_date=predict_date
                )
                if df is not None and not df.empty:
                    stock_data = df
            except Exception as e:
                pass
            
            # 检查预测日期是否有数据
            if predict_date and stock_data is not None and not stock_data.empty:
                last_date = stock_data.index[-1]
                predict_dt = pd.to_datetime(predict_date)
                if last_date.date() != predict_dt.date():
                    # 预测日期没有数据，跳过该股票
                    continue
            
            filter_context = {
                'stock_code': stock_code,
                'stock_name': stock_info.get('stock_name', ''),
                'open_date': stock_info.get('open_date'),
                'pre_close': stock_info.get('pre_close'),
                'total_capital': stock_info.get('total_capital'),
                'circulating_capital': stock_info.get('circulating_capital'),
                'market': stock_info.get('market', market),
                'stock_data': stock_data,
                'predict_date': predict_date
            }
            
            passed = True
            for stock_filter in enabled_filters:
                if not self._evaluate_single(stock_code, stock_filter, filter_context):
                    passed = False
                    break
            
            if passed:
                result.append(stock_code)
        
        return result
    
    def apply_pre_filters(self, stock_list: List[str], context: Dict = None) -> List[str]:
        """应用预筛选条件（模型预测前）"""
        pre_filters = self.get_pre_filters()
        if not pre_filters:
            return stock_list
        
        return self._apply_filters(stock_list, pre_filters, context or {})
    
    def apply_post_filters(self, stock_list: List[str], prediction_results: Dict = None, context: Dict = None) -> List[str]:
        """应用后筛选条件（模型预测后）"""
        post_filters = self.get_post_filters()
        if not post_filters:
            return stock_list
        
        ctx = context or {}
        if prediction_results:
            ctx['prediction_results'] = prediction_results
        
        return self._apply_filters(stock_list, post_filters, ctx)
    
    def _apply_filters(self, stock_list: List[str], filters: List[StockFilter], context: Dict) -> List[str]:
        """应用条件筛选股票"""
        result = []
        
        for stock_code in stock_list:
            passed = True
            for stock_filter in filters:
                if not self._evaluate_single(stock_code, stock_filter, context):
                    passed = False
                    break
            
            if passed:
                result.append(stock_code)
        
        return result
    
    def _evaluate_single(self, stock_code: str, stock_filter: StockFilter, context: Dict) -> bool:
        """评估单个股票是否满足条件"""
        filter_impl = FilterRegistry.get_filter(stock_filter.condition_type)
        if not filter_impl:
            print(f"[FilterEngine] 条件类型 {stock_filter.condition_type} 未注册")
            return True
        
        try:
            filter_context = {
                'stock_code': stock_code,
                'parameters': stock_filter.parameters,
                **context
            }
            
            if 'stock_name' not in filter_context and stock_code in self._stock_info:
                stock_info = self._stock_info[stock_code]
                filter_context['stock_name'] = stock_info.get('stock_name', '')
                filter_context['open_date'] = stock_info.get('open_date')
                filter_context['pre_close'] = stock_info.get('pre_close')
                filter_context['total_capital'] = stock_info.get('total_capital')
                filter_context['circulating_capital'] = stock_info.get('circulating_capital')
            
            return filter_impl.evaluate(stock_code, filter_context)
        except Exception as e:
            print(f"[FilterEngine] 评估 {stock_code} 条件 {stock_filter.name} 失败: {e}")
            return True
    
    def preview_filter(self, stock_list: List[str], filter_id: str, context: Dict = None) -> Dict:
        """预览单个条件的筛选效果"""
        stock_filter = self.config.get_filter(filter_id) if self.config else None
        if not stock_filter:
            return {'error': '条件不存在'}
        
        filter_impl = FilterRegistry.get_filter(stock_filter.condition_type)
        if not filter_impl:
            return {'error': f'条件类型 {stock_filter.condition_type} 未注册'}
        
        passed = []
        failed = []
        
        for stock_code in stock_list:
            filter_context = {
                'stock_code': stock_code,
                'parameters': stock_filter.parameters,
                **(context or {})
            }
            
            if 'stock_name' not in filter_context and stock_code in self._stock_info:
                stock_info = self._stock_info[stock_code]
                filter_context['stock_name'] = stock_info.get('stock_name', '')
                filter_context['open_date'] = stock_info.get('open_date')
                filter_context['pre_close'] = stock_info.get('pre_close')
                filter_context['total_capital'] = stock_info.get('total_capital')
                filter_context['circulating_capital'] = stock_info.get('circulating_capital')
            
            try:
                if filter_impl.evaluate(stock_code, filter_context):
                    passed.append(stock_code)
                else:
                    failed.append(stock_code)
            except Exception as e:
                failed.append(stock_code)
        
        return {
            'total': len(stock_list),
            'passed': len(passed),
            'failed': len(failed),
            'passed_stocks': passed[:100],
            'failed_stocks': failed[:100]
        }


_filter_engine: Optional[FilterEngine] = None


def get_filter_engine() -> FilterEngine:
    """获取全局FilterEngine实例"""
    global _filter_engine
    if _filter_engine is None:
        _filter_engine = FilterEngine()
        FilterRegistry.auto_discover()
    return _filter_engine
