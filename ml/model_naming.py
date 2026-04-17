def generate_model_name(
    market: str,
    period: str,
    model_type: str,
    end_date: str,
    feature_count: int,
    horizon: int,
    threshold: float,
    vol_window: int,
    stock_count: int,
    metric: float = None,
    is_ensemble: bool = False,
    ensemble_id: str = None,
    ensemble_index: int = None
) -> str:
    """统一生成标准化的模型名称

    单模型格式: {market}_{period}_{model_type}_{end_date}_{features}f_{horizon}h_{threshold}t_{vol_window}v_{stocks}[_{metric}]
    集成子模型格式: {market}_{period}_ENS_{end_date}_{features}f_{horizon}h_{threshold}t_{vol_window}v_{stocks}_{ensemble_id}_{model_type}_{ensemble_index}

    Args:
        market: 市场，如 'SZ', 'SH'
        period: 周期，如 '1D', '1W', '1M'
        model_type: 模型类型，如 'RF', 'LightGBM', 'XGBoost', 'ENS'
        end_date: 结束日期，格式 YYYYMMDD
        feature_count: 特征数量
        horizon: 预测天数
        threshold: 阈值
        vol_window: 波动窗口
        stock_count: 股票数量
        metric: 指标值（可选）
        is_ensemble: 是否集成模型的子模型
        ensemble_id: 集成任务ID
        ensemble_index: 子模型索引

    Returns:
        标准化的模型名称
    """
    base = f'{market.upper()}_{period.upper()}_{model_type}_{end_date}_{feature_count}f_{horizon}h_{threshold}t_{vol_window}v_{stock_count}'

    if metric is not None:
        base = f'{base}_{metric:.2f}'

    if is_ensemble and ensemble_id:
        base = f'{market.upper()}_{period.upper()}_ENS_{end_date}_{feature_count}f_{horizon}h_{threshold}t_{vol_window}v_{stock_count}_{ensemble_id}_{model_type}_{ensemble_index}'
    elif ensemble_id:
        base = f'{base}_{ensemble_id}'

    return base


def parse_model_name(name: str) -> dict:
    """解析模型名称，提取元数据

    Returns:
        dict with parsed fields or None if not standard format
    """
    parts = name.split('_')
    if len(parts) < 9:
        return None

    try:
        result = {
            'market': parts[0],
            'period': parts[1],
            'model_type': parts[2],
            'end_date': parts[3],
            'feature_count': int(parts[4].replace('f', '')),
            'horizon': int(parts[5].replace('h', '')),
            'threshold': float(parts[6].replace('t', '')),
            'vol_window': int(parts[7].replace('v', '')),
            'stock_count': int(parts[8]),
        }

        if result['model_type'] == 'ENS':
            result['is_ensemble'] = True
            if len(parts) >= 11:
                result['ensemble_id'] = parts[10]
                if len(parts) >= 12:
                    result['model_type'] = parts[11]
                    if len(parts) >= 13:
                        result['ensemble_index'] = int(parts[12])
        elif len(parts) >= 10:
            if parts[9].replace('.', '').isdigit():
                result['metric'] = float(parts[9])

        return result
    except (ValueError, IndexError):
        return None