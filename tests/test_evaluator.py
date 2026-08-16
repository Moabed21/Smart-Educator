from routes.schemes.evaluationResult import EvaluationStatus
from services.evaluator import _CriteriaScores, _compute_overall_score, _compute_status


def test_compute_overall_score_non_mcq():
    scores = _CriteriaScores(
        context_grounding_score=0.8,
        clarity_score=0.9,
        answer_correctness_score=1.0,
        explanation_correctness_score=0.9,
        learning_outcome_alignment_score=0.8,
        difficulty_score=0.7,
        question_type_validity_score=0.9,
        choices_validity_score=None,
    )
    # 7 always-on fields sum = 6.0 / 7 = 0.8571
    overall = _compute_overall_score(scores, is_mcq=False)
    assert round(overall, 4) == round(6.0 / 7, 4)


def test_compute_overall_score_mcq():
    scores = _CriteriaScores(
        context_grounding_score=1.0,
        clarity_score=1.0,
        answer_correctness_score=1.0,
        explanation_correctness_score=1.0,
        learning_outcome_alignment_score=1.0,
        difficulty_score=1.0,
        question_type_validity_score=1.0,
        choices_validity_score=1.0,
    )
    overall = _compute_overall_score(scores, is_mcq=True)
    assert overall == 1.0


def test_compute_status_accepted():
    status = _compute_status(overall_score=0.85, answer_correctness_score=0.9)
    assert status == EvaluationStatus.ACCEPTED


def test_compute_status_needs_review():
    status = _compute_status(overall_score=0.65, answer_correctness_score=0.8)
    assert status == EvaluationStatus.NEEDS_REVIEW


def test_compute_status_rejected_low_overall():
    status = _compute_status(overall_score=0.45, answer_correctness_score=0.8)
    assert status == EvaluationStatus.REJECTED


def test_compute_status_factuality_override():
    # Even if overall is high (0.80), a wrong answer (<0.5) must force status to REJECTED
    status = _compute_status(overall_score=0.80, answer_correctness_score=0.4)
    assert status == EvaluationStatus.REJECTED
