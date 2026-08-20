from datasets import load_dataset, concatenate_datasets
import os
from collections import Counter

LABEL_NAMES = {0: "World", 1: "Sports", 2: "Business", 3: "Sci/Tech"}
NUM_LABELS = len(LABEL_NAMES)


def prepare_dataset():
    # Load AG News from Hugging Face Hub (120k train / 7.6k test articles, 4 categories)
    dataset = load_dataset("ag_news")
    dataset = dataset.shuffle(seed=42)

    def balance_subset(ds, size_per_class):
        subsets = []
        for label_id in range(NUM_LABELS):
            subset = ds.filter(lambda example, lid=label_id: example["label"] == lid)
            subsets.append(subset.select(range(size_per_class)))
        # Shuffle after concatenation to avoid class ordering bias during training
        return concatenate_datasets(subsets).shuffle(seed=42)

    # 1000 articles × 4 classes = 4000 training samples
    train_dataset = balance_subset(dataset["train"], 1000)
    # 250 articles × 4 classes = 1000 test samples
    test_dataset = balance_subset(dataset["test"], 250)

    os.makedirs("data/train", exist_ok=True)
    os.makedirs("data/test", exist_ok=True)

    train_dataset.save_to_disk("data/train")
    test_dataset.save_to_disk("data/test")

    print(f"Train dataset size: {len(train_dataset)}")
    print(f"Test dataset size:  {len(test_dataset)}")

    label_dist = Counter(train_dataset["label"])
    for label_id, count in sorted(label_dist.items()):
        print(f"  {LABEL_NAMES[label_id]}: {count} samples")

    return train_dataset, test_dataset


if __name__ == "__main__":
    prepare_dataset()
