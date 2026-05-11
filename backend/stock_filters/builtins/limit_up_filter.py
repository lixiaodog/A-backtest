"""
涨停筛选器
"""
from typing import Dict
from .base import BaseFilter


class LimitUpFilter(BaseFilter):
    """涨停筛选器
    
    筛选当日涨停的股票，根据股票代码自动判断涨停幅度
    """
    
    filter_id = 'limit_up'
    name = "涨停筛选"
    description = "筛选当日涨停的股票，自动识别主板/创业板/科创板/北交所"
    category = "技术指标"
    
    parameters_schema = {
        "type": "object",
        "properties": {
            "filter_mode": {
                "type": "string",
                "title": "筛选模式",
                "description": "选择保留还是排除涨停/跌停股票",
                "enum": ["符合", "排除"],
                "default": "符合"
            },
            "limit_type": {
                "type": "string",
                "title": "涨停类型",
                "description": "选择涨停或跌停",
                "enum": ["涨停", "跌停", "不限制"],
                "default": "涨停"
            },
            "tolerance": {
                "type": "number",
                "title": "容差范围(%)",
                "description": "由于价格最小单位是分，实际涨幅可能有偏差，设置容差范围",
                "default": 0.1,
                "minimum": 0,
                "maximum": 1
            }
        },
        "required": ["filter_mode", "limit_type"]
    }
    
    def _get_limit_pct(self, stock_code: str) -> float:
        """根据股票代码获取涨跌幅限制
        
        Args:
            stock_code: 股票代码
            
        Returns:
            涨跌幅限制百分比
        """
        code = str(stock_code)
        
        # 北交所：8、4开头，涨跌幅30%
        if code.startswith(('8', '4')):
            return 30.0
        
        # 科创板：688开头，涨跌幅20%
        if code.startswith('688'):
            return 20.0
        
        # 创业板：300开头，涨跌幅20%
        if code.startswith('300'):
            return 20.0
        
        # 主板：60、00开头，涨跌幅10%
        # ST股票：涨跌幅5%（需要从股票名称判断）
        return 10.0
    
    def evaluate(self, stock_code: str, context: Dict) -> bool:
        """评估股票是否满足条件
        
        Args:
            stock_code: 股票代码
            context: 上下文信息，包含stock_data等
            
        Returns:
            是否满足筛选条件
        """
        stock_data = context.get('stock_data')
        if stock_data is None:
            return True
        
        parameters = context.get('parameters', {})
        filter_mode = parameters.get('filter_mode', '符合')
        limit_type = parameters.get('limit_type', '涨停')
        tolerance = parameters.get('tolerance', 0.1)
        
        if limit_type == "不限制":
            return True
        
        try:
            if len(stock_data) < 2:
                return False
            
            latest = stock_data.iloc[-1]
            prev = stock_data.iloc[-2]
            
            close = latest.get('close')
            prev_close = prev.get('close')
            stock_name = context.get('stock_name', '')
            
            if close is None or prev_close is None or prev_close == 0:
                return True
            
            change_pct = (close - prev_close) / prev_close * 100
            
            # 获取涨跌幅限制
            limit_pct = self._get_limit_pct(stock_code)
            
            # 判断是否是ST股票
            if 'ST' in stock_name or '*ST' in stock_name:
                # 主板ST股票涨跌幅5%，创业板/科创板ST股票仍为20%
                if not (stock_code.startswith('300') or stock_code.startswith('688')):
                    limit_pct = 5.0
            
            # 判断是否涨停/跌停
            is_limit_hit = False
            if limit_type == "涨停":
                # 涨停：涨幅接近涨停幅度（考虑容差）
                is_limit_hit = abs(change_pct - limit_pct) <= tolerance
            elif limit_type == "跌停":
                # 跌停：跌幅接近跌停幅度（考虑容差）
                is_limit_hit = abs(change_pct + limit_pct) <= tolerance
            
            # 根据筛选模式返回结果
            if filter_mode == "符合":
                # 符合：保留涨停/跌停的股票
                return is_limit_hit
            else:  # 排除
                # 排除：排除涨停/跌停的股票
                return not is_limit_hit
                
        except Exception as e:
            print(f"[LimitUpFilter] 评估 {stock_code} 失败: {e}")
            return True
