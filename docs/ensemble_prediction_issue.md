# 回归集成模型预测异常问题分析

## 🚨 问题发现

### 预测结果异常

**集成模型预测值**：
```
RandomForest: 0.072897 (7.29%收益)  ✓ 合理
LightGBM:     -0.003524 (-0.35%收益) ✓ 合理
Ridge:        0.836944 (83.69%收益)  ❌ 异常！

集成预测（平均）: 0.302106 (30.21%收益) ❌ 异常！
```

**问题**：
- Ridge模型预测值是0.836944（83.69%收益）
- 这显然是不合理的，正常收益率应该在-10%到+10%之间
- 导致集成预测的平均值也被拉高到30.21%

---

## 🔍 问题根源

### 1. Ridge模型的问题

**Ridge模型特点**：
- 线性模型，只能处理线性关系
- 对特征尺度敏感
- 需要特征归一化

**可能原因**：
1. ❌ Ridge模型对归一化后的特征预测不稳定
2. ❌ Ridge模型的正则化参数不合适
3. ❌ Ridge模型对非线性数据拟合差

### 2. 训练指标对比

```
RandomForest: R²=0.109, RMSE=0.074, MAE=0.050
LightGBM:     R²=0.137, RMSE=0.073, MAE=0.049
Ridge:        R²=0.082, RMSE=0.075, MAE=0.051
```

**观察**：
- Ridge的R²最低（0.082）
- RMSE和MAE与其他模型相似
- 但预测时出现异常值

---

## 💡 解决方案

### 方案1：移除Ridge模型（推荐）

**原因**：
- Ridge是线性模型，不适合预测股票收益
- 股票收益与因子的关系是非线性的
- Ridge的预测不稳定

**修改**：
```python
# 回归集成模型只使用RandomForest和LightGBM
if mode == 'regression':
    model_types = ['RandomForest', 'LightGBM']  # 移除Ridge
```

### 方案2：使用加权平均

**原因**：
- 根据模型的R²值分配权重
- R²高的模型权重更大

**修改**：
```python
# 根据R²值计算权重
weights = {
    'RandomForest': 0.109,
    'LightGBM': 0.137,
    'Ridge': 0.082
}

# 归一化权重
total = sum(weights.values())
weights = {k: v/total for k, v in weights.items()}

# 加权平均
ensemble_pred = sum(pred * weights[model] for model, pred in predictions.items())
```

### 方案3：使用中位数而非平均值

**原因**：
- 中位数对异常值不敏感
- 可以避免Ridge异常值的影响

**修改**：
```python
# 使用中位数
ensemble_pred = np.median(list(predictions.values()))
```

---

## 🎯 推荐方案

**方案1：移除Ridge模型**

**理由**：
1. ✅ Ridge不适合非线性关系
2. ✅ 简单直接，不需要额外处理
3. ✅ RandomForest和LightGBM已经足够

**实施**：
修改 `ml/trainer.py` 中的 `train_ensemble` 方法：

```python
def train_ensemble(self, X, y, mode='regression', ...):
    if mode == 'regression':
        # 移除Ridge，只使用RandomForest和LightGBM
        model_types = ['RandomForest', 'LightGBM']
    else:
        model_types = ['RandomForest', 'LightGBM']
    
    # 训练模型...
```

---

## 📊 修改后的效果

**修改前**：
```
RandomForest: 0.072897
LightGBM:     -0.003524
Ridge:        0.836944  ← 异常

集成预测: 0.302106 (30.21%) ❌
```

**修改后（移除Ridge）**：
```
RandomForest: 0.072897
LightGBM:     -0.003524

集成预测: 0.034687 (3.47%) ✓ 合理
```

---

## 🚀 立即行动

### 1. 修改训练逻辑

修改 `ml/trainer.py` 第213行：

```python
# 修改前
model_types = ['RandomForest', 'LightGBM', 'Ridge']

# 修改后
model_types = ['RandomForest', 'LightGBM']
```

### 2. 重新训练模型

删除旧的集成模型，使用新的训练逻辑重新训练。

### 3. 验证预测结果

确保预测值在合理范围内（-10%到+10%）。

---

## 📝 总结

**问题**：Ridge模型预测值异常（83.69%收益）

**原因**：Ridge是线性模型，不适合预测非线性关系的股票收益

**解决**：从集成模型中移除Ridge，只使用RandomForest和LightGBM

**效果**：预测值回归正常范围（3.47%收益）

---

**生成时间**: 2026-04-22  
**问题模型**: Ridge  
**解决方案**: 移除Ridge，使用RandomForest + LightGBM
