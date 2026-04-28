"""
自定义策略模板

策略名称: 自定义策略
策略描述: 用于创建新的自定义交易策略，基于传入的指标和参数进行交易。

参数说明:
- 使用此模板创建新策略时，请继承此框架并根据需要修改参数和交易逻辑

使用说明:
1. 复制此模板并重命名类名
2. 在params中定义策略参数，格式: ('参数名', 默认值, '参数描述', 类型)
3. 在__init__中初始化所需的技术指标
4. 在next()中实现交易逻辑
5. 在strategy_metadata.json中注册策略元数据

注意事项:
- 所有参数都应有明确的描述和合理的取值范围
- 交易逻辑应处理无持仓和有持仓两种状态
- 使用self.order避免重复下单
- 使用self.log()记录交易信号
"""

import backtrader as bt
from backend.strategies.base_strategy import BaseStrategy

class CustomStrategy(BaseStrategy):
    """
    自定义策略框架 - 创建新策略时请基于此模板
    """
    params = (
        # 示例参数，实际使用时替换
        ('period', 14, '指标计算周期', int),
        ('threshold', 30, '信号阈值', float),
        ('printlog', False),
    )

    name = '自定义策略'
    description = '请修改策略描述'

    def __init__(self):
        """初始化策略指标"""
        super().__init__()
        # 在此初始化技术指标，例如:
        # self.indicator = bt.indicators.XXX(self.datas[0].close, period=self.params.period)

    def next(self):
        """每个bar执行一次交易逻辑"""
        if self.order:
            return

        # 在此实现交易逻辑
        # 示例:
        # if not self.position:
        #     if self.indicator < self.params.threshold:
        #         self.order = self.buy()
        # else:
        #     if self.indicator > self.params.threshold:
        #         self.order = self.sell()
        pass
