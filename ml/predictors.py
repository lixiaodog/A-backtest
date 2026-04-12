import pandas as pd
import numpy as np


class Predictor:
    def __init__(self, model, feature_engineer):
        self.model = model
        self.feature_engineer = feature_engineer

    def predict(self, df: pd.DataFrame, feature_names: list = None):
        features = self.feature_engineer.calculate_features(df, feature_names)
        if len(features) == 0:
            return None

        last_features = features.iloc[-1:]

        prediction = self.model.predict(last_features)[0]
        probabilities = self.model.predict_proba(last_features)[0]

        signal_map = {0: '卖出', 1: '持有', 2: '买入'}
        signal = signal_map.get(prediction, '持有')

        confidence = float(max(probabilities))

        return {
            'signal': signal,
            'confidence': confidence,
            'probabilities': {
                '卖出': float(probabilities[0]),
                '持有': float(probabilities[1]),
                '买入': float(probabilities[2])
            }
        }

    def predict_batch(self, df: pd.DataFrame, feature_names: list = None):
        features = self.feature_engineer.calculate_features(df, feature_names)
        if len(features) == 0:
            return None

        predictions = self.model.predict(features)
        probabilities = self.model.predict_proba(features)

        signal_map = {0: '卖出', 1: '持有', 2: '买入'}
        signals = [signal_map.get(p, '持有') for p in predictions]

        return {
            'signals': signals,
            'probabilities': probabilities.tolist(),
            'dates': features.index.tolist()
        }
