import pytest
import sys
import os
import time
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import app

class TestMLTrainAPI:
    @pytest.fixture
    def client(self):
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client

    def test_train_single_stock(self, client):
        print("\n[测试] 测试单只股票训练...")
        payload = {
            'stock_code': '000001',
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
        }
        response = client.post('/api/ml/train', json=payload)
        assert response.status_code == 200, f"请求失败: {response.status_code}, {response.data}"
        data = response.get_json()

        print(f"[测试] 响应: {data}")
        assert data['status'] == 'trained', f"训练失败: {data}"
        assert 'model' in data or 'metrics' in data
        print("[测试] 单只股票训练测试通过!")

    def test_train_multiple_stocks_one_by_one(self, client):
        print("\n[测试] 测试多只股票按顺序训练同一模型...")
        stock_list = ['000001', '000002', '000004']
        payload = {
            'stock_code': stock_list,
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
        }
        response = client.post('/api/ml/train', json=payload)
        assert response.status_code == 200, f"请求失败: {response.status_code}, {response.data}"
        data = response.get_json()

        print(f"[测试] 响应: {data}")
        assert data['status'] == 'trained', f"训练失败: {data}"
        assert 'stock_sample_counts' in data, "缺少 stock_sample_counts 字段"
        assert len(data['stock_sample_counts']) == len(stock_list), \
            f"股票样本分布数量不符: 期望{len(stock_list)}, 实际{len(data['stock_sample_counts'])}"

        total_samples = sum(data['stock_sample_counts'].values())
        print(f"[测试] 各股票样本分布: {data['stock_sample_counts']}, 总样本: {total_samples}")
        assert total_samples > 0, "总样本数为0"

        if 'model' in data:
            model_info = data['model']
            assert 'RandomForest' in model_info.get('model_name', '') or 'unified' in model_info.get('model_name', ''), \
                f"模型名称不符合预期: {model_info.get('model_name')}"
            print(f"[测试] 模型名称: {model_info.get('model_name')}")

        print("[测试] 多只股票按顺序训练测试通过!")

    def test_train_multiple_stocks_progress_tracking(self, client):
        print("\n[测试] 测试多只股票训练进度跟踪...")
        stock_list = ['000001', '000002', '000004', '000006', '000007']
        payload = {
            'stock_code': stock_list,
            'market': 'SZ',
            'period': '1d',
            'start_date': '20230101',
            'end_date': '20231231',
            'model_type': 'RandomForest',
            'features': ['ma5', 'ma10', 'rsi6'],
            'horizon': 5,
            'threshold': 0.02,
            'label_type': 'fixed',
            'mode': 'classification'
        }

        print("[测试] 提交训练任务...")
        response = client.post('/api/ml/train', json=payload)
        assert response.status_code == 200, f"请求失败: {response.status_code}"
        data = response.get_json()
        task_id = data.get('task_id')

        print(f"[测试] 任务ID: {task_id}")
        assert task_id is not None, "缺少 task_id"

        print("[测试] 检查训练进度...")
        max_retries = 30
        for i in range(max_retries):
            time.sleep(2)
            progress_response = client.get(f'/api/ml/train/progress/{task_id}')
            progress_data = progress_response.get_json()
            print(f"[测试] 进度: {progress_data.get('progress')}% - {progress_data.get('status')} - {progress_data.get('message')}")

            if progress_data.get('progress') == 100 or progress_data.get('status') == '完成':
                print("[测试] 训练完成!")
                break

            if progress_data.get('status') == 'unknown':
                print("[测试] 任务已过期或不存在")
                break

        final_response = client.get(f'/api/ml/train/progress/{task_id}')
        final_data = final_response.get_json()
        print(f"[测试] 最终状态: {final_data}")

        if final_data.get('status') not in ['完成', 'completed', 'unknown']:
            print(f"[测试] 警告: 任务可能未完成，最终状态: {final_data}")

        print("[测试] 进度跟踪测试完成!")

    def test_train_stocks_skip_invalid(self, client):
        print("\n[测试] 测试跳过无效股票...")
        stock_list = ['000001', 'INVALID_STOCK', '000002', '999999']
        valid_stocks = ['000001', '000002']
        payload = {
            'stock_code': stock_list,
            'market': 'SZ',
            'period': '1d',
            'start_date': '20230101',
            'end_date': '20231231',
            'model_type': 'RandomForest',
            'features': ['ma5', 'ma10', 'rsi6'],
            'horizon': 5,
            'threshold': 0.02,
            'label_type': 'fixed',
            'mode': 'classification'
        }
        response = client.post('/api/ml/train', json=payload)
        assert response.status_code == 200, f"请求失败: {response.status_code}"
        data = response.get_json()

        print(f"[测试] 响应: {data}")
        assert data['status'] == 'trained', f"训练失败: {data}"
        assert 'stock_sample_counts' in data
        trained_stocks = list(data['stock_sample_counts'].keys())
        print(f"[测试] 成功训练的股票: {trained_stocks}")
        assert len(trained_stocks) == len(valid_stocks), \
            f"应只训练有效股票，实际训练了: {trained_stocks}"
        print("[测试] 跳过无效股票测试通过!")

    def test_train_stocks_data_insufficient(self, client):
        print("\n[测试] 测试所有股票数据都不足的情况...")
        stock_list = ['INVALID1', 'INVALID2', 'INVALID3']
        payload = {
            'stock_code': stock_list,
            'market': 'SZ',
            'period': '1d',
            'start_date': '20230101',
            'end_date': '20231231',
            'model_type': 'RandomForest',
            'features': ['ma5', 'ma10', 'rsi6'],
            'horizon': 5,
            'threshold': 0.02,
            'label_type': 'fixed',
            'mode': 'classification'
        }
        response = client.post('/api/ml/train', json=payload)
        print(f"[测试] 响应状态码: {response.status_code}")
        print(f"[测试] 响应: {response.get_json()}")
        assert response.status_code == 400, "所有股票都无效时应该返回400错误"
        data = response.get_json()
        assert 'error' in data
        assert '没有足够的有效数据' in data['error']
        print("[测试] 数据不足错误处理测试通过!")

    def test_train_ensemble_multiple_stocks(self, client):
        print("\n[测试] 测试多只股票集成训练...")
        stock_list = ['000001', '000002']
        payload = {
            'stock_code': stock_list,
            'market': 'SZ',
            'period': '1d',
            'start_date': '20230101',
            'end_date': '20231231',
            'model_type': 'RandomForest',
            'features': ['ma5', 'ma10', 'ma20'],
            'horizon': 5,
            'threshold': 0.02,
            'label_type': 'fixed',
            'mode': 'classification',
            'use_ensemble': True
        }
        response = client.post('/api/ml/train', json=payload)
        assert response.status_code == 200, f"请求失败: {response.status_code}"
        data = response.get_json()

        print(f"[测试] 响应: {data}")
        assert data['status'] == 'trained', f"训练失败: {data}"
        assert 'models' in data, "集成训练应该返回多个模型"
        assert len(data['models']) > 1, "集成训练应该返回多个子模型"
        assert 'stock_sample_counts' in data
        print(f"[测试] 集成训练了 {len(data['models'])} 个子模型")
        print("[测试] 多只股票集成训练测试通过!")


class TestMLFeaturesAPI:
    @pytest.fixture
    def client(self):
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client

    def test_get_features(self, client):
        print("\n[测试] 测试获取特征列表...")
        response = client.get('/api/ml/features')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) > 0
        print(f"[测试] 获取到 {len(data)} 个特征")
        print("[测试] 获取特征列表测试通过!")

    def test_get_stocks(self, client):
        print("\n[测试] 测试获取股票列表...")
        response = client.get('/api/ml/stocks?market=SZ&period=1d')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
        print(f"[测试] SZ市场1d周期有 {len(data)} 只股票")
        print("[测试] 获取股票列表测试通过!")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
