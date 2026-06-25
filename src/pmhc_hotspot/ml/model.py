"""ML model definitions using scikit-learn / XGBoost."""

from __future__ import annotations

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

try:
    from xgboost import XGBClassifier

    HAS_XGB = True
except ImportError:
    HAS_XGB = False


def build_pipeline(
    feature_columns: list[str],
    categorical_columns: list[str] | None = None,
    model_type: str = "xgboost",
    random_state: int = 42,
) -> Pipeline:
    categorical_columns = categorical_columns or []
    numeric_columns = [c for c in feature_columns if c not in categorical_columns]

    preprocessor = ColumnTransformer(
        transformers=[
            (
                "num",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="median")),
                        ("scale", StandardScaler()),
                    ]
                ),
                numeric_columns,
            ),
            (
                "cat",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="most_frequent")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                categorical_columns,
            ),
        ],
        remainder="drop",
    )

    if model_type == "xgboost":
        if not HAS_XGB:
            raise ImportError('Install the ML extra: pip install -e ".[ml]"')
        estimator = XGBClassifier(
            n_estimators=300,
            learning_rate=0.05,
            max_depth=4,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_lambda=1.0,
            objective="binary:logistic",
            eval_metric="logloss",
            random_state=random_state,
            n_jobs=1,
        )
    else:
        estimator = LogisticRegression(
            max_iter=2000,
            class_weight="balanced",
            random_state=random_state,
        )

    return Pipeline([("preprocess", preprocessor), ("model", estimator)])
