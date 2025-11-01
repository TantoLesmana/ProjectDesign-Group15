import numpy as np
import pandas as pd
import tensorflow as tf


# 1. Load the TFLite model and allocate tensors.
interpreter = tf.lite.Interpreter(model_path="code/ml/food_model_ktinos.tflite")
interpreter.allocate_tensors()

# 2. Get input and output tensor details.
input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()

# input data
df = pd.read_csv("code/ml/mq_sensors_log_ktinos_mera1.csv")
feature_columns = ['Raw_value_MQ2', 'Raw_value_MQ3', 'Raw_value_MQ4', 'Raw_value_MQ135',
                   'Raw_value_MQ6', 'Raw_value_MQ7', 'Raw_value_MQ8', 'Raw_value_MQ9']
raw_features = df[feature_columns].values

max_value = 65535.0  # Common max for 16-bit raw sensor data
scaled_features = raw_features / max_value
input_index = input_details[0]['index']
all_scaled_features = scaled_features.astype(input_details[0]['dtype'])

# # Assuming your model has one input tensor at index 0
# input_shape = input_details[0]['shape']

# # 3. Prepare your input data (replace this with your actual test data)
# # This example creates random data matching the model's expected shape and dtype.
# input_data = np.array(np.random.random_sample(input_shape), dtype=np.float32)

# 4. Set the tensor, invoke the interpreter, and get the output.
# print(len(input_data))

all_predictions = []

# Loop through each row of your data (1448 times)
for single_sample in all_scaled_features:
    # 1. Reshape the 1D sample (8,) into the required 2D input shape (1, 8)
    # and ensure it's the correct float32 type.
    input_data = single_sample.reshape(1, 8).astype(np.float32)

    # 2. Set the tensor for the single sample
    # The 'ValueError' will now be fixed because input_data.shape[0] is 1
    interpreter.set_tensor(input_index, input_data)

    # 3. Run the model
    interpreter.invoke()

    # 4. Get the prediction
    prediction = interpreter.get_tensor(output_details[0]['index'])
    all_predictions.append(prediction)

# Combine all the predictions into a single array (e.g., shape 1448, 2)
final_predictions = np.vstack(all_predictions)

# 5. Interpret the output
print("Model Output:\n", final_predictions)