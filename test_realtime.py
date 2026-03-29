import sys, os, time, requests, socketio as sio
sys.path.insert(0, '.')

progress_events = []
chart_events = []

client = sio.Client()

@client.on('progress')
def on_progress(data):
    progress_events.append(data)
    print(f"[PROGRESS] status={data.get('status')}, message={str(data.get('message', ''))[:50]}")

@client.on('backtest_chart')
def on_chart(data):
    chart_events.append(data)
    print(f"[CHART] bar_index={data.get('bar_index')}, close={data.get('bar', {}).get('close')}")

try:
    client.connect('http://localhost:5000', wait_timeout=5)
    print('WebSocket connected')

    payload = {
        'stock': '600519',
        'start_date': '20230101',
        'end_date': '20231231',
        'strategy': 'sma_cross'
    }
    resp = requests.post('http://localhost:5000/api/backtest', json=payload)
    task_id = resp.json()['task_id']
    print(f'Task submitted: {task_id}')

    timeout = 120
    start = time.time()
    while time.time() - start < timeout:
        if any(e.get('status') in ['completed', 'failed'] for e in progress_events):
            break
        time.sleep(1)

    print(f'\nTotal progress events: {len(progress_events)}')
    print(f'Total chart events: {len(chart_events)}')

    if chart_events:
        print(f'First chart event: bar_index={chart_events[0].get("bar_index")}')
        print(f'Last chart event: bar_index={chart_events[-1].get("bar_index")}')

    client.disconnect()
except Exception as e:
    print(f'Error: {e}')
