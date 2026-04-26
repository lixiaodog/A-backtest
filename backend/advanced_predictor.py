"""
选股引擎 - 支持多股票、多模型批量预测和结果融合
"""
import threading
import traceback
import sys
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import pandas as pd
import os
from multiprocessing import cpu_count


@dataclass
class PredictionResult:
    stock_code: str
    stock_name: str
    model_id: str
    model_type: str
    model_name: str = ""
    signal: str = ""
    confidence: float = 0.0
    buy_probability: float = 0.0
    sell_probability: float = 0.0
    hold_probability: float = 0.0
    predicted_return: float = 0.0
    raw_prediction: Dict = field(default_factory=dict)
    rank: int = 0
    error: str = ""


def _predict_single_stock_process(args) -> Optional[PredictionResult]:
    stock_code, model_info, period, market, data_source_config = args
    
    try:
        import joblib
        import pandas as pd
        import numpy as np
        from ml.predictors import Predictor
        from ml.feature_engineering import FeatureEngineer
        from backend.providers.local_provider import LocalDataProvider
        from backend.providers.factor_cache_provider import FactorCacheProvider
        
        data_provider = None
        source_type = 'local'
        if data_source_config:
            source_type = data_source_config.get('type', 'local')
            stock_file_map = data_source_config.get('stock_file_map')
            
            if source_type == 'factor_cache':
                data_provider = FactorCacheProvider(
                    cache_path=data_source_config.get('cache_path', './data/factor_cache/'),
                    raw_data_path=data_source_config.get('raw_data_path', './data/'),
                    factor_library=data_source_config.get('factor_library', 'alpha191'),
                    silent=False,
                    stock_file_map=stock_file_map
                )
            elif source_type == 'local':
                data_provider = LocalDataProvider(
                    data_path=data_source_config.get('data_path', './data/'),
                    silent=False,
                    stock_file_map=stock_file_map
                )
            else:
                from backend.providers import create_provider
                data_provider = create_provider('akshare')
        else:
            data_provider = LocalDataProvider(silent=False)
        
        realtime_data = data_provider.get_stock_data(stock_code, period=period, market=market, latest_only=True)
        
        if realtime_data is None or realtime_data.empty:
            return None
        
        stock_name = stock_code
        if "name" in realtime_data.columns and len(realtime_data) > 0:
            stock_name = realtime_data["name"].iloc[-1]
        
        model_path = model_info.get("file_path")
        if not model_path:
            return None
        model = joblib.load(model_path)
        if not model:
            return None
        
        predictor = Predictor(None, None, model_info.get('label_type', 'fixed'))
        predictor.model = model
        
        model_features = model_info.get("features", [])
        
        if source_type == 'factor_cache':
            available_features = [f for f in model_features if f in realtime_data.columns]
            if not available_features:
                return None
            
            last_row = realtime_data.iloc[-1:]
            features = last_row[available_features].copy()
            
            if features.isnull().any().any():
                features = features.fillna(0)
            
            if model_info.get("scaler_params"):
                scaler_params = model_info["scaler_params"]
                mean = np.array(scaler_params['mean'])
                scale = np.array(scaler_params['scale'])
                
                if len(mean) == len(features.columns) and np.all(scale > 0):
                    feature_order = scaler_params.get('feature_names', model_features)
                    available_in_order = [f for f in feature_order if f in features.columns]
                    if available_in_order:
                        features_ordered = features[available_in_order].values
                        scale_subset = np.array([scale[feature_order.index(f)] for f in available_in_order])
                        mean_subset = np.array([mean[feature_order.index(f)] for f in available_in_order])
                        features_normalized = (features_ordered - mean_subset) / scale_subset
                        features = pd.DataFrame(features_normalized, columns=available_in_order)
        else:
            if len(realtime_data) > 120:
                realtime_data = realtime_data.tail(120).reset_index(drop=True)
            
            feature_engineer = FeatureEngineer()
            if model_info.get("scaler_params"):
                feature_engineer.set_scaler_params(model_info["scaler_params"])
            
            features = feature_engineer.calculate_features(
                realtime_data, model_features
            )
        
        if features is None or features.empty:
            return None
        
        last_features = features.iloc[-1:] if len(features) > 1 else features
        threshold = model_info.get('threshold', 0.02)
        if model_info.get("mode") == "regression":
            prediction = predictor._predict_regression(last_features, threshold)
        else:
            prediction = predictor._predict_classification(last_features)
        
        if not prediction:
            return None
        
        return PredictionResult(
            stock_code=stock_code,
            stock_name=stock_name,
            model_id=model_info.get("id", ""),
            model_type=model_info.get("model_type", ""),
            model_name=model_info.get("model_name", model_info.get("id", "")),
            signal=prediction.get("signal", "持有"),
            confidence=prediction.get("confidence", 0.0),
            buy_probability=prediction.get("probabilities", {}).get("买入", 0.0),
            sell_probability=prediction.get("probabilities", {}).get("卖出", 0.0),
            hold_probability=prediction.get("probabilities", {}).get("持有", 0.0),
            predicted_return=prediction.get("predicted_return", 0.0),
            raw_prediction=prediction
        )
    except Exception as e:
        print(f"[Process] {stock_code} 预测异常: {e}")
        import traceback
        traceback.print_exc()
        return None


@dataclass
class PredictionTask:
    task_id: str
    markets: List[str]
    stocks: List[str]
    model_ids: List[str]
    sort_by: str = "confidence"
    sort_order: str = "desc"
    top_n: int = 100
    fusion_mode: str = "intersection"
    period: str = "1d"
    status: str = "pending"
    progress: int = 0
    message: str = ""
    results: Dict[str, List[PredictionResult]] = field(default_factory=dict)
    fused_results: List[PredictionResult] = field(default_factory=list)
    total_stocks: int = 0
    processed_stocks: int = 0
    export_files: Dict[str, str] = field(default_factory=dict)
    stopped: bool = False
    start_time: float = 0.0


class AdvancedPredictor:

    def __init__(self, max_workers: int = 4, data_provider=None):
        self.max_workers = max_workers
        self.tasks: Dict[str, PredictionTask] = {}
        self._lock = threading.Lock()
        
        if data_provider is None:
            from backend.providers import ProviderFactory
            self.data_provider = ProviderFactory.create_provider('akshare')
        else:
            self.data_provider = data_provider

    def create_task(self, task_id: str, markets: List[str], stocks: List[str],
                    model_ids: List[str], sort_by: str = "confidence",
                    sort_order: str = "desc", top_n: int = 100,
                    fusion_mode: str = "intersection", period: str = "1d") -> PredictionTask:
        import time
        task = PredictionTask(
            task_id=task_id,
            markets=markets,
            stocks=stocks,
            model_ids=model_ids,
            sort_by=sort_by,
            sort_order=sort_order,
            top_n=top_n,
            fusion_mode=fusion_mode,
            period=period,
            status="pending",
            progress=0,
            start_time=time.time()
        )
        with self._lock:
            self.tasks[task_id] = task
        return task

    def get_task(self, task_id: str) -> Optional[PredictionTask]:
        return self.tasks.get(task_id)
    
    def stop_task(self, task_id: str) -> bool:
        with self._lock:
            task = self.tasks.get(task_id)
            if task and task.status == "running":
                task.stopped = True
                task.status = "stopping"
                task.message = "正在停止..."
                return True
        return False
    
    def delete_task(self, task_id: str) -> bool:
        with self._lock:
            task = self.tasks.get(task_id)
            if task:
                if task.status == "running":
                    task.stopped = True
                    task.status = "stopping"
                del self.tasks[task_id]
                return True
        return False
    
    def get_all_tasks(self) -> List[Dict]:
        import time
        tasks = []
        with self._lock:
            for task in self.tasks.values():
                elapsed = time.time() - task.start_time if task.start_time > 0 else 0
                tasks.append({
                    'task_id': task.task_id,
                    'status': task.status,
                    'progress': task.progress,
                    'message': task.message,
                    'total_stocks': task.total_stocks,
                    'processed_stocks': task.processed_stocks,
                    'model_count': len(task.model_ids),
                    'elapsed_time': round(elapsed, 1)
                })
        return sorted(tasks, key=lambda x: x.get('task_id', ''), reverse=True)

    def run_prediction(self, task: PredictionTask):
        print(f"[AdvancedPredictor] ========== 开始预测任务 {task.task_id} ==========", flush=True)
        sys.stdout.flush()
        try:
            task.status = "running"
            task.message = "准备股票列表..."
            task.progress = 5

            if task.stopped:
                task.status = "stopped"
                task.message = "任务已停止"
                return

            all_stocks = self._get_stock_list(task.markets, task.stocks, task.period)
            task.total_stocks = len(all_stocks)
            
            dp_name = getattr(self.data_provider, 'name', 'unknown')
            task.message = f"[DEBUG dp={dp_name}] 扫描完成，共 {task.total_stocks} 只股票待预测"
            task.progress = 10

            is_regression = False
            for model_idx, model_id in enumerate(task.model_ids):
                if task.stopped:
                    task.status = "stopped"
                    task.message = f"任务已停止，已完成 {model_idx}/{len(task.model_ids)} 个模型"
                    return
                
                model_info = self._get_model_info(model_id)
                if model_info:
                    model_type = model_info.get('model_type', 'Unknown')
                    if model_info.get('mode') == 'regression' or model_info.get('label_type') == 'regression':
                        is_regression = True
                else:
                    from ml import ModelRegistry
                    registry = ModelRegistry()
                    sub_models = registry.get_models_by_parent_id(model_id)
                    if sub_models:
                        model_type = f"集成模型({len(sub_models)}个子模型)"
                    else:
                        model_type = 'Unknown'
                task.message = f"模型 {model_idx+1}/{len(task.model_ids)} [{model_type}]: 开始预测 {task.total_stocks} 只股票"
                
                results = self._predict_with_model(model_id, all_stocks, task)
                task.results[model_id] = results
                task.progress = 10 + int((model_idx + 1) / len(task.model_ids) * 70)

            if task.stopped:
                task.status = "stopped"
                task.message = "任务已停止"
                return

            task.message = "排序各模型结果..."
            if is_regression and task.sort_by == "confidence":
                task.sort_by = "return"
            self._sort_results(task)
            task.progress = 85

            task.message = f"融合 {len(task.model_ids)} 个模型结果..."
            self._fuse_results(task)
            task.progress = 95

            task.fused_results = self._sort_single_result(
                task.fused_results, task.sort_by, task.sort_order
            )[:task.top_n]

            task.message = "导出结果到Excel..."
            self._export_results_to_excel(task)

            task.status = "completed"
            task.progress = 100
            task.message = f"预测完成，共筛选出 {len(task.fused_results)} 只股票"

        except Exception as e:
            task.status = "failed"
            task.message = f"预测失败: {str(e)}"
            traceback.print_exc()

    def _get_stock_list(self, markets: List[str], stocks: List[str], period: str = "1d") -> List[str]:
        result_set = set()

        for stock in stocks:
            if stock and stock.strip():
                result_set.add(stock.strip())

        for market in markets:
            market_stocks = self.data_provider.get_market_stocks(market, period=period)
            result_set.update(market_stocks)

        return sorted(list(result_set))

    def _infer_market(self, stock_code: str) -> str:
        code = str(stock_code)
        if code.startswith(('60', '68', '69', '5')):
            return 'SH'
        elif code.startswith(('8', '4', '9')):
            return 'BJ'
        else:
            return 'SZ'

    def _get_model_info(self, model_id: str) -> Optional[Dict]:
        from ml import ModelRegistry
        try:
            registry = ModelRegistry()
            model_info = registry.get_model_by_id(model_id)
            if not model_info:
                model_info = registry.get_model_by_parent_id(model_id)
            return model_info
        except Exception:
            return None

    def _predict_with_model(self, model_id: str, stocks: List[str],
                           task: PredictionTask) -> List[PredictionResult]:
        from ml import ModelRegistry
        from ml.predictors import Predictor

        results = []
        
        try:
            registry = ModelRegistry()
            model_info = registry.get_model_by_id(model_id)
            
            if not model_info:
                model_info = registry.get_model_by_parent_id(model_id)
            
            if not model_info:
                sub_models = registry.get_models_by_parent_id(model_id)
                if sub_models:
                    print(f"[AdvancedPredictor] 集成模型 {model_id} 包含 {len(sub_models)} 个子模型", flush=True)
                    all_results = []
                    for sub_model in sub_models:
                        source_type = 'local'
                        if hasattr(self, 'data_provider'):
                            source_type = self.data_provider.name
                        
                        if source_type == 'factor_cache':
                            sub_results = self._predict_sequential(model_id, sub_model, stocks, task)
                        else:
                            sub_results = self._predict_parallel(model_id, sub_model, stocks, task)
                        all_results.extend(sub_results)
                    return all_results
                else:
                    print(f"[AdvancedPredictor] 模型 {model_id} 不存在", flush=True)
                    return results

            print(f"[AdvancedPredictor] 模型 {model_id} 开始预测 {len(stocks)} 只股票", flush=True)
            
            source_type = 'local'
            if hasattr(self, 'data_provider'):
                source_type = self.data_provider.name
            
            if source_type == 'factor_cache':
                print(f"[AdvancedPredictor] 因子缓存模式: 使用多线程并发预测", flush=True)
                results = self._predict_sequential(model_id, model_info, stocks, task)
            else:
                print(f"[AdvancedPredictor] 普通模式: 使用多进程并发预测", flush=True)
                results = self._predict_parallel(model_id, model_info, stocks, task)

        except Exception as e:
            print(f"[AdvancedPredictor] 模型 {model_id} 预测失败: {e}", flush=True)
            traceback.print_exc()

        return results

    def _predict_sequential(self, model_id: str, model_info: Dict, 
                           stocks: List[str], task: PredictionTask) -> List[PredictionResult]:
        import joblib
        from ml.predictors import Predictor
        import numpy as np
        
        print(f"[AdvancedPredictor] _predict_sequential 开始: 模型={model_id}, 股票数={len(stocks)}", flush=True)
        sys.stdout.flush()
        
        results = []
        success_count = 0
        fail_count = 0
        total = len(stocks)
        
        predictor = Predictor(None, None, model_info.get('label_type', 'fixed'))
        model_path = model_info.get("file_path")
        
        if not model_path:
            print(f"[AdvancedPredictor] 模型路径为空，跳过", flush=True)
            return results
            
        print(f"[AdvancedPredictor] 加载模型: {model_path}", flush=True)
        model = joblib.load(model_path)
        if not model:
            print(f"[AdvancedPredictor] 模型加载失败", flush=True)
            return results
        predictor.model = model
        print(f"[AdvancedPredictor] 模型加载成功", flush=True)
        
        model_features = model_info.get("features", [])
        scaler_params = model_info.get("scaler_params")
        threshold = model_info.get('threshold', 0.02)
        mode = model_info.get("mode")
        
        print(f"[AdvancedPredictor] 模型特征数: {len(model_features)}, mode={mode}, threshold={threshold}", flush=True)
        
        results_lock = threading.Lock()
        processed_lock = threading.Lock()
        processed_count = [0]
        
        def predict_single_stock(stock):
            nonlocal success_count, fail_count
            try:
                market = self._infer_market(stock)
                # 获取最新一天的因子数据
                realtime_data = self.data_provider.get_stock_data(
                    stock, 
                    period=task.period, 
                    market=market,
                    include_raw_data=False,
                    latest_only=True
                )
                
                if realtime_data is None or realtime_data.empty:
                    with processed_lock:
                        fail_count += 1
                        processed_count[0] += 1
                    if fail_count <= 3:
                        print(f"[Thread] {stock}: 无数据 (market={market})", flush=True)
                    return None
                
                available_features = [f for f in model_features if f in realtime_data.columns]
                if not available_features:
                    with processed_lock:
                        fail_count += 1
                        processed_count[0] += 1
                    if fail_count <= 3:
                        print(f"[Thread] {stock}: 无可用特征 (有{len(realtime_data.columns)}列)", flush=True)
                    return None
                
                last_row = realtime_data.iloc[-1:]
                features = last_row[available_features].copy()
                
                if features.isnull().any().any():
                    features = features.fillna(0)
                
                if features.isnull().any().any():
                    features = features.fillna(0)
                
                if mode == "regression":
                    prediction = predictor._predict_regression(features, threshold)
                else:
                    prediction = predictor._predict_classification(features)
                
                with processed_lock:
                    processed_count[0] += 1
                
                if prediction:
                    with processed_lock:
                        success_count += 1
                    if success_count <= 3:
                        print(f"[Thread] {stock}: 成功 信号={prediction.get('signal', '')} 收益={prediction.get('predicted_return', 0)*100:.2f}%", flush=True)
                    return PredictionResult(
                        stock_code=stock,
                        stock_name=stock,
                        model_id=model_info.get("id", ""),
                        model_type=model_info.get("model_type", ""),
                        model_name=model_info.get("model_name", model_info.get("id", "")),
                        signal=prediction.get("signal", "持有"),
                        confidence=prediction.get("confidence") or 0.0,
                        buy_probability=prediction.get("probabilities", {}).get("买入") or 0.0,
                        sell_probability=prediction.get("probabilities", {}).get("卖出") or 0.0,
                        hold_probability=prediction.get("probabilities", {}).get("持有") or 0.0,
                        predicted_return=prediction.get("predicted_return") or 0.0,
                        raw_prediction=prediction
                    )
                else:
                    with processed_lock:
                        fail_count += 1
                    return None
                    
            except Exception as e:
                with processed_lock:
                    fail_count += 1
                    processed_count[0] += 1
                if fail_count <= 5:
                    print(f"[Thread] {stock} 预测异常: {e}", flush=True)
                    import traceback
                    traceback.print_exc()
                return None
        
        max_workers = max(4, (cpu_count() or 4) * 2)
        print(f"[AdvancedPredictor] 使用 {max_workers} 个线程进行并发预测", flush=True)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for i, stock in enumerate(stocks):
                if task.stopped:
                    print(f"[AdvancedPredictor] 任务已停止", flush=True)
                    break
                futures.append(executor.submit(predict_single_stock, stock))
            
            for i, future in enumerate(as_completed(futures)):
                if task.stopped:
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                
                result = future.result()
                if result:
                    with results_lock:
                        results.append(result)
                
                task.processed_stocks = processed_count[0]
                
                if (i + 1) % 500 == 0 or (i + 1) == total:
                    task.message = f"模型 {model_id[:8]}: {i+1}/{total} 成功:{success_count} 失败:{fail_count}"
                    print(f"[AdvancedPredictor] 预测进度: {i+1}/{total} 成功:{success_count}", flush=True)
        
        print(f"[AdvancedPredictor] 模型 {model_id} 预测完成: {success_count} 成功, {fail_count} 失败", flush=True)
        return results

    def _predict_parallel(self, model_id: str, model_info: Dict,
                         stocks: List[str], task: PredictionTask) -> List[PredictionResult]:
        from ml.predictors import Predictor
        from ml.feature_engineering import FeatureEngineer

        results = []
        success_count = 0
        fail_count = 0

        predictor = Predictor(None, None, model_info.get('label_type', 'fixed'))
        feature_engineer = FeatureEngineer()

        max_workers = max(2, (cpu_count() or 4) - 2)
        print(f"[AdvancedPredictor] 使用 {max_workers} 个进程进行并发预测", flush=True)
        
        predict_args = []
        
        stock_file_map = None
        if hasattr(self, 'data_provider') and hasattr(self.data_provider, '_stock_file_map'):
            stock_file_map = self.data_provider._stock_file_map
        
        for stock in stocks:
            market = self._infer_market(stock)
            data_source_config = None
            if hasattr(self, 'data_provider'):
                provider = self.data_provider
                if provider.name == 'local':
                    data_source_config = {
                        'type': 'local',
                        'data_path': getattr(provider, 'data_path', './data/'),
                        'stock_file_map': stock_file_map
                    }
                elif provider.name == 'factor_cache':
                    data_source_config = {
                        'type': 'factor_cache',
                        'cache_path': getattr(provider, 'cache_path', './data/factor_cache/'),
                        'raw_data_path': getattr(provider, 'raw_data_path', './data/'),
                        'factor_library': getattr(provider, 'factor_library', 'alpha191'),
                        'stock_file_map': stock_file_map
                    }
                else:
                    data_source_config = {'type': 'akshare'}
            
            predict_args.append((
                stock, model_info, task.period, market, data_source_config
            ))
        
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            future_to_stock = {}
            submitted_count = 0
            for args in predict_args:
                if task.stopped:
                    break
                stock = args[0]
                future = executor.submit(_predict_single_stock_process, args)
                future_to_stock[future] = stock
                submitted_count += 1
                
                if submitted_count % 100 == 0:
                    task.message = f"模型 {model_id[:8]}: 已提交 {submitted_count}/{len(stocks)} 只股票"

            for future in as_completed(future_to_stock):
                if task.stopped:
                    for f in future_to_stock:
                        if not f.done():
                            f.cancel()
                    break
                
                stock = future_to_stock[future]
                try:
                    result = future.result(timeout=120)
                    if result:
                        results.append(result)
                        success_count += 1
                    else:
                        fail_count += 1
                    task.processed_stocks += 1
                    
                    if task.processed_stocks % 50 == 0 or task.processed_stocks == len(stocks):
                        task.message = f"模型 {model_id[:8]}: {stock} ({task.processed_stocks}/{len(stocks)}) 成功:{success_count} 失败:{fail_count}"
                except Exception as e:
                    fail_count += 1
                    task.processed_stocks += 1
                    task.message = f"模型 {model_id[:8]}: {stock} 预测失败 ({task.processed_stocks}/{len(stocks)})"

        print(f"[AdvancedPredictor] 模型 {model_id} 预测完成: {success_count} 成功, {fail_count} 失败", flush=True)
        return results

    def _predict_single_stock(self, stock_code: str, model_info: Dict,
                              feature_engineer, predictor, period: str, market: str = None) -> Optional[PredictionResult]:
        try:
            import joblib
            import numpy as np

            realtime_data = self.data_provider.get_stock_data(stock_code, period=period, market=market)

            if realtime_data is None or realtime_data.empty:
                return None
            
            stock_name = stock_code
            if "name" in realtime_data.columns and len(realtime_data) > 0:
                stock_name = realtime_data["name"].iloc[-1]

            model_path = model_info.get("file_path")
            if not model_path:
                return None
            model = joblib.load(model_path)
            if not model:
                return None

            predictor.model = model
            
            model_features = model_info.get("features", [])
            
            if self.data_provider.name == 'factor_cache':
                available_features = [f for f in model_features if f in realtime_data.columns]
                if not available_features:
                    return None
                
                last_row = realtime_data.iloc[-1:]
                features = last_row[available_features].copy()
                
                if features.isnull().any().any():
                    features = features.fillna(0)
                
                if model_info.get("scaler_params"):
                    scaler_params = model_info["scaler_params"]
                    mean = np.array(scaler_params['mean'])
                    scale = np.array(scaler_params['scale'])
                    
                    if len(mean) == len(features.columns) and np.all(scale > 0):
                        feature_order = scaler_params.get('feature_names', model_features)
                        available_in_order = [f for f in feature_order if f in features.columns]
                        if available_in_order:
                            features_ordered = features[available_in_order].values
                            scale_subset = np.array([scale[feature_order.index(f)] for f in available_in_order])
                            mean_subset = np.array([mean[feature_order.index(f)] for f in available_in_order])
                            features_normalized = (features_ordered - mean_subset) / scale_subset
                            features = pd.DataFrame(features_normalized, columns=available_in_order)
            else:
                if len(realtime_data) > 120:
                    realtime_data = realtime_data.tail(120).reset_index(drop=True)
                
                if model_info.get("scaler_params"):
                    feature_engineer.set_scaler_params(model_info["scaler_params"])

                features = feature_engineer.calculate_features(
                    realtime_data, model_features
                )

            if features is None or features.empty:
                return None

            last_features = features.iloc[-1:] if len(features) > 1 else features

            threshold = model_info.get('threshold', 0.02)
            if model_info.get("mode") == "regression":
                prediction = predictor._predict_regression(last_features, threshold)
            else:
                prediction = predictor._predict_classification(last_features)

            if not prediction:
                return None

            return PredictionResult(
                stock_code=stock_code,
                stock_name=stock_name,
                model_id=model_info.get("id", ""),
                model_type=model_info.get("model_type", ""),
                model_name=model_info.get("model_name", model_info.get("id", "")),
                signal=prediction.get("signal", "持有"),
                confidence=prediction.get("confidence", 0.0),
                buy_probability=prediction.get("probabilities", {}).get("买入", 0.0),
                sell_probability=prediction.get("probabilities", {}).get("卖出", 0.0),
                hold_probability=prediction.get("probabilities", {}).get("持有", 0.0),
                predicted_return=prediction.get("predicted_return", 0.0),
                raw_prediction=prediction
            )

        except Exception as e:
            print(f"[AdvancedPredictor] {stock_code} 预测异常: {e}", flush=True)
            import traceback
            traceback.print_exc()
            return None

    def _sort_results(self, task: PredictionTask):
        for model_id in task.results:
            task.results[model_id] = self._sort_single_result(
                task.results[model_id], task.sort_by, task.sort_order
            )

    def _sort_single_result(self, results: List[PredictionResult],
                           sort_by: str, sort_order: str) -> List[PredictionResult]:
        reverse = sort_order == "desc"

        def signal_weight(signal: str) -> int:
            if "买入" in signal:
                return 2
            elif "持有" in signal:
                return 1
            else:
                return 0

        if sort_by == "confidence":
            if reverse:
                sorted_results = sorted(results, key=lambda x: (signal_weight(x.signal), x.confidence or 0), reverse=True)
            else:
                sorted_results = sorted(results, key=lambda x: (signal_weight(x.signal), x.confidence or 0))
        elif sort_by == "buy_probability":
            sorted_results = sorted(results, key=lambda x: x.buy_probability or 0, reverse=reverse)
        elif sort_by == "return":
            sorted_results = sorted(results, key=lambda x: x.predicted_return or 0, reverse=reverse)
        else:
            sorted_results = results

        for i, result in enumerate(sorted_results):
            result.rank = i + 1

        return sorted_results

    def _fuse_results(self, task: PredictionTask):
        if not task.results:
            return

        if len(task.model_ids) == 1:
            task.fused_results = list(task.results.get(task.model_ids[0], []))
            return

        top_results_by_model = {}
        for model_id in task.model_ids:
            if model_id in task.results:
                top_results_by_model[model_id] = {
                    r.stock_code: r for r in task.results[model_id][:task.top_n]
                }

        if task.fusion_mode == "intersection":
            task.fused_results = self._fuse_intersection(top_results_by_model, task)
            if not task.fused_results:
                task.fused_results = self._fuse_union(top_results_by_model, task)
        elif task.fusion_mode == "union":
            task.fused_results = self._fuse_union(top_results_by_model, task)
        elif task.fusion_mode == "weighted":
            task.fused_results = self._fuse_weighted(top_results_by_model, task)
        else:
            task.fused_results = self._fuse_intersection(top_results_by_model, task)

    def _fuse_intersection(self, results_by_model: Dict[str, Dict[str, PredictionResult]],
                          task: PredictionTask) -> List[PredictionResult]:
        if not results_by_model:
            return []

        common_stocks = None
        for model_results in results_by_model.values():
            stocks = set(model_results.keys())
            if common_stocks is None:
                common_stocks = stocks
            else:
                common_stocks = common_stocks.intersection(stocks)

        if not common_stocks:
            return []

        fused = []
        for stock_code in common_stocks:
            total_confidence = 0
            total_buy_prob = 0
            signals = []

            for model_id, model_results in results_by_model.items():
                result = model_results[stock_code]
                total_confidence += result.confidence
                total_buy_prob += result.buy_probability
                signals.append(result.signal)

            buy_count = signals.count("买入") + signals.count("强烈买入") + signals.count("轻度买入")
            sell_count = signals.count("卖出") + signals.count("强烈卖出") + signals.count("轻度卖出")

            if buy_count > sell_count:
                final_signal = "买入"
            elif sell_count > buy_count:
                final_signal = "卖出"
            else:
                final_signal = "持有"

            avg_confidence = total_confidence / len(results_by_model)
            avg_buy_prob = total_buy_prob / len(results_by_model)

            fused.append(PredictionResult(
                stock_code=stock_code,
                stock_name=model_results[stock_code].stock_name,
                model_id="fused",
                model_type="融合结果",
                model_name="融合结果",
                signal=final_signal,
                confidence=avg_confidence,
                buy_probability=avg_buy_prob,
                raw_prediction={"models": len(results_by_model)}
            ))

        return fused

    def _fuse_union(self, results_by_model: Dict[str, Dict[str, PredictionResult]],
                   task: PredictionTask) -> List[PredictionResult]:
        if not results_by_model:
            return []

        all_stocks = set()
        for model_results in results_by_model.values():
            all_stocks.update(model_results.keys())

        fused = []
        for stock_code in all_stocks:
            best_result = None
            best_confidence = -1

            for model_results in results_by_model.values():
                if stock_code in model_results:
                    result = model_results[stock_code]
                    if result.confidence > best_confidence:
                        best_confidence = result.confidence
                        best_result = result

            if best_result:
                fused.append(best_result)

        return fused

    def _fuse_weighted(self, results_by_model: Dict[str, Dict[str, PredictionResult]],
                      task: PredictionTask) -> List[PredictionResult]:
        if not results_by_model:
            return []

        stock_votes = {}

        for model_results in results_by_model.values():
            for stock_code, result in model_results.items():
                if stock_code not in stock_votes:
                    stock_votes[stock_code] = {
                        "results": [],
                        "buy_votes": 0,
                        "total_confidence": 0
                    }
                stock_votes[stock_code]["results"].append(result)
                if "买入" in result.signal:
                    stock_votes[stock_code]["buy_votes"] += 1
                stock_votes[stock_code]["total_confidence"] += result.confidence

        sorted_stocks = sorted(
            stock_votes.items(),
            key=lambda x: (x[1]["buy_votes"], x[1]["total_confidence"]),
            reverse=True
        )

        fused = []
        for stock_code, vote_info in sorted_stocks:
            avg_confidence = vote_info["total_confidence"] / len(vote_info["results"])
            buy_ratio = vote_info["buy_votes"] / len(vote_info["results"])

            if buy_ratio >= 0.5:
                signal = "买入"
            elif buy_ratio == 0:
                signal = "卖出"
            else:
                signal = "持有"

            first_result = vote_info["results"][0]
            fused.append(PredictionResult(
                stock_code=stock_code,
                stock_name=first_result.stock_name,
                model_id="fused",
                model_type=f"融合({len(vote_info['results'])}模型)",
                model_name=f"融合({len(vote_info['results'])}模型)",
                signal=signal,
                confidence=avg_confidence,
                buy_probability=buy_ratio,
                raw_prediction={
                    "buy_votes": vote_info["buy_votes"],
                    "total_models": len(vote_info["results"])
                }
            ))

        return fused

    def _export_results_to_excel(self, task: PredictionTask):
        try:
            import pandas as pd
            from datetime import datetime
            import os
            
            export_dir = os.path.join(os.path.dirname(__file__), '..', 'exports')
            os.makedirs(export_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            for model_id, results in task.results.items():
                if not results:
                    continue
                
                model_name = results[0].model_name if results else model_id
                
                data = []
                for r in results:
                    row = {
                        '排名': r.rank,
                        '股票代码': r.stock_code,
                        '股票名称': r.stock_name,
                        '模型名称': r.model_name or model_name,
                        '模型类型': r.model_type,
                        '买入概率': r.buy_probability,
                        '持有概率': r.hold_probability,
                        '卖出概率': r.sell_probability,
                        '预测收益率': r.predicted_return,
                        '信号': r.signal,
                        '置信度': r.confidence,
                    }
                    if r.raw_prediction:
                        for k, v in r.raw_prediction.items():
                            if k not in ('signal', 'confidence', 'probabilities', 'predicted_return'):
                                row[f'raw_{k}'] = str(v) if not isinstance(v, (int, float)) else v
                    data.append(row)
                
                df = pd.DataFrame(data)
                
                filename = f"predict_{task.task_id}_{model_id[:8]}_{timestamp}.xlsx"
                filepath = os.path.join(export_dir, filename)
                
                df.to_excel(filepath, index=False, sheet_name='预测结果')
                
                task.export_files[model_id] = filepath
            
            if task.fused_results:
                data = []
                for r in task.fused_results:
                    row = {
                        '排名': r.rank,
                        '股票代码': r.stock_code,
                        '股票名称': r.stock_name,
                        '模型名称': r.model_name,
                        '模型类型': r.model_type,
                        '买入概率': r.buy_probability,
                        '持有概率': r.hold_probability,
                        '卖出概率': r.sell_probability,
                        '预测收益率': r.predicted_return,
                        '信号': r.signal,
                        '置信度': r.confidence,
                    }
                    if r.raw_prediction:
                        for k, v in r.raw_prediction.items():
                            if k not in ('signal', 'confidence', 'probabilities', 'predicted_return'):
                                row[f'raw_{k}'] = str(v) if not isinstance(v, (int, float)) else v
                    data.append(row)
                
                df = pd.DataFrame(data)
                filename = f"predict_{task.task_id}_fused_{timestamp}.xlsx"
                filepath = os.path.join(export_dir, filename)
                df.to_excel(filepath, index=False, sheet_name='融合结果')
                
                task.export_files['fused'] = filepath
                
        except Exception as e:
            print(f"[AdvancedPredictor] 导出Excel失败: {e}", flush=True)
            traceback.print_exc()


_advanced_predictor = None
_global_tasks = {}
_global_tasks_lock = threading.Lock()


def register_task(task_id: str, predictor: 'AdvancedPredictor'):
    with _global_tasks_lock:
        _global_tasks[task_id] = predictor


def get_task_predictor(task_id: str) -> Optional['AdvancedPredictor']:
    with _global_tasks_lock:
        return _global_tasks.get(task_id)


def get_advanced_predictor() -> AdvancedPredictor:
    global _advanced_predictor
    if _advanced_predictor is None:
        _advanced_predictor = AdvancedPredictor(max_workers=4)
    return _advanced_predictor
