import itertools
import json
from dataclasses import dataclass


@dataclass
class QuestionWithLO:
    """
    Minimal representation of one (question, learning outcome) pairing —
    just enough to build training pairs from. Building a list of these from
    real DB rows (via get_links_by_question CRUD function) is
    handled in routes/training_pairs.py.
    """
    question_id: str
    question_text: str
    lo_id: str
    concept: str


@dataclass
class TrainingPair:
    question_a_id: str
    question_b_id: str
    label: int  # 1 = similar meaning, 0 = different meaning
    pair_type: str  # "positive" | "negative" | "hard_negative"


def _keyword_overlap(text_a: str, text_b: str) -> float:
    """
    Jaccard similarity between the word sets of two texts — a cheap,
    dependency-free way to detect "similar wording" for hard negatives.
    Not semantic similarity (that's what the embedding model is for);
    this is deliberately just surface-level word overlap.
    """
    words_a = set(text_a.split())
    words_b = set(text_b.split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


def generate_pairs(
    questions: list[QuestionWithLO],
    hard_negative_threshold: float = 0.3,
) -> list[TrainingPair]:
    """
    Build positive / negative / hard-negative training pairs from a list
    of (question, LO) pairings, per team_strategy.md's §8.7 definitions:

    - positive: same LO + same concept, not the exact same question.
    - negative: linked to different LOs.
    - hard_negative: different LOs, but high surface-level word overlap
      (looks similar on the surface, but tests a different outcome).
    """
    pairs: list[TrainingPair] = []

    for q_a, q_b in itertools.combinations(questions, 2):
        if q_a.question_id == q_b.question_id:
            continue

        same_lo = q_a.lo_id == q_b.lo_id
        same_concept = q_a.concept == q_b.concept

        if same_lo and same_concept:
            pairs.append(TrainingPair(
                question_a_id=q_a.question_id,
                question_b_id=q_b.question_id,
                label=1,
                pair_type="positive",
            ))
        elif not same_lo:
            overlap = _keyword_overlap(q_a.question_text, q_b.question_text)
            pair_type = "hard_negative" if overlap >= hard_negative_threshold else "negative"
            pairs.append(TrainingPair(
                question_a_id=q_a.question_id,
                question_b_id=q_b.question_id,
                label=0,
                pair_type=pair_type,
            ))

    return pairs


def export_pairs_jsonl(pairs: list[TrainingPair], path: str) -> None:
    """
    Write pairs to a JSONL file (one JSON object per line) — the format
    sentence-transformers training scripts typically expect.
    """
    with open(path, "w", encoding="utf-8") as f:
        for pair in pairs:
            f.write(json.dumps({
                "question_a_id": pair.question_a_id,
                "question_b_id": pair.question_b_id,
                "label": pair.label,
                "pair_type": pair.pair_type,
            }, ensure_ascii=False) + "\n")