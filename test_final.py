import requests
import time
import json

print('=' * 50)
print('测试: 多股票训练 + Alpha191 + 进度追踪')
print('=' * 50)

resp = requests.post('http://localhost:5000/api/ml/train', json={
    'stock_code': ['000001', '000002', '000004', '000006', '000007'],
    'market': 'SZ',
    'period': '1d',
    'start_date': '20230101',
    'end_date': '20231231',
    'model_type': 'RandomForest',
    'features': [],  # 空列表 = Alpha191
    'horizon': 5,
    'threshold': 0.02,
    'label_type': 'fixed',
    'mode': 'classification'
}, timeout=120)

print(f'\n请求完成!')
print(f'Status: {resp.status_code}')

try:
    result = resp.json()
    print(f'Task ID: {result.get("task_id")}')
    print(f'Status: {result.get("status")}')

    if result.get('status') == 'trained':
        print(f'\n训练成功!')
        print(f'股票样本: {result.get("stock_sample_counts")}')
        metrics = result.get('metrics', {})
        print(f'准确率: {metrics.get("accuracy", "N/A"):.2%}')
    else:
        print(f'\n响应: {json.dumps(result, indent=2, ensure_ascii=False)[:500]}')
except Exception as e:
    print(f'解析失败: {e}')
    print(f'原始响应: {resp.text[:1000]}')
