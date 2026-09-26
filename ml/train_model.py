import pandas as pd
import joblib

from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_absolute_error, r2_score


# 1. Dataset load
df = pd.read_csv("dataset.csv")

print("Dataset loaded successfully!")
print("Total records:", len(df))


# 2. Input features and target
X = df[
    [
        "distance_km",
        "weight_kg",
        "vehicle_type",
        "loading_required",
        "goods_type",
        "traffic_level"
    ]
]

y = df["fare_inr"]


# 3. Categorical and numerical columns
categorical_features = [
    "vehicle_type",
    "loading_required",
    "goods_type",
    "traffic_level"
]

numerical_features = [
    "distance_km",
    "weight_kg"
]


# 4. Preprocessing
preprocessor = ColumnTransformer(
    transformers=[
        (
            "categorical",
            OneHotEncoder(handle_unknown="ignore"),
            categorical_features
        ),
        (
            "numerical",
            "passthrough",
            numerical_features
        )
    ]
)


# 5. Random Forest model
model = RandomForestRegressor(
    n_estimators=100,
    random_state=42
)


# 6. Complete ML pipeline
pipeline = Pipeline(
    steps=[
        ("preprocessor", preprocessor),
        ("model", model)
    ]
)


# 7. Train-test split
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42
)


# 8. Train model
print("Training model...")
pipeline.fit(X_train, y_train)

print("Model training completed!")


# 9. Prediction
y_pred = pipeline.predict(X_test)


# 10. Model evaluation
mae = mean_absolute_error(y_test, y_pred)
r2 = r2_score(y_test, y_pred)

print("--------------------------------")
print("MODEL EVALUATION")
print("--------------------------------")
print("Mean Absolute Error:", round(mae, 2))
print("R2 Score:", round(r2, 4))


# 11. Save trained model
joblib.dump(pipeline, "model.pkl")

print("--------------------------------")
print("Model saved successfully!")
print("File created: model.pkl")