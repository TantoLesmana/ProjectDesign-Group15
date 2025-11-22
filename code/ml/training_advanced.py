import os
import pandas as pd
import tensorflow as tf
from tensorflow.keras import layers, models, optimizers, regularizers
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler


def run_experiment(config, X_train, y_train, X_test, y_test):
    """Trains, evaluates, and saves the model based on the given configuration."""
    
    # Extract settings
    epochs = config['epochs']
    batch_size = config['batch_size']
    tag = config['tag']
    learning_rate = config.get('learning_rate', 0.001)
    l2_reg = config.get('l2_reg', 0.0)
    
    print(f"\n--- Running Experiment: {tag} ---")
    print(f"  | Config: E:{epochs}, B:{batch_size}, LR:{learning_rate}, L2:{l2_reg}")

    # Define the model architecture with L2 Regularization
    model = models.Sequential([
        layers.Dense(16, activation='relu', input_shape=(6,),
                     kernel_regularizer=regularizers.l2(l2_reg)),
        layers.Dense(8, activation='relu',
                     kernel_regularizer=regularizers.l2(l2_reg)),
        layers.Dense(1, activation='sigmoid')
    ])
    
    # Define the optimizer with the specified learning rate
    adam_optimizer = optimizers.Adam(learning_rate=learning_rate)

    # Compile the model
    model.compile(
        optimizer=adam_optimizer,
        loss='binary_crossentropy',
        metrics=['accuracy']
    )

    # Train
    history = model.fit(
        X_train, y_train,
        epochs=epochs,
        batch_size=batch_size,
        validation_split=0.2,
        verbose=0
    )
    
    # Evaluate on test set
    loss, acc = model.evaluate(X_test, y_test, verbose=0)
    print(f"  | Test accuracy: **{acc:.4f}**")
    
    # Save Evaluation Results to a File
    results_path = "experiment_results_corrected.csv"
    results_df = pd.DataFrame({
        'Tag': [tag], 
        'Epochs': [epochs], 
        'Batch_Size': [batch_size], 
        'Learning_Rate': [learning_rate],
        'L2_Regularization': [l2_reg],
        'Test_Accuracy': [acc],
        'Test_Loss': [loss]
    })
    
    header = not os.path.exists(results_path)
    results_df.to_csv(results_path, mode='a', index=False, header=header)

    # Save model and convert to tflite
    saved_model_path = f"models/saved_models/{tag}"
    tflite_path = f"models/tflite_models/{tag}.tflite"

    try:
        model.export(saved_model_path)
        
        converter = tf.lite.TFLiteConverter.from_saved_model(saved_model_path)
        tflite_model = converter.convert()
        
        with open(tflite_path, "wb") as f:
            f.write(tflite_model)
    except Exception as e:
        print(f"Error saving {tag}: {e}")
        
    return acc


df = pd.read_excel(".\dataset\data2.xlsx")

# Analog Data
analog_cols = ["MQ2A", "MQ3A", "MQ4A", "MQ8A", "MQ9A", "MQ135A"]
X = df[analog_cols].values
y = df["output"].values

# Transform Array
scaler = StandardScaler()
X = scaler.fit_transform(X)

# Train-Test Split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Hyperparameter Tuning
configs = [
    # Low Learning Rate, Light Regularization
    {'epochs': 80, 'batch_size': 16, 'learning_rate': 0.0005, 'l2_reg': 0.001, 'tag': 'gentle_80e_5e4lr_L2001'},
    # Slower Learning, More Epochs
    {'epochs': 120, 'batch_size': 16, 'learning_rate': 0.0002, 'l2_reg': 0.001, 'tag': 'slowLR_120e_2e4lr_L2001'},
    # Higher Regularization
    {'epochs': 80, 'batch_size': 16, 'learning_rate': 0.0005, 'l2_reg': 0.01, 'tag': 'highReg_80e_5e4lr_L201'},
]

os.makedirs("models/saved_models", exist_ok=True)
os.makedirs("models/tflite_models", exist_ok=True)

test_accuracies = {}
for config in configs:
    acc = run_experiment(config, X_train, y_train, X_test, y_test)
    test_accuracies[config['tag']] = acc

# Summary
print("\n" + "="*40)
print("--- Summary of Corrected Test Accuracies ---")
print("="*40)

# Identify the best performing tag
best_tag = max(test_accuracies, key=test_accuracies.get)
best_acc = test_accuracies[best_tag]

for tag, acc in test_accuracies.items():
    print(f"**{tag}**: {acc:.4f}{' (BEST)' if tag == best_tag else ''}")
