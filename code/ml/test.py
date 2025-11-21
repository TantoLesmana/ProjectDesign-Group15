import numpy as np
import pandas as pd
import tensorflow as tf
import joblib


MODEL = "./models/tflite_models/food_classifier.tflite"
SCALER = "./models/scaler/food_classifier_scaler.pkl"
# DATASET = "./code/ml/mq_sensors_log_ktinos_mera1.csv"
DATASET = "./dataset/data2.xlsx"
TRAINING_COLUMNS = ["MQ2A", "MQ3A", "MQ4A", "MQ8A", "MQ9A", "MQ135A"]


# Load the TFLite model and allocate tensors.
interpreter = tf.lite.Interpreter(model_path=MODEL)
interpreter.allocate_tensors()

# Get input and output tensor details.
input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()

# input data
# df = pd.read_csv(DATASET)
df = pd.read_excel(DATASET)
feature_columns = ['Raw_value_MQ2', 'Raw_value_MQ3', 'Raw_value_MQ4', 'Raw_value_MQ135',
                   'Raw_value_MQ6', 'Raw_value_MQ7', 'Raw_value_MQ8', 'Raw_value_MQ9']
NEW_INPUT_MAP = {
    'Raw_value_MQ2': 'MQ2A',
    'Raw_value_MQ3': 'MQ3A',
    'Raw_value_MQ4': 'MQ4A',
    'Raw_value_MQ8': 'MQ8A',
    'Raw_value_MQ9': 'MQ9A',
    'Raw_value_MQ135': 'MQ135A'
}
# df.rename(columns=NEW_INPUT_MAP, inplace=True)
raw_features = df[TRAINING_COLUMNS].values

# Load trained scaler
scaler = joblib.load(SCALER)
scaled_features = scaler.transform(raw_features)
input_index = input_details[0]['index']
all_scaled_features = scaled_features.astype(input_details[0]['dtype'])

all_predictions = []

# Loop through each row of your data (1448 times)
for single_sample in all_scaled_features:
    # Reshape Input
    input_data = single_sample.reshape(1, len(TRAINING_COLUMNS)).astype(np.float32)

    # Set Tensor
    interpreter.set_tensor(input_index, input_data)

    # Run the model
    interpreter.invoke()

    # Get the prediction
    prediction = interpreter.get_tensor(output_details[0]['index'])
    all_predictions.append(prediction)

# Combine all the predictions into a single array
final_predictions = np.vstack(all_predictions)
print("Model Output:\n", final_predictions)