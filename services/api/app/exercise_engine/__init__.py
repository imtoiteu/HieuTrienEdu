"""HieuTrienEducation exercise engine.

Public surface:

    template = QuestionTemplate.from_model(question_row)
    variant  = generate_variant(template, seed=12345)   # deterministic
    result   = grade_answer(question.question_type, variant.answer, user_answer)

The engine has no database or web dependencies beyond the ``QuestionType`` enum, so it can be
unit-tested in isolation and reused by content-authoring scripts.
"""

from app.exercise_engine.algebra import (
    AlgebraError,
    expressions_equivalent,
    format_number,
    parse_student_expression,
    to_latex,
)
from app.exercise_engine.distractors import build_choice_set, generate_numeric_distractors
from app.exercise_engine.generator import (
    GeneratedVariant,
    GenerationError,
    QuestionTemplate,
    generate_variant,
)
from app.exercise_engine.graders import (
    AnswerFormatError,
    GradeResult,
    grade_answer,
    parse_number,
)
from app.exercise_engine.safe_eval import ExpressionError, evaluate, evaluate_bool
from app.exercise_engine.sampling import SamplingError, VariableSpec, sample_variables
from app.exercise_engine.templating import TemplateError, render_template

__all__ = [
    "AlgebraError",
    "AnswerFormatError",
    "ExpressionError",
    "GradeResult",
    "GeneratedVariant",
    "GenerationError",
    "QuestionTemplate",
    "SamplingError",
    "TemplateError",
    "VariableSpec",
    "build_choice_set",
    "evaluate",
    "evaluate_bool",
    "expressions_equivalent",
    "format_number",
    "generate_numeric_distractors",
    "generate_variant",
    "grade_answer",
    "parse_number",
    "parse_student_expression",
    "render_template",
    "sample_variables",
    "to_latex",
]
