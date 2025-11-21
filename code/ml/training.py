import os
import pandas as pd
import tensorflow as tf
import joblib
from tensorflow.keras import layers, models, regularizers
from tensorflow.keras.layers import LeakyReLU
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler


df = pd.read_excel(".\dataset\data2.xlsx")

# Analog Data
analog_cols = ["MQ2A", "MQ3A", "MQ4A", "MQ8A", "MQ9A", "MQ135A"]
X = df[analog_cols].values
y = df["output"].values

# Train-Test Split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Transform Array
scaler = StandardScaler()
X_train = scaler.fit_transform(X_train)
X_test = scaler.transform(X_test)

# Binary Classifier
model = models.Sequential([
    layers.Dense(16, input_shape=(6,), kernel_regularizer=regularizers.l2(0.01)),
    LeakyReLU(alpha=0.01),
    layers.Dense(8, kernel_regularizer=regularizers.l2(0.01)),
    LeakyReLU(alpha=0.01),
    layers.Dense(1, activation='sigmoid')
])

model.compile(
    optimizer='adam',
    loss='binary_crossentropy',
    metrics=['accuracy']
)

# Train
history = model.fit(
    X_train, y_train,
    epochs=30,
    batch_size=16,
    validation_split=0.2
)

# Evaluate
loss, acc = model.evaluate(X_test, y_test)
print(f"Test accuracy = {acc:.3f}")

# Predict
pred = model.predict(X_test[:5])
print("Predictions:", pred)

# Save model and convert to tflite
model.export("models/saved_models/food_classifier")
converter = tf.lite.TFLiteConverter.from_saved_model("models/saved_models/food_classifier")
tflite_model = converter.convert()

os.makedirs("models/saved_models", exist_ok=True)
os.makedirs("models/tflite_models", exist_ok=True)
os.makedirs("models/scaler", exist_ok=True)

joblib.dump(scaler, 'models/scaler/food_classifier_scaler.pkl')
with open("models/tflite_models/food_classifier.tflite", "wb") as f:
    f.write(tflite_model)
