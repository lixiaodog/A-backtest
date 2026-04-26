# 波动率训练问题分析报告

## 🚨 严重问题发现

经过测试，发现波动率训练存在**严重的标签分布不均衡问题**！

## 📊 测试结果

### 标签分布极度不均衡

```
标签 0.0: 133 (66.50%)  ← 下跌
标签 1.0: 13 (6.50%)   ← 持平（极少！）
标签 2.0: 49 (24.50%)  ← 上涨

最大/最小比例: 10.23倍
```

**问题严重性**：
- 标签1只有6.5%的样本
- 标签0占了66.5%
- 严重的类别不平衡，会导致模型偏向预测标签0

## 🔍 问题根源

### 当前实现的逻辑

```python
def generate_labels_by_volatility(self, df, horizon=5, vol_window=20, lower_q=0.2, upper_q=0.8):
    future_returns = df['close'].shift(-horizon) / df['close'] - 1
    returns = df['close'].pct_change()
    
    # 计算波动率
    rolling_vol = returns.rolling(window=vol_window).std()
    vol_rolling = rolling_vol.rolling(window=vol_window).mean()
    
    # 使用波动率的分位数作为阈值
    lower_threshold = vol_rolling.quantile(lower_q)  # 0.006846
    upper_threshold = vol_rolling.quantile(upper_q)  # 0.010373
    
    # 根据未来收益率与阈值的关系生成标签
    labels[future_returns < lower_threshold] = 0
    labels[(future_returns >= lower_threshold) & (future_returns <= upper_threshold)] = 1
    labels[future_returns > upper_threshold] = 2
```

### 问题分析

**阈值 vs 未来收益率范围**：
```
波动率阈值:
  - 下限: 0.006846 (0.68%)
  - 上限: 0.010373 (1.04%)

未来收益率范围:
  - 最小: -0.045082 (-4.51%)
  - 最大: 0.066942 (6.69%)
```

**问题**：
1. ❌ 使用**波动率的分位数**作为阈值，而不是**未来收益率的分位数**
2. ❌ 波动率阈值（0.68%-1.04%）与未来收益率范围（-4.51%-6.69%）不匹配
3. ❌ 大部分未来收益率（<0.68%）被标记为标签0
4. ❌ 只有很少的未来收益率（0.68%-1.04%）被标记为标签1

## 💡 正确的实现

### 方案1：使用未来收益率的分位数（推荐）

```python
def generate_labels_by_volatility_corrected(self, df, horizon=5, vol_window=20, lower_q=0.2, upper_q=0.8):
    future_returns = df['close'].shift(-horizon) / df['close'] - 1
    
    # 使用未来收益率的分位数作为阈值
    lower_threshold = future_returns.quantile(lower_q)
    upper_threshold = future_returns.quantile(upper_q)
    
    labels = pd.Series(index=future_returns.index, dtype=int)
    labels[future_returns < lower_threshold] = 0
    labels[(future_returns >= lower_threshold) & (future_returns <= upper_threshold)] = 1
    labels[future_returns > upper_threshold] = 2
    
    return labels
```

**优点**：
- ✅ 标签分布均衡（20%-60%-20%）
- ✅ 阈值与未来收益率匹配
- ✅ 更符合实际交易逻辑

### 方案2：使用波动率调整阈值

```python
def generate_labels_by_volatility_adjusted(self, df, horizon=5, vol_window=20, lower_q=0.2, upper_q=0.8):
    future_returns = df['close'].shift(-horizon) / df['close'] - 1
    returns = df['close'].pct_change()
    
    # 计算波动率
    rolling_vol = returns.rolling(window=vol_window).std()
    vol_rolling = rolling_vol.rolling(window=vol_window).mean()
    
    # 使用波动率调整阈值
    # 例如：阈值 = 均值 ± k * 波动率
    mean_return = future_returns.mean()
    lower_threshold = mean_return - vol_rolling
    upper_threshold = mean_return + vol_rolling
    
    labels = pd.Series(index=future_returns.index, dtype=int)
    labels[future_returns < lower_threshold] = 0
    labels[(future_returns >= lower_threshold) & (future_returns <= upper_threshold)] = 1
    labels[future_returns > upper_threshold] = 2
    
    return labels
```

## 📋 影响分析

### 对模型训练的影响

**当前问题会导致**：
1. ❌ 模型偏向预测标签0（占66.5%）
2. ❌ 对标签1的预测能力极差（只有6.5%样本）
3. ❌ 模型准确率虚高（预测全为0就有66.5%准确率）
4. ❌ 实际交易效果差

**示例**：
```python
# 如果模型总是预测标签0
预测准确率 = 66.5%  # 看起来不错

# 但实际上
对标签1的召回率 = 0%  # 完全无法识别持平
对标签2的召回率 = 0%  # 完全无法识别上涨
```

## 🎯 建议

### 立即行动

1. **修改标签生成逻辑**
   - 使用未来收益率的分位数，而不是波动率的分位数
   - 确保标签分布均衡

2. **重新训练模型**
   - 使用修正后的标签生成逻辑
   - 删除旧的波动率模型

3. **验证标签分布**
   - 训练前检查标签分布
   - 确保各类别比例合理

### 长期改进

1. **添加标签分布检查**
   - 在训练前自动检查标签分布
   - 如果不均衡，发出警告

2. **支持类别权重**
   - 对不均衡的标签使用类别权重
   - 提高少数类别的权重

3. **文档说明**
   - 明确说明波动率标签的含义
   - 提供正确的使用示例

## 📝 总结

**问题严重性**: 🔴 高 - 影响模型训练效果

**根本原因**: 使用波动率的分位数作为阈值，而不是未来收益率的分位数

**解决方案**: 修改标签生成逻辑，使用未来收益率的分位数

**影响范围**: 所有使用波动率标签训练的模型

---

**生成时间**: 2026-04-21  
**测试股票**: 000001  
**标签分布**: 极度不均衡（10.23倍差异）
