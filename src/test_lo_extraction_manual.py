"""Manual smoke test — calls real Gemini API, no mocking. Run directly: python test_lo_extraction_manual.py"""
import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s: %(message)s")

from routes.schemes.educationalContext import (
    DifficultyDistribution,
    EducationalContext,
    QuestionConfig,
)
from routes.schemes.evaluationResult import EvaluationStatus
from graph.graph import run_pipeline
from helpers.db import AsyncSessionLocal

SAMPLE_CONTEXT = EducationalContext(
    subject="Chemistry",
    grade_level="10",
    passage="""نظرية بور لذرة الهيدروجين

يُعَدُّ الضوءُ المصدرَ الرئيسَ للمعلوماتِ التي استندتْ إليها النظرياتُ الحديثةُ في تفسيرِ بنيةِ الذرةِ وتركيبِها؛ فقد لاحظَ العلماءُ في أواخرِ القرنِ التاسعِ عشرَ انبعاثَ الضوءِ من بعضِ العناصرِ عندَ تسخينِها؛ ما دفعَهُمْ إلى دراسةِ الضوءِ وتحليلِهِ، وتوصلوا إلى ارتباطِ سلوكِ العنصرِ بالتوزيعِ الإلكترونيِّ. وقد استندَ نيلز بور إلى نتائجِ هذهِ الدراساتِ في بناءِ نموذجِهِ الكمِّيِّ لذرةِ الهيدروجينِ.

ينقسم الطيف الكهرومغناطيسي إلى قسمين: الطيف المرئي، وهو مدى ضيّق من الأطوال الموجية يتراوح بين 350 نانومتراً و800 نانومتر ويمكن للعين تمييزه. والطيف غير المرئي، الذي يشمل جميع الأطوال الموجية التي يزيد طولها على 800 نانومتر أو يقل عن 350 نانومتر.

عبّر بلانك عن طاقة الفوتون بالعلاقة: E = hv، حيث E طاقة الفوتون بالجول، h ثابت بلانك ويساوي 6.63×10^-34 جول.ثانية، وν تردد الضوء بالهيرتز.

فرضيات نظرية بور: تضمنت نظرية بور افتراضين. الافتراض الأول: يمتلك الإلكترون مقداراً محدداً من الطاقة يساوي طاقة المستوى الموجود فيه، وتحسب طاقة المستوى بالعلاقة En = -RH/n^2 حيث RH ثابت ريدبيرغ ويساوي 2.18×10^-18 جول. الافتراض الثاني: تتغير طاقة الإلكترون عند انتقاله بين مستويات الطاقة، فعند اكتسابه طاقة ينتقل لمستوى أعلى، وعند انتقاله لمستوى أقل ينبعث الضوء على شكل فوتونات، ويحسب فرق الطاقة بالعلاقة |ΔE| = RH(1/n1^2 - 1/n2^2)."""
    ,
    question_config=QuestionConfig(mcq_count=3, true_false_count=2, short_answer_count=2),
    difficulty_distribution=DifficultyDistribution(easy=0.3, medium=0.5, hard=0.2),
)


async def main() -> None:
    async with AsyncSessionLocal() as db:
        final_state = await run_pipeline(SAMPLE_CONTEXT, db)

    learning_outcomes = final_state["learning_outcomes"]
    questions = final_state["questions"]
    resolved_links = final_state["resolved_links"]
    evaluations = final_state["evaluations"]

    accepted = sum(1 for e in evaluations if e.result.status == EvaluationStatus.ACCEPTED)
    needs_review = sum(1 for e in evaluations if e.result.status == EvaluationStatus.NEEDS_REVIEW)
    rejected = sum(1 for e in evaluations if e.result.status == EvaluationStatus.REJECTED)

    print("\n=== Pipeline summary ===")
    print(f"Learning outcomes extracted: {len(learning_outcomes)}")
    print(f"Questions generated:         {len(questions)}")
    print(f"Question-to-LO links:        {len(resolved_links)}")
    print(f"Questions evaluated:         {len(evaluations)}")
    print(f"  accepted:     {accepted}")
    print(f"  needs_review: {needs_review}")
    print(f"  rejected:     {rejected}")
    print(f"\nPersisted questions: {final_state['persisted_questions']}  "
          f"Discarded: {final_state['discarded_count']}")
    print(f"Persisted breakdown: LOs={final_state['persisted_learning_outcomes']} "
          f"links={final_state['persisted_links']} evaluations={final_state['persisted_evaluations']}")


if __name__ == "__main__":
    asyncio.run(main())
