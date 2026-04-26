"""
检查训练任务停止功能的问题
"""

## 🚨 问题分析

### 当前实现

**停止任务API**：
```python
@app.route('/api/ml/train/stop/<task_id>', methods=['POST'])
def ml_stop_train(task_id):
    if task_id in training_tasks:
        training_tasks[task_id]['stopped'] = True
        training_tasks[task_id]['status'] = 'stopped'
        training_tasks[task_id]['message'] = '训练任务已停止'
        return jsonify({'status': 'stopping', 'task_id': task_id})
    return jsonify({'status': 'not_found', 'message': '任务不存在'}), 404
```

**问题**：
- ❌ 只是设置了`stopped`标志
- ❌ 训练任务执行过程中**没有检查**这个标志
- ❌ 无法真正停止正在运行的训练任务

---

## 💡 解决方案

### 方案1：在训练过程中检查停止标志（推荐）

在训练任务的关键位置检查`stopped`标志，如果发现被停止，则立即退出。

**修改位置**：
1. `_train_task` 函数开始时检查
2. 数据准备循环中检查
3. 模型训练前检查
4. 集成训练循环中检查

**示例**：
```python
def _train_task(...):
    # 在关键位置检查是否被停止
    if task_id in training_tasks and training_tasks[task_id].get('stopped'):
        _log(f'[训练任务] 任务ID: {task_id} - 任务已被停止')
        return
    
    # 数据准备
    for stock in stock_list:
        # 检查停止标志
        if task_id in training_tasks and training_tasks[task_id].get('stopped'):
            _log(f'[训练任务] 任务ID: {task_id} - 任务已被停止')
            return
        
        # 处理股票数据...
    
    # 训练前检查
    if task_id in training_tasks and training_tasks[task_id].get('stopped'):
        _log(f'[训练任务] 任务ID: {task_id} - 任务已被停止')
        return
    
    # 训练模型...
```

### 方案2：使用线程终止（不推荐）

使用线程的terminate方法强制终止线程，但这种方法不安全，可能导致资源泄漏。

---

## 🎯 推荐实施方案1

### 修改点

1. **在`_train_task`函数开始时检查**
2. **在数据准备循环中检查**
3. **在训练前检查**
4. **在集成训练循环中检查**

### 具体修改

#### 1. 在`_train_task`函数开始时添加检查

```python
def _train_task(task_id, ...):
    # 检查是否被停止
    if task_id in training_tasks and training_tasks[task_id].get('stopped'):
        _log(f'[训练任务] 任务ID: {task_id} - 任务已被停止')
        return
    
    # 原有代码...
```

#### 2. 在数据准备后检查

```python
# 数据准备完成后
if task_id in training_tasks and training_tasks[task_id].get('stopped'):
    _log(f'[训练任务] 任务ID: {task_id} - 任务已被停止')
    return

# 继续训练...
```

#### 3. 在集成训练循环中检查

修改`ml/trainer.py`的`train_ensemble`方法：

```python
def train_ensemble(self, X, y, mode='regression', ...):
    # 添加停止检查回调
    stop_check_callback = kwargs.get('stop_check_callback')
    
    for i, mt in enumerate(model_types, 1):
        # 检查是否被停止
        if stop_check_callback and stop_check_callback():
            self._report_progress('[集成训练] 任务已被停止')
            return None
        
        # 训练模型...
```

---

## 📝 实施步骤

1. **修改`_train_task`函数**
   - 添加停止检查点

2. **修改`train_ensemble`方法**
   - 添加停止检查回调

3. **测试停止功能**
   - 启动训练任务
   - 点击停止按钮
   - 验证任务是否真正停止

---

## 🎯 预期效果

**修改前**：
- 点击停止按钮
- 任务状态变为"stopped"
- 但训练继续运行
- 无法真正停止

**修改后**：
- 点击停止按钮
- 任务状态变为"stopped"
- 训练在下一个检查点停止
- 任务真正停止

---

**生成时间**: 2026-04-22  
**问题**: 训练任务无法停止  
**原因**: 没有检查停止标志  
**解决**: 在关键位置添加停止检查
