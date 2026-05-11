from typing import Dict
from .base import BaseFilter


class ExcludeSTFilter(BaseFilter):
    filter_id = 'exclude_st'
    name = '排除ST股票'
    description = '排除名称包含ST、*ST、SST、S*ST的股票'
    category = 'fundamental'
    filter_stage = 'pre_filter'
    parameters_schema = {}
    
    def evaluate(self, stock_code: str, context: Dict) -> bool:
        stock_name = context.get('stock_name', '')
        
        st_keywords = ['ST', '*ST', 'SST', 'S*ST']
        
        for keyword in st_keywords:
            if keyword in stock_name.upper():
                return False
        
        return True
