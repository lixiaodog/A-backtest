# 后台 API 自动化测试计划

## 目标
为 `backend/app.py` 的 REST API 和 WebSocket 创建自动化测试。

## 测试框架
**pytest** + requests + python-socketio

## 测试范围

### REST API 测试

| 接口 | 方法 | 测试内容 |
|------|------|----------|
| `/api/strategies` | GET | 返回策略列表 |
| `/api/backtest` | POST | 提交回测任务，返回 task_id |
| `/api/backtest/<task_id>` | GET | 获取指定任务状态和结果 |
| `/api/chart/<filename>` | GET | 访问回测图表图片 |
| `/api/upload` | POST | 上传 CSV 文件 |

### WebSocket 测试

| 事件 | 方向 | 测试内容 |
|------|------|----------|
| `connect` | 服务端→客户端 | 连接成功验证 |
| `backtest_chart` | 服务端→客户端 | 接收实时K线数据 |
| `progress` | 服务端→客户端 | 接收回测进度更新 |

## 实现步骤

1. 创建 `backend/requirements-test.txt`
2. 创建 `backend/test_app.py`，包含：
   - `test_get_strategies()` - 测试策略列表接口
   - `test_submit_backtest()` - 测试提交回测任务
   - `test_get_backtest_result()` - 测试获取回测结果
   - `test_upload_csv()` - 测试文件上传
   - `test_serve_chart()` - 测试图表访问
   - `test_websocket_connect()` - 测试 WebSocket 连接
   - `test_websocket_progress_events()` - 测试 progress 事件推送
3. 运行 `pytest backend/test_app.py` 验证

## 测试方法
- REST API：使用 Flask app test client
- WebSocket：使用 python-socketio client 连接测试
