# Technical因子库计算逻辑说明

## 因子分类

### 📊 真实绝对值因子（需要归一化处理）

这些因子存储的是真实价格值，在不同股票之间量级差异巨大，需要除以收盘价转换为相对值。

#### 1. 移动平均线系列 (MA)

| 因子名 | 当前计算逻辑 | 应改为相对值计算 | 说明 |
|--------|-------------|-----------------|------|
| ma5 | `close.rolling(5).mean()` | `close.rolling(5).mean() / close` | 5日均价相对值 |
| ma10 | `close.rolling(10).mean()` | `close.rolling(10).mean() / close` | 10日均价相对值 |
| ma20 | `close.rolling(20).mean()` | `close.rolling(20).mean() / close` | 20日均价相对值 |
| ma30 | `close.rolling(30).mean()` | `close.rolling(30).mean() / close` | 30日均价相对值 |
| ma60 | `close.rolling(60).mean()` | `close.rolling(60).mean() / close` | 60日均价相对值 |
| ma120 | `close.rolling(120).mean()` | `close.rolling(120).mean() / close` | 120日均价相对值 |
| ma250 | `close.rolling(250).mean()` | `close.rolling(250).mean() / close` | 250日均价相对值 |

**问题**: 
- 贵州茅台 ma20 ≈ 1800元
- 中国银行 ma20 ≈ 4.5元
- 量级差异400倍，归一化后仍会有偏差

**解决方案**: 改为存储 `ma / close`，表示均线相对位置

#### 2. 指数移动平均线系列 (EMA)

| 因子名 | 当前计算逻辑 | 应改为相对值计算 | 说明 |
|--------|-------------|-----------------|------|
| ema12 | `close.ewm(span=12).mean()` | `close.ewm(span=12).mean() / close` | 12日EMA相对值 |
| ema26 | `close.ewm(span=26).mean()` | `close.ewm(span=26).mean() / close` | 26日EMA相对值 |

#### 3. MACD系列

| 因子名 | 当前计算逻辑 | 应改为相对值计算 | 说明 |
|--------|-------------|-----------------|------|
| macd | `ema12 - ema26` | `(ema12 - ema26) / close` | MACD相对值 |
| macd_signal | `macd.ewm(span=9).mean()` | `macd.ewm(span=9).mean() / close` | MACD信号线相对值 |
| macd_diff | `macd - macd_signal` | `(macd - macd_signal) / close` | MACD柱状图相对值 |

**计算步骤**:
```python
ema12 = close.ewm(span=12).mean()
ema26 = close.ewm(span=26).mean()
macd = ema12 - ema26
macd_signal = macd.ewm(span=9).mean()
macd_diff = macd - macd_signal

# 改为相对值
macd_rel = (ema12 - ema26) / close
macd_signal_rel = macd_signal / close
macd_diff_rel = macd_diff / close
```

#### 4. 布林带系列 (Bollinger Bands)

| 因子名 | 当前计算逻辑 | 应改为相对值计算 | 说明 |
|--------|-------------|-----------------|------|
| bollinger_upper | `ma20 + 2*std20` | `(ma20 + 2*std20) / close` | 上轨相对值 |
| bollinger_middle | `ma20` | `ma20 / close` | 中轨相对值 |
| bollinger_lower | `ma20 - 2*std20` | `(ma20 - 2*std20) / close` | 下轨相对值 |

**计算步骤**:
```python
ma20 = close.rolling(window=20).mean()
std20 = close.rolling(window=20).std()

# 改为相对值
bollinger_upper = (ma20 + 2 * std20) / close
bollinger_middle = ma20 / close
bollinger_lower = (ma20 - 2 * std20) / close
```

#### 5. 平均真实波幅 (ATR)

| 因子名 | 当前计算逻辑 | 应改为相对值计算 | 说明 |
|--------|-------------|-----------------|------|
| atr | `tr.rolling(14).mean()` | `tr.rolling(14).mean() / close` | ATR相对值 |

**计算步骤**:
```python
tr1 = high - low
tr2 = abs(high - close.shift())
tr3 = abs(low - close.shift())
tr = max(tr1, tr2, tr3)

# 改为相对值
atr = tr.rolling(window=14).mean() / close
```

---

### ✅ 相对值因子（无需修改）

这些因子已经是相对值或比率，在不同股票之间可直接比较。

#### 6. KDJ系列

| 因子名 | 计算逻辑 | 值范围 | 说明 |
|--------|---------|--------|------|
| kdj_k | `rsv.ewm(com=2).mean()` | 0-100 | K值，已是相对值 |
| kdj_d | `kdj_k.ewm(com=2).mean()` | 0-100 | D值，已是相对值 |
| kdj_j | `3*kdj_k - 2*kdj_d` | 可超范围 | J值，已是相对值 |

**计算步骤**:
```python
low_min = low.rolling(window=9).min()
high_max = high.rolling(window=9).max()
rsv = 100 * (close - low_min) / (high_max - low_min)  # 已经是相对值
kdj_k = rsv.ewm(com=2).mean()
kdj_d = kdj_k.ewm(com=2).mean()
kdj_j = 3 * kdj_k - 2 * kdj_d
```

#### 7. RSI系列

| 因子名 | 计算逻辑 | 值范围 | 说明 |
|--------|---------|--------|------|
| rsi6 | `100 - 100/(1+rs)` | 0-100 | 6日RSI，已是相对值 |
| rsi12 | `100 - 100/(1+rs)` | 0-100 | 12日RSI，已是相对值 |
| rsi24 | `100 - 100/(1+rs)` | 0-100 | 24日RSI，已是相对值 |

**计算步骤**:
```python
delta = close.diff()
gain = delta.where(delta > 0, 0).rolling(window=period).mean()
loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
rs = gain / loss
rsi = 100 - (100 / (1 + rs))  # 已经是相对值
```

#### 8. 成交量比率

| 因子名 | 计算逻辑 | 说明 |
|--------|---------|------|
| volume_ratio | `volume / volume.rolling(5).mean()` | 当前成交量/5日平均成交量，已是相对值 |

#### 9. 收益率系列

| 因子名 | 计算逻辑 | 说明 |
|--------|---------|------|
| return_1d | `close.pct_change(1)` | 1日收益率，已是相对值 |
| return_5d | `close.pct_change(5)` | 5日收益率，已是相对值 |
| return_10d | `close.pct_change(10)` | 10日收益率，已是相对值 |

#### 10. 波动率系列

| 因子名 | 计算逻辑 | 说明 |
|--------|---------|------|
| volatility_5d | `close.pct_change().rolling(5).std()` | 5日波动率，已是相对值 |
| volatility_20d | `close.pct_change().rolling(20).std()` | 20日波动率，已是相对值 |

#### 11. 最高最低价比率

| 因子名 | 计算逻辑 | 说明 |
|--------|---------|------|
| high_low_ratio | `high / low` | 最高价/最低价，已是相对值 |

---

## 📋 因子统计

### 需要修改的因子（真实值 → 相对值）

共 **17个因子** 需要修改：

1. **MA系列** (7个): ma5, ma10, ma20, ma30, ma60, ma120, ma250
2. **EMA系列** (2个): ema12, ema26
3. **MACD系列** (3个): macd, macd_signal, macd_diff
4. **Bollinger系列** (3个): bollinger_upper, bollinger_middle, bollinger_lower
5. **ATR** (1个): atr

### 无需修改的因子（已是相对值）

共 **12个因子** 无需修改：

1. **KDJ系列** (3个): kdj_k, kdj_d, kdj_j
2. **RSI系列** (3个): rsi6, rsi12, rsi24
3. **Volume Ratio** (1个): volume_ratio
4. **Returns系列** (3个): return_1d, return_5d, return_10d
5. **Volatility系列** (2个): volatility_5d, volatility_20d
6. **High-Low Ratio** (1个): high_low_ratio

---

## ⚠️ 修改影响

### 优点
1. **消除量级差异**: 不同价格股票的因子值在同一量级
2. **提高模型效果**: 归一化更有效，模型学习趋势而非价格大小
3. **增强可比性**: 因子值反映相对位置，便于跨股票比较

### 注意事项
1. **需要重新计算缓存**: 修改后需要重新生成所有technical因子缓存
2. **模型需要重新训练**: 使用新的因子值训练模型
3. **向后兼容性**: 旧模型无法使用新因子，需要版本管理

---

## 💡 建议

### 实施方案

1. **修改计算逻辑** (backend/factor_cache/manager.py)
   - 将真实值因子改为除以收盘价
   - 保持相对值因子不变

2. **重新生成缓存**
   - 删除现有technical缓存
   - 重新计算所有股票的technical因子

3. **重新训练模型**
   - 使用新因子训练模型
   - 保存新的归一化参数

### 代码修改位置

文件: `backend/factor_cache/manager.py`
方法: `_compute_technical_indicators`

修改内容:
```python
# 移动平均线 - 改为相对值
for period in [5, 10, 20, 30, 60, 120, 250]:
    data[f'ma{period}'] = close.rolling(window=period).mean() / close

# EMA - 改为相对值
data['ema12'] = close.ewm(span=12).mean() / close
data['ema26'] = close.ewm(span=26).mean() / close

# MACD - 改为相对值
ema12 = close.ewm(span=12).mean()
ema26 = close.ewm(span=26).mean()
macd = (ema12 - ema26) / close
data['macd'] = macd
macd_signal = macd.ewm(span=9).mean()
data['macd_signal'] = macd_signal
data['macd_diff'] = macd - macd_signal

# Bollinger Bands - 改为相对值
ma20 = close.rolling(window=20).mean()
std20 = close.rolling(window=20).std()
data['bollinger_upper'] = (ma20 + 2 * std20) / close
data['bollinger_middle'] = ma20 / close
data['bollinger_lower'] = (ma20 - 2 * std20) / close

# ATR - 改为相对值
tr1 = high - low
tr2 = abs(high - close.shift())
tr3 = abs(low - close.shift())
tr = np.maximum(np.maximum(tr1, tr2), tr3)
data['atr'] = tr.rolling(window=14).mean() / close
```
