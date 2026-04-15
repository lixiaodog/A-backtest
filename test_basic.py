import requests
import json

print('测试: 基本训练功能')
resp = requests.post('http://localhost:5000/api/ml/train', json={
    'stock_code': ['000001', '000002'],
    'market': 'SZ',
    'period': '1d',
    'start_date': '20230101',
    'end_date': '20231231',
    'model_type': 'RandomForest',
    'features': ['ma5', 'ma10'],
    'horizon': 5,
    'threshold': 0.02,
    'label_type': 'fixed',
    'mode': 'classification'
}, timeout=30)

print(f'Status: {resp.status_code}')
result = resp.json()
print(f'Status: {result.get("status")}')
print(f'Stock counts: {result.get("stock_sample_counts")}')
if result.get('status') == 'trained':
    acc = result.get('metrics', {}).get('accuracy', 0)
    print(f'Accuracy: {acc:.2%}')
    print('测试通过!')
else:
    print(f'Error: {result.get("error", "Unknown")}')
