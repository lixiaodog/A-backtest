import requests

print('测试: Alpha191特征训练')
resp = requests.post('http://localhost:5000/api/ml/train', json={
    'stock_code': ['000001', '000002', '000004'],
    'market': 'SZ',
    'period': '1d',
    'start_date': '20230101',
    'end_date': '20231231',
    'model_type': 'RandomForest',
    'features': [],
    'horizon': 5,
    'threshold': 0.02,
    'label_type': 'fixed',
    'mode': 'classification'
}, timeout=60)

print(f'Status: {resp.status_code}')
print(f'Content type: {resp.headers.get("Content-Type")}')
print(f'Response length: {len(resp.text)}')
print(f'Response: {resp.text[:1500]}')
