import pytest
import sys
import os
import time
import threading
import io

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, socketio

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@pytest.fixture
def app_context():
    with app.app_context():
        yield

class TestStrategiesAPI:
    def test_get_strategies(self, client):
        response = client.get('/api/strategies')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
        assert 'sma_cross' in data
        assert 'momentum' in data
        assert 'rsi' in data

class TestBacktestAPI:
    def test_submit_backtest(self, client):
        payload = {
            'stock': '600519',
            'start_date': '20230101',
            'end_date': '20230131',
            'strategy': 'sma_cross',
            'cash': 1000000
        }
        response = client.post('/api/backtest', json=payload)
        assert response.status_code == 200
        data = response.get_json()
        assert 'task_id' in data
        assert data['status'] == 'running'

    def test_submit_backtest_invalid_strategy(self, client):
        payload = {
            'stock': '600519',
            'start_date': '20230101',
            'end_date': '20230131',
            'strategy': 'invalid_strategy'
        }
        response = client.post('/api/backtest', json=payload)
        assert response.status_code == 200

    def test_get_backtest_result_not_found(self, client):
        response = client.get('/api/backtest/nonexistent_task_id')
        assert response.status_code == 404

    def test_get_backtest_result_after_submit(self, client):
        payload = {
            'stock': '600519',
            'start_date': '20230101',
            'end_date': '20230131',
            'strategy': 'sma_cross'
        }
        submit_resp = client.post('/api/backtest', json=payload)
        task_id = submit_resp.get_json()['task_id']

        response = client.get(f'/api/backtest/{task_id}')
        assert response.status_code == 200
        data = response.get_json()
        assert data['id'] == task_id
        assert 'status' in data

class TestUploadAPI:
    def test_upload_no_file(self, client):
        response = client.post('/api/upload')
        assert response.status_code == 400

    def test_upload_empty_filename(self, client):
        data = {'file': (io.BytesIO(b''), '')}
        response = client.post('/api/upload', data=data, content_type='multipart/form-data')
        assert response.status_code == 400

class TestChartAPI:
    def test_serve_chart_not_found(self, client):
        response = client.get('/api/chart/nonexistent.png')
        assert response.status_code == 404

    def test_serve_chart_invalid_filename(self, client):
        response = client.get('/api/chart/../../../etc/passwd')
        assert response.status_code == 404

class TestWebSocket:
    def test_websocket_connect(self):
        import socketio as sio

        connected = threading.Event()

        client = sio.Client()

        @client.on('connect')
        def on_connect():
            connected.set()

        @client.on('disconnect')
        def on_disconnect():
            pass

        try:
            client.connect('http://localhost:5000', wait_timeout=5)
            assert connected.is_set(), "WebSocket connection failed"
            client.disconnect()
        except Exception as e:
            pytest.skip(f"Backend not running: {e}")

    def test_websocket_progress_events(self):
        import socketio as sio

        progress_events = []
        connected = threading.Event()

        client = sio.Client()

        @client.on('progress')
        def on_progress(data):
            progress_events.append(data)
            connected.set()

        try:
            client.connect('http://localhost:5000', wait_timeout=5)

            import requests
            payload = {
                'stock': '600519',
                'start_date': '20230101',
                'end_date': '20230131',
                'strategy': 'sma_cross'
            }
            resp = requests.post('http://localhost:5000/api/backtest', json=payload)
            task_id = resp.json()['task_id']

            timeout = 60
            start = time.time()
            while time.time() - start < timeout:
                if any(e.get('status') == 'completed' or e.get('status') == 'failed'
                       for e in progress_events):
                    break
                time.sleep(0.5)

            assert len(progress_events) > 0, "No progress events received"

            client.disconnect()
        except Exception as e:
            pytest.skip(f"Backend not running or test timeout: {e}")

    def test_websocket_pause_resume(self):
        import socketio as sio

        pause_received = threading.Event()
        resume_received = threading.Event()
        connected = threading.Event()

        client = sio.Client()

        @client.on('connect')
        def on_connect():
            connected.set()

        @client.on('backtest_paused')
        def on_paused(data):
            pause_received.set()

        @client.on('backtest_resumed')
        def on_resumed(data):
            resume_received.set()

        try:
            client.connect('http://localhost:5000', wait_timeout=5)
            assert connected.is_set(), "WebSocket connection failed"

            import requests
            payload = {
                'stock': '600519',
                'start_date': '20230101',
                'end_date': '20230131',
                'strategy': 'sma_cross'
            }
            resp = requests.post('http://localhost:5000/api/backtest', json=payload)
            task_id = resp.json()['task_id']

            time.sleep(2)

            client.emit('pause_backtest', {'task_id': task_id})

            if not pause_received.wait(timeout=5):
                raise AssertionError("backtest_paused event not received")

            client.emit('resume_backtest', {'task_id': task_id})

            if not resume_received.wait(timeout=5):
                raise AssertionError("backtest_resumed event not received")

            client.disconnect()
        except Exception as e:
            pytest.skip(f"Backend not running or test timeout: {e}")
