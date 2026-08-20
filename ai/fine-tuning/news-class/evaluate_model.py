import torch
from datasets import load_from_disk
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from sklearn.metrics import confusion_matrix, classification_report
import matplotlib.pyplot as plt
import seaborn as sns

LABEL_NAMES = ["World", "Sports", "Business", "Sci/Tech"]


def evaluate_model():
    test_dataset = load_from_disk("data/test")

    model_path = "models/news-classifier/final"
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForSequenceClassification.from_pretrained(model_path)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()  # Disable Dropout for deterministic results

    def tokenize_function(examples):
        return tokenizer(examples["text"], padding="max_length", truncation=True, return_tensors="pt")

    all_predictions = []
    all_labels = []

    with torch.no_grad():
        for i in range(0, len(test_dataset), 32):
            batch = test_dataset[i:i + 32]
            inputs = tokenize_function(batch)
            inputs = {k: v.to(device) for k, v in inputs.items()}

            outputs = model(**inputs)
            # outputs.logits shape: (batch_size, 4) — one score per category
            predictions = torch.argmax(outputs.logits, dim=-1).cpu().numpy()

            all_predictions.extend(predictions)
            all_labels.extend(batch["label"])

    # 4×4 confusion matrix — diagonal = correct predictions, off-diagonal = mistakes
    cm = confusion_matrix(all_labels, all_predictions)
    report = classification_report(all_labels, all_predictions, target_names=LABEL_NAMES, zero_division=0)

    print("Confusion Matrix:")
    print(cm)
    print("\nClassification Report:")
    print(report)

    plt.figure(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", xticklabels=LABEL_NAMES, yticklabels=LABEL_NAMES)
    plt.xlabel("Predicted Label")
    plt.ylabel("True Label")
    plt.title("Confusion Matrix — News Topic Classification")
    plt.tight_layout()
    plt.savefig("confusion_matrix.png")
    plt.close()

    # Qualitative review — check whether mistakes are logical (e.g. Business ↔ World)
    print("\nExample Predictions:")
    for i in range(min(10, len(test_dataset))):
        example = test_dataset[i]
        true = LABEL_NAMES[example["label"]]
        predicted = LABEL_NAMES[all_predictions[i]]
        match = "✓" if true == predicted else "✗"
        print(f"{match} True: {true:10} | Predicted: {predicted:10} | {example['text'][:80]}...")
        print("-" * 80)

    return all_predictions, all_labels


if __name__ == "__main__":
    evaluate_model()
