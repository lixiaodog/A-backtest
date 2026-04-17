import argparse
import json
import time
import requests
import sys
from datetime import datetime

BASE_URL = 'http://localhost:5000/api'

DEFAULT_MODELS = [
    {
        'name': '模型1-分类-SZ-日线-RF',
        'market': 'SZ',
        'period': '1d',
        'model_type': 'RandomForest',
        'use_ensemble': False,
        'stocks': ['000001', '000002', '000004', '000005', '000006', '000007', '000008', '000009', '000010'],
        'horizon': 5,
        'threshold': 0.02,
        'vol_window': 20,
        'label_type': 'fixed',
        'mode': 'classification',
        'features': ['alpha191'],
        'train_mode': 'thread'
    },
    {
        'name': '模型2-回归-SZ-日线-LightGBM',
        'market': 'SZ',
        'period': '1d',
        'model_type': 'LightGBM',
        'use_ensemble': False,
        'stocks': ['000001', '000002', '000004', '000005', '000006', '000007', '000008', '000009', '000010'],
        'horizon': 5,
        'threshold': 0.02,
        'vol_window': 20,
        'label_type': 'fixed',
        'mode': 'regression',
        'features': ['alpha191'],
        'train_mode': 'thread'
    },
    {
        'name': '模型3-集成-SH-日线',
        'market': 'SH',
        'period': '1d',
        'model_type': 'RandomForest,LightGBM',
        'use_ensemble': True,
        'stocks': ['600000', '600016', '600019', '600028', '600030', '600031', '600036', '600048', '600050'],
        'horizon': 5,
        'threshold': 0.02,
        'vol_window': 20,
        'label_type': 'fixed',
        'mode': 'classification',
        'features': ['alpha191'],
        'train_mode': 'thread'
    },
]


def start_training(config):
    print(f"\n{'='*60}")
    print(f"开始训练: {config['name']}")
    print(f"{'='*60}")

    payload = {
        'market': config.get('market', 'SZ'),
        'period': config.get('period', '1d'),
        'model_type': config.get('model_type', 'RandomForest'),
        'use_ensemble': config.get('use_ensemble', False),
        'stocks': config.get('stocks', []),
        'start_date': config.get('start_date', ''),
        'end_date': config.get('end_date', datetime.now().strftime('%Y%m%d')),
        'horizon': config.get('horizon', 5),
        'threshold': config.get('threshold', 0.02),
        'vol_window': config.get('vol_window', 20),
        'label_type': config.get('label_type', 'fixed'),
        'mode': config.get('mode', 'classification'),
        'features': config.get('features', ['alpha191']),
        'train_mode': config.get('train_mode', 'thread')
    }

    try:
        resp = requests.post(f'{BASE_URL}/ml/train', json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        task_id = data.get('task_id')
        if not task_id:
            print(f"错误: 响应中没有task_id: {data}")
            return None

        print(f"任务已启动, task_id: {task_id}")
        return task_id

    except requests.exceptions.RequestException as e:
        print(f"请求失败: {e}")
        return None


def wait_for_training(task_id, poll_interval=5):
    print(f"等待训练完成...")

    while True:
        try:
            resp = requests.get(f'{BASE_URL}/ml/train/progress/{task_id}', timeout=10)
            resp.raise_for_status()
            progress = resp.json()

            status = progress.get('status', 'unknown')
            pct = progress.get('progress', 0)
            msg = progress.get('message', '')

            print(f"\r  状态: {status} ({pct}%) - {msg}", end='', flush=True)

            if status in ['完成', 'completed', 'done', 'success']:
                print(f"\n训练完成!")
                return True

            if status in ['失败', 'error', 'failed', '错误']:
                print(f"\n训练失败!")
                return False

            time.sleep(poll_interval)

        except requests.exceptions.RequestException as e:
            print(f"\n查询进度失败: {e}")
            time.sleep(poll_interval)


def main():
    parser = argparse.ArgumentParser(description='批量训练模型')
    parser.add_argument('--config', '-c', type=str, help='配置文件路径(JSON格式)')
    parser.add_argument('--market', '-m', type=str, default='SZ', help='市场(SZ/SH)')
    parser.add_argument('--period', '-p', type=str, default='1d', help='周期(1d/1w/1m)')
    parser.add_argument('--model-type', '-t', type=str, default='RandomForest', help='模型类型')
    parser.add_argument('--ensemble', '-e', action='store_true', help='使用集成模式')
    parser.add_argument('--stocks', '-s', type=str, help='股票列表(逗号分隔)')
    parser.add_argument('--mode', type=str, default='classification', choices=['classification', 'regression'], help='训练模式')
    parser.add_argument('--horizon', type=int, default=5, help='预测天数')
    parser.add_argument('--features', '-f', type=str, default='alpha191', help='特征类型(alpha191/technical/all)')

    args = parser.parse_args()

    if args.config:
        with open(args.config, 'r', encoding='utf-8') as f:
            models = json.load(f)
    else:
        models = []

    if not models:
        stocks = args.stocks.split(',') if args.stocks else ['000001', '000002', '000004', '000005', '000006']

        config = {
            'name': f'训练任务-{datetime.now().strftime("%Y%m%d-%H%M%S")}',
            'market': args.market,
            'period': args.period,
            'model_type': args.model_type,
            'use_ensemble': args.ensemble,
            'stocks': stocks,
            'horizon': args.horizon,
            'threshold': 0.02,
            'vol_window': 20,
            'label_type': 'fixed',
            'mode': args.mode,
            'features': [args.features],
            'train_mode': 'thread'
        }
        models = [config]

    print(f"将训练 {len(models)} 个模型")

    for i, config in enumerate(models, 1):
        print(f"\n[{i}/{len(models)}]")

        task_id = start_training(config)
        if not task_id:
            print(f"跳过此模型，继续下一个")
            continue

        success = wait_for_training(task_id)

        if not success:
            print(f"训练失败，继续下一个")

    print(f"\n{'='*60}")
    print("所有训练任务完成!")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
