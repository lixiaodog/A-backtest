# 集成模型训练详解

## 🎯 集成模型训练方式

**是的，你的理解完全正确！**

集成模型就是使用**同一套训练数据**同时训练多个不同的模型，然后将它们组成一组。

---

## 📊 训练流程

### 1. 数据准备

```python
# 原始数据
X, y  # 特征和标签

# 数据分割
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
```

**说明**：
- 使用同一套数据
- 分割为训练集（80%）和测试集（20%）
- 所有模型使用相同的训练集和测试集

---

### 2. 训练多个模型

#### 回归任务

```python
model_types = ['RandomForest', 'LightGBM', 'Ridge']
models = {}

for model_type in model_types:
    # 使用相同的训练数据训练不同的模型
    models[model_type] = train_model(X_train, y_train, model_type)
```

**训练3个模型**：
- RandomForest回归器
- LightGBM回归器
- Ridge回归器

#### 分类任务

```python
model_types = ['RandomForest', 'LightGBM']
models = {}

for model_type in model_types:
    # 使用相同的训练数据训练不同的模型
    models[model_type] = train_model(X_train, y_train, model_type)
```

**训练2个模型**：
- RandomForest分类器
- LightGBM分类器

---

### 3. 评估模型

```python
# 评估每个模型在训练集和测试集上的性能
train_metrics = {name: evaluate(m, X_train, y_train) for name, m in models.items()}
test_metrics = {name: evaluate(m, X_test, y_test) for name, m in models.items()}
```

**评估指标**：
- 回归：MSE, RMSE, MAE, R²
- 分类：Accuracy, Precision, Recall, F1

---

### 4. 保存模型

```python
# 为每个模型生成唯一ID
parent_id = uuid.uuid4()

# 保存每个子模型
for model_name, model in models.items():
    # 保存模型文件
    filepath = save_model(model, f'{model_name}_{parent_id}.pkl')
    
    # 注册到模型注册表
    registry.register_model(
        model_type=model_name,
        file_path=filepath,
        parent_model_id=parent_id,  # 关联到同一个父ID
        is_ensemble=True
    )
```

**保存方式**：
- 每个模型单独保存为一个文件
- 所有模型共享同一个`parent_model_id`
- 标记为`is_ensemble=True`

---

## 🔍 预测流程

### 1. 加载集成模型

```python
# 通过parent_model_id加载所有子模型
sub_models = registry.get_models_by_parent_id(parent_id)

# 加载所有模型文件
models = {}
for model_info in sub_models:
    model = load_model(model_info['file_path'])
    models[model_info['model_type']] = model
```

### 2. 预测并融合

```python
# 每个模型独立预测
predictions = {}
for name, model in models.items():
    predictions[name] = model.predict(X)

# 融合预测结果
final_prediction = np.mean(list(predictions.values()), axis=0)
```

**融合方式**：
- 回归：取平均值
- 分类：取平均概率，然后选择最大概率的类别

---

## 💡 为什么使用集成模型？

### 优势

1. **提高准确率**
   - 不同模型学习不同的模式
   - 融合后更准确

2. **降低过拟合**
   - 单个模型可能过拟合
   - 多个模型融合降低风险

3. **提高稳定性**
   - 不同模型有不同的优缺点
   - 融合后更稳定

4. **互补性**
   - RandomForest：稳定性好
   - LightGBM：准确率高
   - Ridge：线性关系

### 示例

**单个模型预测**：
```
RandomForest: 0.05 (5%收益)
LightGBM:      0.03 (3%收益)
Ridge:         0.04 (4%收益)
```

**集成预测**：
```
平均: (0.05 + 0.03 + 0.04) / 3 = 0.04 (4%收益)
```

---

## 📋 集成模型 vs 单个模型

| 特性 | 单个模型 | 集成模型 |
|------|---------|---------|
| **训练时间** | 快 | 慢（多个模型） |
| **预测时间** | 快 | 慢（多个预测） |
| **准确率** | 中等 | 高 |
| **稳定性** | 中等 | 高 |
| **过拟合风险** | 高 | 低 |
| **存储空间** | 小 | 大（多个文件） |

---

## 🎯 使用建议

### 何时使用集成模型？

✅ **推荐使用**：
- 追求最高准确率
- 数据量充足
- 计算资源充足
- 生产环境部署

❌ **不推荐使用**：
- 快速原型开发
- 计算资源有限
- 实时性要求高
- 存储空间有限

---

## 📊 实际示例

### 训练集成模型

```python
# API调用
POST /api/ml/train
{
    "stocks": ["000001", "600519"],
    "model_type": "RandomForest",  # 基础模型类型
    "mode": "regression",
    "use_ensemble": true  # 启用集成训练
}
```

### 训练过程

```
[集成训练] 开始集成训练，模式: regression
[集成训练] 样本数: 5000, 特征数: 220
[集成训练] 数据分割完成，训练集: 4000, 测试集: 1000
[集成训练] 训练第 1/3 个模型: RandomForest
[集成训练] 训练第 2/3 个模型: LightGBM
[集成训练] 训练第 3/3 个模型: Ridge
[集成训练] 开始评估模型...
[集成训练] RandomForest 测试集 R²: 0.0850, RMSE: 0.0234
[集成训练] LightGBM 测试集 R²: 0.0920, RMSE: 0.0228
[集成训练] Ridge 测试集 R²: 0.0500, RMSE: 0.0250
[集成训练] 完成，总耗时 45.23秒
```

### 预测结果

```python
# 单个模型预测
RandomForest预测: 买入信号，置信度 0.65
LightGBM预测:     买入信号，置信度 0.70
Ridge预测:        持有信号，置信度 0.55

# 集成预测
平均置信度: (0.65 + 0.70 + 0.55) / 3 = 0.63
最终信号: 买入（2票买入，1票持有）
```

---

## 🎉 总结

**集成模型训练方式**：
1. ✅ 使用同一套训练数据
2. ✅ 同时训练多个不同的模型
3. ✅ 每个模型独立保存
4. ✅ 预测时融合所有模型的结果

**优势**：
- 提高准确率
- 降低过拟合
- 提高稳定性

**代价**：
- 训练时间更长
- 预测时间更长
- 存储空间更大

---

**生成时间**: 2026-04-22  
**适用场景**: 集成模型训练  
**核心原理**: 同一数据训练多个模型，融合预测结果
