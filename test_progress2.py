import requests
import time

print('发起训练请求 (Alpha191特征，延长训练时间)...')
resp = requests.post('http://localhost:5000/api/ml/train', json={
    'stock_code': ['000001', '000002', '000004', '000006', '000007', '000008', '000009'],
    'market': 'SZ',
    'period': '1d',
    'start_date': '20230101',
    'end_date': '20231231',
    'model_type': 'RandomForest',
    'features': [],  # 空列表 = 使用Alpha191
    'horizon': 5,
    'threshold': 0.02,
    'label_type': 'fixed',
    'mode': 'classification'
}, timeout=120)
result = resp.json()
print(f'响应状态: {result.get("status")}')
task_id = result.get('task_id')
print(f'Task ID: {task_id}')

if result.get('status') == 'trained':
    print('训练已完成（速度太快，进度无法追踪）')
    print(f'股票样本分布: {result.get("stock_sample_counts")}')
else:
    for i in range(20):
        time.sleep(1)
        progress_resp = requests.get(f'http://localhost:5000/api/ml/train/progress/{task_id}')
        p = progress_resp.json()
        print(f'{i+1}s - Progress: {p.get("progress")}% - {p.get("status")} - {p.get("message")}')
        if p.get('progress') == 100:
            print('Training completed!')
            break
