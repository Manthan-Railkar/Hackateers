import os
import pandas as pd
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, accuracy_score
import pickle
import ast
import numpy as np

def train():
    print("Starting classifier training pipeline...")
    data_path = os.path.join("data", "page_dataset.csv")
    if not os.path.exists(data_path):
        print(f"Dataset not found at {data_path}. Cannot proceed.")
        return

    df = pd.read_csv(data_path)
    
    # Assuming features are stored as separate columns feature_0 to feature_32
    feature_cols = [c for c in df.columns if c.startswith("feature_")]
    if not feature_cols:
        # Fallback to eval string arrays if stored in a single column
        if "features" in df.columns:
            df["features_arr"] = df["features"].apply(lambda x: ast.literal_eval(x) if isinstance(x, str) else x)
            X = np.stack(df["features_arr"].values)
        else:
            print("No valid feature columns found.")
            return
    else:
        X = df[feature_cols].values

    y = df["label"].values

    le = LabelEncoder()
    y_encoded = le.fit_transform(y)
    
    X_train, X_test, y_train, y_test = train_test_split(X, y_encoded, test_size=0.2, stratify=y_encoded, random_state=42)

    model = lgb.LGBMClassifier(objective="multiclass", num_class=len(le.classes_), n_estimators=300, max_depth=8)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    print("Accuracy:", accuracy_score(y_test, y_pred))
    print("\nClassification Report:\n", classification_report(y_test, y_pred, target_names=le.classes_))

    os.makedirs("models", exist_ok=True)
    with open("models/page_classifier.pkl", "wb") as f:
        pickle.dump(model, f)
    with open("models/label_encoder.pkl", "wb") as f:
        pickle.dump(le, f)
        
    with open("models/feature_names.pkl", "wb") as f:
        pickle.dump(feature_cols if feature_cols else [f"feature_{i}" for i in range(X.shape[1])], f)

    print("Models saved successfully to 'models/' directory.")

if __name__ == "__main__":
    train()
