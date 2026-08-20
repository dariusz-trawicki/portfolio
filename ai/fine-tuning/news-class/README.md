# News Topic Classifier

A fine-tuned **DistilBERT** model for multi-class classification of news articles into four topic categories, built with Hugging Face Transformers and served via a Gradio web interface.

---

## Overview

This project fine-tunes a pre-trained DistilBERT model on the [AG News dataset](https://huggingface.co/datasets/sh0416/ag_news) to classify news articles into one of four categories:

| Label | Category |
|-------|----------|
| 0     | World    |
| 1     | Sports   |
| 2     | Business |
| 3     | Sci/Tech |

It covers the full ML pipeline: data preparation → training → evaluation → interactive demo.

```
prepare_dataset.py  →  train_model.py  →  evaluate_model.py  →  app.py
```

---

## Project Structure

```
news-topic-classifier/
├── prepare_dataset.py    # Download and balance the AG News dataset
├── train_model.py        # Fine-tune DistilBERT for 4-class classification
├── evaluate_model.py     # Evaluate model, generate confusion matrix
├── app.py                # Gradio web interface
├── pyproject.toml        # Dependencies (uv)
├── data/
│   ├── train/            # Saved training set (Arrow format)
│   └── test/             # Saved test set (Arrow format)
└── models/
    └── news-classifier/
        └── final/        # Saved model weights and tokenizer
```

---

## Dataset

AG News contains 120,000 training and 7,600 test articles evenly distributed across 4 topic categories.

| Split | World | Sports | Business | Sci/Tech | Total |
|-------|-------|--------|----------|----------|-------|
| Train | 1,000 | 1,000  | 1,000    | 1,000    | 4,000 |
| Test  | 250   | 250    | 250      | 250      | 1,000 |

All splits are **balanced** — equal sample count per class — to prevent the model from being biased toward any single category.

> A smaller subset is used compared to the full dataset to keep training time reasonable on a laptop. The full dataset can be used by increasing `size_per_class` in `prepare_dataset.py`.

---

## Model

| Property         | Value                       |
|------------------|-----------------------------|
| Base model       | `distilbert-base-uncased`   |
| Parameters       | ~66M                        |
| Task             | Multi-class text classification |
| Number of labels | 4                           |
| Max input length | 512 tokens                  |

DistilBERT is a distilled version of BERT — 40% fewer parameters, 60% faster, while retaining ~97% of BERT's accuracy. The classification head (a linear Dense layer mapping `hidden_size → 4`) is randomly initialised and learned during fine-tuning.

---

## Requirements

- Python >= 3.10
- [uv](https://github.com/astral-sh/uv) package manager

---

## Quick Start

### 1. Install dependencies

```bash
uv sync
```

### 2. Prepare the dataset

```bash
uv run python prepare_dataset.py
```

Downloads the AG News dataset from Hugging Face Hub, creates a balanced subset for each class, and saves both splits to `data/`.

Sample output:
```
Train dataset size: 4000
Test dataset size:  1000
  World:    1000 samples
  Sports:   1000 samples
  Business: 1000 samples
  Sci/Tech: 1000 samples
```

### 3. Train the model

```bash
uv run python train_model.py
```

Fine-tunes DistilBERT for 4 epochs. Evaluates after every epoch and saves the best checkpoint (by F1 score) to `models/news-classifier/final/`.

### 4. Evaluate the model

```bash
uv run python evaluate_model.py
```

Prints a per-class classification report and saves a 4×4 confusion matrix heatmap to `confusion_matrix.png`.

### 5. Launch the web app

```bash
uv run python app.py
```

Opens a Gradio interface at [http://127.0.0.1:7860](http://127.0.0.1:7860).

---

## Training Configuration

| Hyperparameter              | Value     |
|-----------------------------|-----------|
| Epochs                      | 4         |
| Batch size (train)          | 16        |
| Batch size (eval)           | 16        |
| Weight decay                | 0.01      |
| Evaluation strategy         | per epoch |
| Best model selection metric | F1        |

> 4 epochs instead of 3 (as in binary sentiment) because distinguishing 4 topic categories requires more training iterations.

---

## Expected Results

| Metric   | Value |
|----------|-------|
| Accuracy | ~87%  |
| F1 score | ~87%  |

> Results may vary slightly depending on hardware and random seed. AG News is harder than for example `binary sentiment classification` — some categories overlap (e.g. Business vs World for economic/political news).

---

## Confusion Matrix

Generated automatically by `evaluate_model.py` and saved as `confusion_matrix.png`.

A 4×4 heatmap — rows represent true labels, columns represent predicted labels. A perfect model has values only on the diagonal.

Common confusion patterns in AG News:
- **Business ↔ World** — economic and geopolitical stories share vocabulary
- **Sci/Tech ↔ Business** — tech company news appears in both categories

---

## Web Interface

The Gradio app accepts a news article headline or paragraph and returns confidence scores for all four categories:

```
Input : "NASA launches new telescope to study distant galaxies."
Output: Sci/Tech  91%
        World      5%
        Business   3%
        Sports     1%
```

Pre-loaded examples covering all four categories are available in the interface for quick testing.

---

## Difference vs Binary Sentiment Classifier

This project extends the binary IMDB sentiment classifier to a 4-class problem. Key differences:

| Aspect               | IMDB Sentiment       | AG News Topic         |
|----------------------|----------------------|-----------------------|
| Number of classes    | 2                    | 4                     |
| Dataset size (train) | 5,000                | 4,000                 |
| Training epochs      | 3                    | 4                     |
| Confusion matrix     | 2×2                  | 4×4                   |
| Gradio output        | top-2 classes        | top-4 classes         |
| Main challenge       | tone detection       | topic disambiguation  |

---

## Dependencies

| Package       | Purpose                          |
|---------------|----------------------------------|
| torch         | Neural network framework         |
| transformers  | DistilBERT model and tokenizer   |
| datasets      | AG News loading and caching      |
| evaluate      | Accuracy and F1 metrics          |
| gradio        | Web interface                    |
| scikit-learn  | Confusion matrix and report      |
| accelerate    | Distributed training support     |
| matplotlib    | Confusion matrix plot            |
| seaborn       | Heatmap styling                  |
