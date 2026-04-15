import requests
import time

# 发起训练任务（用更多股票延长训练时间）
resp = requests.post('http://localhost:5000/api/ml/train', json={
    'stock_code': ['000001', '000002', '000004', '000006', '000007', '000008', '000009'],
    'market': 'SZ',
    'period': '1d',
    'start_date': '20230101',
    'end_date': '20231231',
    'model_type': 'RandomForest',
    'features': ['ma5', 'ma10', 'ma20', 'rsi6', 'rsi12'],
    'horizon': 5,
    'threshold': 0.02,
    'label_type': 'fixed',
    'mode': 'classification'
})
result = resp.json()
task_id = result.get('task_id')
print(f'Task ID: {task_id}')

# 立即开始轮询进度
for i in range(20):
    time.sleep(0.5)
    try:
        progress_resp = requests.get(f'http://localhost:5000/api/ml/train/progress/{task_id}', timeout=2)
        p = progress_resp.json()
        print(f'{i*0.5:.1f}s - Progress: {p.get("progress")}% - {p.get("status", "")} - {p.get("message", "")}')
        if p.get('progress') == 100:
            print('Training completed!')
            break
        if p.get('status') == 'unknown':
            print('Task unknown (may have completed too fast)')
            break
    except Exception as e:
        print(f'Error: {e}')
