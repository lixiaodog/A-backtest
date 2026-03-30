# Backtrader 回测引擎详解计划

## 目标
详细解释 `backtest_engine.py` 的架构、组件和数据流动。

## 文件结构概览

```
backtest_engine.py (共345行)
├── 第1-13行: 导入和matplotlib配置
├── 第15-44行: RealtimeChartObserver - 实时图表观察者
├── 第46-69行: RealtimeSignalAnalyzer - 实时信号分析器
├── 第71-147行: RealtimeStatsAnalyzer - 实时统计分析器
├── 第149-166行: AStockCommission - A股佣金计算
├── 第168-345行: AStockBacktestEngine - 回测引擎核心类
```

## 详细解释章节

### 1. 环境配置 (第1-13行)
- matplotlib后端设置为'Agg'（无GUI模式）
- 用于在服务器端生成图表图片

### 2. RealtimeChartObserver (第15-44行)
- 继承自 `bt.Observer`
- 功能：每根K线推送实时数据给前端
- 支持暂停/恢复机制
- 通过socketio emit到指定room

### 3. RealtimeSignalAnalyzer (第46-69行)
- 继承自 `bt.Analyzer`
- 功能：监听订单执行事件
- 买卖交易时实时推送信号

### 4. RealtimeStatsAnalyzer (第71-147行)
- 继承自 `bt.Analyzer`
- 功能：定期推送统计数据
- 包含权益曲线、胜率统计、交易列表

### 5. AStockCommission (第149-166行)
- 自定义佣金计算类
- A股手续费：佣金0.03%+印花税0.05%+过户费0.002%

### 6. AStockBacktestEngine (第168-345行)
- 核心回测引擎封装
- 管理Cerebro实例
- 支持暂停/恢复
- 数据分析结果收集
- 图表生成

## 执行方式
直接向用户解释，无需代码修改