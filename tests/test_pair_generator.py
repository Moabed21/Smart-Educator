from services.pair_generator import (
    QuestionWithLO,
    _keyword_overlap,
    generate_pairs,
)


def test_keyword_overlap():
    text1 = "ما هي عاصمة فرنسا"
    text2 = "ما هي عاصمة إيطاليا"
    # Overlap: {"ما", "هي", "عاصمة"} / {"ما", "هي", "عاصمة", "فرنسا", "إيطاليا"} = 3/5 = 0.6
    overlap = _keyword_overlap(text1, text2)
    assert overlap == 0.6


def test_keyword_overlap_empty():
    assert _keyword_overlap("", "hello world") == 0.0


def test_generate_positive_pair():
    q1 = QuestionWithLO(
        question_id="Q1",
        question_text="وضح مفهوم الانكسار الضوئي",
        lo_id="LO_001",
        concept="انكسار الضوء",
    )
    q2 = QuestionWithLO(
        question_id="Q2",
        question_text="ماذا يحدث للضوء عند مروره بين وسطين شفافين",
        lo_id="LO_001",
        concept="انكسار الضوء",
    )
    pairs = generate_pairs([q1, q2])
    assert len(pairs) == 1
    assert pairs[0].label == 1
    assert pairs[0].pair_type == "positive"


def test_generate_negative_pair():
    q1 = QuestionWithLO(
        question_id="Q1",
        question_text="ما هي سرعة الضوء في الفراغ",
        lo_id="LO_001",
        concept="سرعة الضوء",
    )
    q2 = QuestionWithLO(
        question_id="Q2",
        question_text="احسب تسارع الجاذبية الأرضية للكرة",
        lo_id="LO_002",
        concept="الجاذبية",
    )
    pairs = generate_pairs([q1, q2])
    assert len(pairs) == 1
    assert pairs[0].label == 0
    assert pairs[0].pair_type == "negative"


def test_generate_hard_negative_pair():
    # Different LO, but high wording overlap
    q1 = QuestionWithLO(
        question_id="Q1",
        question_text="ما هي أهمية عملية البناء الضوئي في النباتات الخضراء",
        lo_id="LO_001",
        concept="البناء الضوئي",
    )
    q2 = QuestionWithLO(
        question_id="Q2",
        question_text="ما هي أهمية عملية التنفس الخلوي في النباتات الخضراء",
        lo_id="LO_002",
        concept="التنفس الخلوي",
    )
    pairs = generate_pairs([q1, q2], hard_negative_threshold=0.3)
    assert len(pairs) == 1
    assert pairs[0].label == 0
    assert pairs[0].pair_type == "hard_negative"
