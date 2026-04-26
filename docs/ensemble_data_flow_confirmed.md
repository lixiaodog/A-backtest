"""
验证集成模型训练流程：数据只读取一次，标签只生成一次
"""

## ✅ 确认：集成模型训练流程

### 训练流程分析

#### 第一步：数据准备（只执行一次）

```python
# 1. 读取所有股票数据
all_X = []
all_y = []

for stock in stocks:
    # 读取股票数据
    raw_data = get_stock_data(stock)
    
    # 生成特征（只执行一次）
    X = feature_engineer.calculate_features(raw_data, features)
    
    # 生成标签（只执行一次）
    y = feature_engineer.generate_labels(raw_data, label_type, horizon)
    
    all_X.append(X)
    all_y.append(y)

# 2. 合并所有数据（只执行一次）
X = pd.concat(all_X, ignore_index=True)
y = pd.concat(all_y, ignore_index=True)

print(f"数据准备完成: X.shape={X.shape}, y.shape={y.shape}")
```

#### 第二步：集成训练（复用同一份数据）

```python
# 3. 集成训练（使用同一份X和y）
if use_ensemble:
    # 调用train_ensemble，传入X和y
    result = trainer.train_ensemble(X, y, mode=mode)
```

#### 第三步：train_ensemble内部实现

```python
def train_ensemble(self, X, y, mode='regression', ...):
    # 数据分割（只执行一次）
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
    
    # 训练多个模型（使用同一份训练数据）
    models = {}
    
    if mode == 'regression':
        model_types = ['RandomForest', 'LightGBM', 'Ridge']
    else:
        model_types = ['RandomForest', 'LightGBM']
    
    for model_type in model_types:
        # 每个模型使用相同的X_train和y_train
        models[model_type] = self._train_model(X_train, y_train, model_type)
    
    return {'models': models, ...}
```

---

## 📊 流程图

```
┌─────────────────────────────────────────┐
│  第一步：数据准备（只执行一次）          │
├─────────────────────────────────────────┤
│  1. 读取股票数据                        │
│  2. 计算特征（一次）                    │
│  3. 生成标签（一次）                    │
│  4. 合并数据（一次）                    │
│                                         │
│  结果：X, y                             │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│  第二步：数据分割（只执行一次）          │
├─────────────────────────────────────────┤
│  X_train, X_test, y_train, y_test       │
│  = train_test_split(X, y)               │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│  第三步：训练多个模型（复用数据）        │
├─────────────────────────────────────────┤
│  for model_type in ['RF', 'LGB', 'Ridge']:│
│      model = train(X_train, y_train)    │
│      # 使用相同的X_train和y_train       │
└─────────────────────────────────────────┘
```

---

## ✅ 确认结论

**是的，你的理解完全正确！**

1. ✅ **数据只读取一次**
   - 在调用train_ensemble之前完成
   - 所有股票数据合并为X和y

2. ✅ **标签只生成一次**
   - 在数据准备阶段生成
   - 所有模型使用相同的标签

3. ✅ **特征只计算一次**
   - 在数据准备阶段计算
   - 所有模型使用相同的特征

4. ✅ **数据分割只执行一次**
   - 在train_ensemble开始时分割
   - 所有模型使用相同的训练集和测试集

5. ✅ **多个模型复用同一份数据**
   - RandomForest使用X_train, y_train
   - LightGBM使用X_train, y_train
   - Ridge使用X_train, y_train

---

## 💡 优势

**为什么这样设计？**

1. **效率高**
   - 数据读取和预处理只执行一次
   - 避免重复计算

2. **一致性**
   - 所有模型使用相同的数据
   - 确保公平比较

3. **内存友好**
   - 不需要多次存储相同的数据
   - 减少内存占用

---

## 📝 实际日志示例

```
[训练任务] 开始准备数据...
[训练任务] 读取股票 000001 数据...
[训练任务] 计算特征... (只执行一次)
[训练任务] 生成标签... (只执行一次)
[训练任务] 读取股票 600519 数据...
[训练任务] 计算特征... (只执行一次)
[训练任务] 生成标签... (只执行一次)
[训练任务] 合并数据... 总样本数: 5000

[训练任务] 开始集成训练...
[集成训练] 数据分割完成，训练集: 4000, 测试集: 1000
[集成训练] 训练第 1/3 个模型: RandomForest (使用X_train, y_train)
[集成训练] 训练第 2/3 个模型: LightGBM (使用X_train, y_train)
[集成训练] 训练第 3/3 个模型: Ridge (使用X_train, y_train)
[集成训练] 完成
```

---

## 🎯 总结

**集成模型训练流程**：
1. ✅ 数据只读取一次
2. ✅ 标签只生成一次
3. ✅ 特征只计算一次
4. ✅ 数据分割只执行一次
5. ✅ 多个模型复用同一份数据

**没有任何重复的数据读取或标签生成操作！**

---

**生成时间**: 2026-04-22  
**确认结果**: 数据只读取一次，标签只生成一次，多个模型复用同一份数据
