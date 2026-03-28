# Backtrader A股回测系统规划

## 项目概述
使用 Backtrader 框架搭建 A 股数据回测系统，支持从免费数据源获取A股数据并进行策略回测。

## 版本兼容性分析
- **AKShare**: 需要 Python 3.8+（推荐 Python 3.11.x 64位）
- **Backtrader**: 支持 Python 2.7 和 3.x
- **结论**: 选用 **Python 3.11** 创建虚拟环境

## 实现步骤

### 1. 环境搭建（首要步骤）
- **检查系统 Python 版本**:
  ```bash
  py --list
  ```
- **创建虚拟环境（使用 Python 3.11）**:
  ```bash
  py -3.11 -m venv venv
  ```
- **激活虚拟环境**:
  ```bash
  .\venv\Scripts\activate
  ```
- **创建 `requirements.txt`** 包含以下依赖：
  - `backtrader` - 回测框架
  - `akshare` - A股免费数据源
  - `pandas` - 数据处理
  - `matplotlib` - 可视化
- **安装依赖**:
  ```bash
  pip install -r requirements.txt
  ```

### 2. 数据获取模块
- 创建 `data_handler.py`
- 使用 akshare 获取 A 股历史数据
- 实现数据格式转换（适配 Backtrader 的 PandasData 格式）
- 支持股票列表、日期范围等参数

### 3. 回测策略模块
- 创建 `strategies/` 目录
- 实现基础策略模板类
- 示例策略：
  - 双均线交叉策略 (SMA Crossover)
  - 简单动量策略
- 包含技术指标计算（MA, RSI, MACD 等）

### 4. 回测引擎配置
- 创建 `backtest_engine.py`
- 配置 A 股券商手续费规则（印花税、过户费、佣金）
- 设置初始资金
- 配置风险参数（止损、止盈）

### 5. 主程序入口
- 创建 `run_backtest.py`
- 整合数据获取、策略选择、回测执行
- 支持命令行参数配置

### 6. 结果分析
- 输出回测绩效指标：
  - 年化收益率
  - 最大回撤
  - 夏普比率
  - 胜率
- 生成回测曲线图

## 文件结构
```
c:\work\backtrader/
├── venv/                  # Python 3.11 虚拟环境
├── requirements.txt
├── data_handler.py      # 数据获取模块
├── backtest_engine.py    # 回测引擎
├── run_backtest.py       # 主程序入口
├── strategies/
│   ├── __init__.py
│   ├── base_strategy.py  # 基础策略模板
│   ├── sma_cross.py      # 双均线策略
│   └── momentum.py       # 动量策略
└── results/              # 回测结果输出目录
```

## 技术说明
- **数据源**: akshare（免费、持续更新、支持A股）
- **交易规则**: 模拟 A 股实际交易规则（ T+1 、涨跌停限制、印花税0.05%、过户费0.002% ）
- **策略类型**: 趋势跟踪、均值回归等基础策略

## 使用方式
```bash
# 激活虚拟环境
.\venv\Scripts\activate

# 运行回测
python run_backtest.py --stock 600519 --start 2020-01-01 --end 2023-12-31 --strategy sma_cross
```

## 执行顺序
1. 检查 Python 版本：`py --list`
2. 创建虚拟环境：`py -3.11 -m venv venv`
3. 激活虚拟环境：`.\venv\Scripts\activate`
4. 安装依赖
5. 创建项目文件
6. 测试运行
