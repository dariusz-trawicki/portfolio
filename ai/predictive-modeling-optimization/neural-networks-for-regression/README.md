# Multivariate Regression with a Neural Network (PyTorch)

This project demonstrates **multivariate regression** (3 features → 1 target) using **scikit-learn** for synthetic data generation and preprocessing, and **PyTorch** for training a simple neural network model.

Although we call it a “neural network”, the model is a **single linear layer**, equivalent to a classic linear regression:

y ≈ w1·x1 + w2·x2 + w3·x3 + b

---

## What’s inside
- **Data generation:** `sklearn.datasets.make_regression`
- **Train/test split:** `train_test_split`
- **Feature scaling:** `StandardScaler`
- **Model:** `nn.Linear(3, 1)` (linear regression in PyTorch)
- **Loss function:** Mean Squared Error (`MSELoss`)
- **Optimizer:** Stochastic Gradient Descent (`SGD`)
- **Evaluation metrics:** RMSE, MAE, R²

---

## Pipeline / Algorithm

### 1. Generate data (`make_regression`)
- `X` shape: `(1000, 3)` → 1000 samples, 3 features  
- `y` shape: `(1000,)` → one target value per sample

### 2. Rename and rescale features
- Map columns to:
  - `Research = X[:, 0]`
  - `Salaries = X[:, 1]`
  - `Infrastructure = X[:, 2]`
- Optionally rescale values to more realistic numeric ranges.

### 3. Build a Pandas DataFrame
- Combine all features and the target into a single table for inspection and visualization.

### 4. Standardize features
- Apply `StandardScaler` to normalize input features using statistics from the training set.

### 5. Convert data to PyTorch tensors
```python
X_train = torch.tensor(X_train, dtype=torch.float32)
y_train = torch.tensor(y_train, dtype=torch.float32)
```

### 6. Define the model (linear neural network)
```python
model = nn.Sequential(
    nn.Linear(3, 1),
)
```

### 7. Define loss function and optimizer
```python
lossfunc = nn.MSELoss()
optimizer = torch.optim.SGD(model.parameters(), lr=0.01)
```

### 8. Train the model
- Forward pass to compute predictions
- Compute loss (MSE)
- Backpropagation
- Update weights using SGD

### 9. Evaluate the model
- **RMSE:** √MSE  
- **MAE:** mean(|y − ŷ|)  
- **R²:** 1 − SS_res / SS_tot

---

## Notes
- The dataset is synthetic and generated from a linear model, which is why very high R² scores (≈1.0) are expected.
- This example focuses on clarity and learning the workflow, not on deep or nonlinear models.

## RUN

```bash
conda create -p ./venv python=3.12 -y
conda activate ./venv
pip install -r requirements.txt
```

#### CLEAN UP ####

```bash
conda deactivate
conda remove -p ./venv --all -y
```
