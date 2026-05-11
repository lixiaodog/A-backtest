from typing import Dict
from .base import BaseFilter
from datetime import datetime


class ExcludeNewStockFilter(BaseFilter):
    filter_id = 'exclude_new_stock'
    name = '排除新股'
    description = '排除上市不足指定天数的股票'
    category = 'fundamental'
    filter_stage = 'pre_filter'
    parameters_schema = {
        'type': 'object',
        'properties': {
            'min_listing_days': {
                'type': 'integer',
                'default': 365,
                'title': '最小上市天数',
                'minimum': 30,
                'maximum': 730
            }
        }
    }
    
    def evaluate(self, stock_code: str, context: Dict) -> bool:
        open_date = context.get('open_date')
        
        if open_date is None:
            return True
        
        parameters = context.get('parameters', {})
        min_days = parameters.get('min_listing_days', 365)
        
        try:
            if isinstance(open_date, str):
                listing_date = datetime.strptime(open_date, '%Y%m%d')
            elif isinstance(open_date, int):
                listing_date = datetime.strptime(str(open_date), '%Y%m%d')
            else:
                return True
            
            days_listed = (datetime.now() - listing_date).days
            
            return days_listed >= min_days
        except Exception as e:
            print(f"[ExcludeNewStockFilter] 评估 {stock_code} 失败: {e}")
            return True
