import gradio as gr
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

LABEL_NAMES = ["World", "Sports", "Business", "Sci/Tech"]

# Load model and tokenizer once at startup — not on every request
model_path = "models/news-classifier/final"
tokenizer = AutoTokenizer.from_pretrained(model_path)
model = AutoModelForSequenceClassification.from_pretrained(model_path)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)
model.eval()  # Disable Dropout for deterministic inference


def predict_topic(text):
    inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=512)
    inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        outputs = model(**inputs)
        # Convert logits to probabilities summing to 1 across 4 categories
        probabilities = torch.nn.functional.softmax(outputs.logits, dim=-1)

    scores = probabilities[0].tolist()
    # Return dict {category: probability} — rendered by gr.Label() as a bar chart
    return {LABEL_NAMES[i]: float(scores[i]) for i in range(len(LABEL_NAMES))}


demo = gr.Interface(
    fn=predict_topic,
    inputs=gr.Textbox(lines=5, placeholder="Paste a news article headline or paragraph..."),
    outputs=gr.Label(num_top_classes=4),
    title="News Topic Classifier",
    description="Classifies a news article into one of four categories: World, Sports, Business, or Sci/Tech.",
    examples=[
        ["NASA launches new telescope to study distant galaxies and black holes."],
        ["The Federal Reserve raised interest rates by 0.25% amid inflation concerns."],
        ["Manchester United defeats Arsenal 3-1 in a thrilling Premier League match."],
        ["World leaders gather at the UN summit to discuss climate change policies."]
    ]
)

if __name__ == "__main__":
    demo.launch()
