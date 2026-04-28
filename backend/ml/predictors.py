import pandas as pd
import numpy as np


class Predictor:
    def __init__(self, model, feature_engineer, label_type='fixed'):
        self.model = model
        self.feature_engineer = feature_engineer
        self.label_type = label_type

    def _align_features(self, features):
        """确保特征顺序与模型期望的一致"""
        # 检查模型是否有feature_names_in_属性
        if isinstance(self.model, dict):
            # 集成模型，使用第一个模型的特征顺序
            first_model = list(self.model.values())[0]
            if hasattr(first_model, 'feature_names_in_'):
                expected_features = list(first_model.feature_names_in_)
                return features[expected_features]
        else:
            # 单个模型
            if hasattr(self.model, 'feature_names_in_'):
                expected_features = list(self.model.feature_names_in_)
                return features[expected_features]
        
        # 如果模型没有feature_names_in_属性，返回原始特征
        return features

    def _get_signal_map(self):
        if self.label_type == 'multi':
            return {0: '强烈卖出', 1: '轻度卖出', 2: '持有', 3: '轻度买入', 4: '强烈买入'}
        return {0: '卖出', 1: '持有', 2: '买入'}

    def _predict_classification(self, last_features):
        if isinstance(self.model, dict):
            all_probs = []
            predictions = {}
            for name, model in self.model.items():
                pred = int(model.predict(last_features)[0])
                probs = model.predict_proba(last_features)[0]
                predictions[name] = pred
                all_probs.append(probs)

            avg_probs = np.mean(all_probs, axis=0)
            prediction = int(np.round(np.mean(list(predictions.values()))))

            signal_map = self._get_signal_map()
            signal = signal_map.get(prediction, '持有')
            confidence = float(max(avg_probs))
            if np.isnan(confidence):
                confidence = None

            prob_dict = {}
            for i, prob in enumerate(avg_probs):
                prob_dict[signal_map.get(i, str(i))] = float(prob)

            return {
                'signal': signal,
                'confidence': confidence,
                'probabilities': prob_dict,
                'model_predictions': predictions
            }
        else:
            prediction = self.model.predict(last_features)[0]
            probabilities = self.model.predict_proba(last_features)[0]

            signal_map = self._get_signal_map()
            signal = signal_map.get(prediction, '持有')

            confidence = float(max(probabilities))
            if np.isnan(confidence):
                confidence = None

            prob_dict = {}
            for i, prob in enumerate(probabilities):
                prob_dict[signal_map.get(i, str(i))] = float(prob)

            return {
                'signal': signal,
                'confidence': confidence,
                'probabilities': prob_dict
            }

    def _predict_regression(self, last_features, threshold=0.02):
        if isinstance(self.model, dict):
            predictions = {}
            for name, model in self.model.items():
                predictions[name] = float(model.predict(last_features)[0])

            pred_values = list(predictions.values())
            mean_pred = np.mean(pred_values)
            std_pred = np.std(pred_values)

            max_diff = 0.05
            confidence = max(0, min(1, 1 - std_pred / max_diff)) if max_diff > 0 else None
            if confidence is not None and np.isnan(confidence):
                confidence = None

            if mean_pred > threshold:
                signal = '买入'
            elif mean_pred < -threshold:
                signal = '卖出'
            else:
                signal = '持有'

            return {
                'signal': signal,
                'confidence': confidence,
                'predicted_return': mean_pred,
                'model_predictions': predictions,
                'std': std_pred
            }
        else:
            pred = float(self.model.predict(last_features)[0])

            if pred > threshold:
                signal = '买入'
            elif pred < -threshold:
                signal = '卖出'
            else:
                signal = '持有'

            abs_pred = abs(pred)
            confidence = min(1.0, abs_pred / 0.1) if abs_pred > 0 else 0.0
            
            if signal == '买入':
                buy_prob = confidence
                sell_prob = 0.0
                hold_prob = 1.0 - confidence
            elif signal == '卖出':
                buy_prob = 0.0
                sell_prob = confidence
                hold_prob = 1.0 - confidence
            else:
                buy_prob = 0.0
                sell_prob = 0.0
                hold_prob = 1.0

            return {
                'signal': signal,
                'confidence': confidence,
                'predicted_return': pred,
                'probabilities': {
                    '买入': buy_prob,
                    '卖出': sell_prob,
                    '持有': hold_prob
                }
            }

    def predict(self, df: pd.DataFrame, feature_names: list = None, threshold=0.02):
        features = self.feature_engineer.calculate_features(df, feature_names)
        if len(features) == 0:
            return None

        last_features = features.iloc[-1:]
        if last_features.isna().any().any():
            return None

        # 确保特征顺序与模型期望的一致
        last_features = self._align_features(last_features)

        if self.label_type == 'regression':
            return self._predict_regression(last_features, threshold)

        return self._predict_classification(last_features)

    def predict_batch(self, df: pd.DataFrame, feature_names: list = None, threshold=0.02):
        features = self.feature_engineer.calculate_features(df, feature_names)
        if len(features) == 0:
            return None

        # 确保特征顺序与模型期望的一致
        features = self._align_features(features)

        if self.label_type == 'regression':
            if isinstance(self.model, dict):
                predictions = {}
                for name, m in self.model.items():
                    predictions[name] = m.predict(features).tolist()

                pred_array = np.array(list(predictions.values()))
                mean_preds = np.mean(pred_array, axis=0)
                std_preds = np.std(pred_array, axis=0)

                signals = []
                for pred in mean_preds:
                    if pred > threshold:
                        signals.append('买入')
                    elif pred < -threshold:
                        signals.append('卖出')
                    else:
                        signals.append('持有')

                return {
                    'signals': signals,
                    'predicted_returns': mean_preds.tolist(),
                    'model_predictions': predictions,
                    'stds': std_preds.tolist(),
                    'dates': features.index.tolist()
                }
            else:
                preds = self.model.predict(features)
                signals = []
                for pred in preds:
                    if pred > threshold:
                        signals.append('买入')
                    elif pred < -threshold:
                        signals.append('卖出')
                    else:
                        signals.append('持有')

                return {
                    'signals': signals,
                    'predicted_returns': preds.tolist(),
                    'dates': features.index.tolist()
                }

        predictions = self.model.predict(features)
        probabilities = self.model.predict_proba(features)

        signal_map = self._get_signal_map()
        signals = [signal_map.get(p, '持有') for p in predictions]

        return {
            'signals': signals,
            'probabilities': probabilities.tolist(),
            'dates': features.index.tolist()
        }
