import numpy as np
from datasets import load_from_disk
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    TrainingArguments,
    Trainer,
    EvalPrediction
)
import evaluate

LABEL_NAMES = ["World", "Sports", "Business", "Sci/Tech"]
NUM_LABELS = len(LABEL_NAMES)


def compute_metrics(pred: EvalPrediction):
    accuracy = evaluate.load("accuracy")
    f1 = evaluate.load("f1")

    logits, labels = pred.predictions, pred.label_ids
    predictions = np.argmax(logits, axis=-1)

    accuracy_score = accuracy.compute(predictions=predictions, references=labels)["accuracy"]
    # Weighted F1 — accounts for class imbalance when averaging across 4 categories
    f1_score = f1.compute(predictions=predictions, references=labels, average="weighted")["f1"]

    return {"accuracy": accuracy_score, "f1": f1_score}


def train_model():
    train_dataset = load_from_disk("data/train")
    test_dataset = load_from_disk("data/test")

    model_name = "distilbert-base-uncased"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    # num_labels=4 adds a Dense head (hidden_size → 4) with random weights on top of DistilBERT
    model = AutoModelForSequenceClassification.from_pretrained(model_name, num_labels=NUM_LABELS)

    # Closure — captures `tokenizer` from the enclosing scope automatically
    def tokenize_function(examples):
        return tokenizer(examples["text"], padding="max_length", truncation=True)

    # remove_columns drops "text" so the Trainer does not warn about unknown columns
    tokenized_train = train_dataset.map(tokenize_function, batched=True).remove_columns(["text"])
    tokenized_test = test_dataset.map(tokenize_function, batched=True).remove_columns(["text"])

    training_args = TrainingArguments(
        output_dir="models/news-classifier",
        per_device_train_batch_size=16,
        per_device_eval_batch_size=16,
        num_train_epochs=4,             # More epochs than binary sentiment — 4 classes need more training
        weight_decay=0.01,              # L2 regularisation to prevent overfitting
        logging_dir="./logs",
        logging_steps=10,
        eval_strategy="epoch",          # Evaluate after every epoch to track progress
        save_strategy="epoch",
        load_best_model_at_end=True,    # Restore the best checkpoint, not the last one
        metric_for_best_model="f1",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_train,
        eval_dataset=tokenized_test,
        compute_metrics=compute_metrics,
    )

    trainer.train()

    model_path = "models/news-classifier/final"
    trainer.save_model(model_path)
    tokenizer.save_pretrained(model_path)

    eval_results = trainer.evaluate()
    print(f"Evaluation results: {eval_results}")

    return model_path


if __name__ == "__main__":
    train_model()
