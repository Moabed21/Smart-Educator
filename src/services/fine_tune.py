import json

from datasets import Dataset
from sentence_transformers import (
    SentenceTransformer,
    SentenceTransformerTrainer,
    SentenceTransformerTrainingArguments,
)
from sentence_transformers.losses import CosineSimilarityLoss

_BASE_MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
_OUTPUT_DIR = "assets/models/fine_tuned_v1"


def load_pairs_jsonl(path: str, question_texts: dict[str, str]) -> Dataset:
    """
    Read a JSONL file produced by pair_generator.export_pairs_jsonl(), and
    resolve each question_id into its actual text via `question_texts`
    (id -> text mapping). Supplying this mapping from the real DB is
    integration work for whoever wires this against real data — not done
    here, since pair_generator only carries question IDs, not full text.
    """
    sentence1, sentence2, scores = [], [], []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            record = json.loads(line)
            text_a = question_texts.get(record["question_a_id"])
            text_b = question_texts.get(record["question_b_id"])
            if text_a is None or text_b is None:
                continue  # skip pairs we can't resolve to real text
            sentence1.append(text_a)
            sentence2.append(text_b)
            scores.append(float(record["label"]))

    return Dataset.from_dict({
        "sentence1": sentence1,
        "sentence2": sentence2,
        "score": scores,
    })


def fine_tune(train_dataset: Dataset, output_dir: str = _OUTPUT_DIR) -> SentenceTransformer:
    """
    Fine-tune the base multilingual model on (sentence1, sentence2, score)
    pairs using CosineSimilarityLoss.

    CosineSimilarityLoss chosen over MultipleNegativesRankingLoss deliberately:
    pair_generator.py already produces explicit positive (score=1) AND
    negative/hard_negative (score=0) pairs. MultipleNegativesRankingLoss only
    trains on (anchor, positive) pairs and generates its own in-batch
    negatives — it would silently ignore the negative/hard_negative pairs
    we went to the trouble of generating. CosineSimilarityLoss uses all of
    them directly.
    """
    model = SentenceTransformer(_BASE_MODEL)
    loss = CosineSimilarityLoss(model)

    args = SentenceTransformerTrainingArguments(
        output_dir=output_dir,
        num_train_epochs=3,
        per_device_train_batch_size=16,
        warmup_ratio=0.1,
        save_strategy="epoch",
    )

    trainer = SentenceTransformerTrainer(
        model=model,
        args=args,
        train_dataset=train_dataset,
        loss=loss,
    )
    trainer.train()

    model.save_pretrained(output_dir)
    return model