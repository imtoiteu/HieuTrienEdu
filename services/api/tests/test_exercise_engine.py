"""Exercise engine: generation, determinism, safety and grading for all nine question types."""

from __future__ import annotations

import pytest

from app.exercise_engine import (
    AnswerFormatError,
    ExpressionError,
    GenerationError,
    QuestionTemplate,
    SamplingError,
    evaluate,
    expressions_equivalent,
    generate_variant,
    grade_answer,
    parse_number,
    render_template,
    sample_variables,
)

# --------------------------------------------------------------------------------------
# safe evaluation
# --------------------------------------------------------------------------------------


class TestSafeEval:
    def test_arithmetic(self):
        assert evaluate("2 + 3 * 4") == 14
        assert evaluate("distance / time", {"distance": 120, "time": 3}) == 40

    def test_allowed_functions(self):
        assert evaluate("sqrt(16)") == 4
        assert evaluate("gcd(12, 18)") == 6
        assert evaluate("round(3.14159, 2)") == 3.14

    def test_comparisons_and_chaining(self):
        assert evaluate("1 < 2 < 3") is True
        assert evaluate("1 < 5 < 3") is False

    @pytest.mark.parametrize(
        "expression",
        [
            "__import__('os').system('echo pwned')",
            "().__class__.__bases__",
            "open('/etc/passwd')",
            "lambda: 1",
            "[x for x in range(10)]",
            "exec('a=1')",
            "eval('1+1')",
            "globals()",
            "(1).__class__",
        ],
    )
    def test_rejects_dangerous_input(self, expression):
        """The evaluator must reject anything outside the arithmetic whitelist."""
        with pytest.raises(ExpressionError):
            evaluate(expression)

    def test_rejects_unknown_variable(self):
        with pytest.raises(ExpressionError):
            evaluate("mystery + 1")

    def test_guards_against_huge_exponents(self):
        with pytest.raises(ExpressionError):
            evaluate("9 ** 999")

    def test_division_by_zero_is_an_expression_error(self):
        with pytest.raises(ExpressionError):
            evaluate("1 / 0")


# --------------------------------------------------------------------------------------
# sampling
# --------------------------------------------------------------------------------------


class TestSampling:
    def test_is_deterministic_for_a_seed(self):
        spec = {"a": {"type": "int", "min": 1, "max": 1000}}
        assert sample_variables(spec, seed=42) == sample_variables(spec, seed=42)

    def test_different_seeds_give_different_draws(self):
        spec = {"a": {"type": "int", "min": 1, "max": 10000}}
        draws = {sample_variables(spec, seed=s)["a"] for s in range(20)}
        assert len(draws) > 5, "sampling should vary across seeds"

    def test_respects_range_and_step(self):
        spec = {"a": {"type": "int", "min": 20, "max": 200, "step": 5}}
        for seed in range(50):
            value = sample_variables(spec, seed=seed)["a"]
            assert 20 <= value <= 200
            assert value % 5 == 0

    def test_applies_constraints(self):
        spec = {
            "distance": {"type": "int", "min": 20, "max": 200, "step": 10},
            "time": {"type": "int", "min": 2, "max": 8},
        }
        for seed in range(30):
            values = sample_variables(spec, ["distance % time == 0"], seed=seed)
            assert values["distance"] % values["time"] == 0

    def test_derived_variables_see_earlier_ones(self):
        spec = {
            "a": {"type": "int", "min": 3, "max": 3},
            "b": {"type": "int", "min": 4, "max": 4},
            "area": {"type": "derived", "expression": "a * b"},
        }
        assert sample_variables(spec, seed=1)["area"] == 12

    def test_choice_variables(self):
        spec = {"unit": {"type": "choice", "choices": ["m", "cm", "km"]}}
        assert sample_variables(spec, seed=7)["unit"] in {"m", "cm", "km"}

    def test_exclusions_are_honoured(self):
        spec = {"a": {"type": "int", "min": 0, "max": 3, "exclude": [0]}}
        for seed in range(40):
            assert sample_variables(spec, seed=seed)["a"] != 0

    def test_unsatisfiable_constraints_raise_clearly(self):
        spec = {"a": {"type": "int", "min": 1, "max": 5}}
        with pytest.raises(SamplingError, match="Could not satisfy"):
            sample_variables(spec, ["a > 100"], seed=1)


# --------------------------------------------------------------------------------------
# templating
# --------------------------------------------------------------------------------------


class TestTemplating:
    def test_simple_substitution(self):
        assert render_template("{{a}} km", {"a": 12}) == "12 km"

    def test_inline_expressions(self):
        assert render_template("{{ a * b }}", {"a": 3, "b": 4}) == "12"

    def test_precision_suffix(self):
        assert render_template("{{ a / b : 2 }}", {"a": 10, "b": 3}) == "3.33"

    def test_leaves_latex_braces_intact(self):
        """The whole reason for the {{...}} syntax: LaTeX must survive untouched."""
        out = render_template(r"\frac{{{a}}}{{{b}}}", {"a": 3, "b": 4})
        assert out == r"\frac{3}{4}"

    def test_latex_without_placeholders_is_unchanged(self):
        text = r"\sqrt{x^2 + y^2}"
        assert render_template(text, {}) == text


# --------------------------------------------------------------------------------------
# generation + grading, per question type
# --------------------------------------------------------------------------------------


def make(**overrides) -> QuestionTemplate:
    base = {
        "slug": "test-question",
        "question_type": "numeric",
        "prompt": "What is the answer?",
    }
    base.update(overrides)
    return QuestionTemplate(**base)


class TestNumeric:
    template = make(
        question_type="numeric",
        prompt="A car travels {{distance}} km in {{time}} hours. What is its average speed?",
        variables={
            "time": {"type": "int", "min": 2, "max": 6},
            "distance": {"type": "int", "min": 20, "max": 300, "step": 10},
        },
        constraints=["distance % time == 0"],
        answer_spec={"expression": "distance / time", "unit": "km/h", "tolerance": 0.001},
    )

    def test_generation_is_reproducible(self):
        a = generate_variant(self.template, seed=99)
        b = generate_variant(self.template, seed=99)
        assert a.variable_values == b.variable_values
        assert a.rendered == b.rendered
        assert a.answer == b.answer

    def test_prompt_is_fully_resolved(self):
        variant = generate_variant(self.template, seed=5)
        assert "{{" not in variant.rendered["prompt"]
        assert str(variant.variable_values["distance"]) in variant.rendered["prompt"]

    def test_answer_is_mathematically_correct(self):
        for seed in range(25):
            variant = generate_variant(self.template, seed=seed)
            expected = variant.variable_values["distance"] / variant.variable_values["time"]
            assert variant.answer["value"] == pytest.approx(expected)

    def test_correct_answer_is_graded_correct(self):
        variant = generate_variant(self.template, seed=3)
        result = grade_answer("numeric", variant.answer, {"value": variant.answer["value"]})
        assert result.is_correct and result.score == 1.0

    def test_wrong_answer_is_graded_incorrect(self):
        variant = generate_variant(self.template, seed=3)
        result = grade_answer("numeric", variant.answer, {"value": variant.answer["value"] + 7})
        assert not result.is_correct and result.score == 0.0

    def test_factor_of_ten_error_gets_specific_feedback(self):
        variant = generate_variant(self.template, seed=3)
        result = grade_answer("numeric", variant.answer, {"value": variant.answer["value"] * 10})
        assert "ten times too large" in result.message

    def test_rendered_payload_never_contains_the_answer(self):
        """Regression guard: the student-facing dict must not leak the answer."""
        variant = generate_variant(self.template, seed=11)
        assert "value" not in variant.rendered
        assert str(variant.answer["value"]) not in str(variant.rendered.get("choices", ""))


class TestNumberParsing:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("42", 42.0),
            ("  3.5 ", 3.5),
            ("3/4", 0.75),
            ("45%", 45.0),
            ("-7", -7.0),
            ("1,5", 1.5),          # Vietnamese decimal comma
            ("1,000", 1000.0),     # English thousands separator
            ("1.234,56", 1234.56), # both separators, comma last -> decimal
            ("1,234.56", 1234.56), # both separators, dot last -> decimal
        ],
    )
    def test_tolerant_number_parsing(self, raw, expected):
        assert parse_number(raw) == pytest.approx(expected)

    def test_rejects_nonsense(self):
        with pytest.raises(AnswerFormatError):
            parse_number("banana")


class TestMultipleChoice:
    template = make(
        question_type="multiple_choice",
        prompt="What is {{a}} + {{b}}?",
        variables={"a": {"type": "int", "min": 2, "max": 20},
                   "b": {"type": "int", "min": 2, "max": 20}},
        answer_spec={"expression": "a + b"},
        options={"distractors": ["a - b", "a * b"], "choice_count": 4},
    )

    def test_produces_four_distinct_choices(self):
        for seed in range(15):
            variant = generate_variant(self.template, seed=seed)
            choices = variant.rendered["choices"]
            assert len(choices) == 4
            assert len({c["label"] for c in choices}) == 4, "distractors must be distinct"

    def test_the_correct_choice_holds_the_right_value(self):
        for seed in range(15):
            variant = generate_variant(self.template, seed=seed)
            correct_id = variant.answer["choice_id"]
            label = next(c["label"] for c in variant.rendered["choices"] if c["id"] == correct_id)
            expected = variant.variable_values["a"] + variant.variable_values["b"]
            assert label == str(expected)

    def test_grading(self):
        variant = generate_variant(self.template, seed=2)
        correct = variant.answer["choice_id"]
        wrong = next(c["id"] for c in variant.rendered["choices"] if c["id"] != correct)
        assert grade_answer("multiple_choice", variant.answer, {"choice_id": correct}).is_correct
        assert not grade_answer("multiple_choice", variant.answer, {"choice_id": wrong}).is_correct

    def test_static_choices(self):
        template = make(
            question_type="multiple_choice",
            prompt="Which is a prime number?",
            options={"choices": [
                {"label": "9", "correct": False},
                {"label": "11", "correct": True},
                {"label": "15", "correct": False},
            ]},
        )
        variant = generate_variant(template, seed=1)
        correct_id = variant.answer["choice_id"]
        label = next(c["label"] for c in variant.rendered["choices"] if c["id"] == correct_id)
        assert label == "11"


class TestMultipleSelect:
    template = make(
        question_type="multiple_select",
        prompt="Select all the forces acting on a falling ball.",
        options={"choices": [
            {"label": "Gravity", "correct": True},
            {"label": "Air resistance", "correct": True},
            {"label": "Magnetism", "correct": False},
            {"label": "Friction with the ground", "correct": False},
        ]},
    )

    def test_exact_selection_is_correct(self):
        variant = generate_variant(self.template, seed=4)
        result = grade_answer("multiple_select", variant.answer,
                              {"choice_ids": variant.answer["choice_ids"]})
        assert result.is_correct and result.score == 1.0

    def test_partial_credit(self):
        variant = generate_variant(self.template, seed=4)
        one = variant.answer["choice_ids"][:1]
        result = grade_answer("multiple_select", variant.answer, {"choice_ids": one})
        assert not result.is_correct
        assert 0 < result.score < 1

    def test_selecting_everything_does_not_score_full_marks(self):
        variant = generate_variant(self.template, seed=4)
        every_id = [c["id"] for c in variant.rendered["choices"]]
        result = grade_answer("multiple_select", variant.answer, {"choice_ids": every_id})
        assert not result.is_correct
        assert result.score == 0.0


class TestExpression:
    template = make(
        question_type="expression",
        prompt="Expand {{a}}(x + {{b}}).",
        variables={"a": {"type": "int", "min": 2, "max": 9},
                   "b": {"type": "int", "min": 2, "max": 9}},
        answer_spec={"expression": "{{a}}*x + {{a*b}}", "symbols": ["x"]},
    )

    def test_equivalent_forms_are_accepted(self):
        variant = generate_variant(self.template, seed=8)
        a = variant.variable_values["a"]
        b = variant.variable_values["b"]
        for written in [f"{a}x + {a*b}", f"{a*b} + {a}x", f"{a}*(x+{b})"]:
            result = grade_answer("expression", variant.answer, {"value": written})
            assert result.is_correct, f"{written} should be accepted"

    def test_wrong_expression_is_rejected(self):
        variant = generate_variant(self.template, seed=8)
        a = variant.variable_values["a"]
        result = grade_answer("expression", variant.answer, {"value": f"{a}x"})
        assert not result.is_correct

    def test_malicious_input_is_rejected_not_executed(self):
        variant = generate_variant(self.template, seed=8)
        result = grade_answer("expression", variant.answer,
                              {"value": "__import__('os').system('id')"})
        assert not result.is_correct
        assert "could not read" in result.message.lower()


class TestOtherTypes:
    def test_true_false(self):
        template = make(
            question_type="true_false",
            prompt="Is {{n}} even?",
            variables={"n": {"type": "int", "min": 1, "max": 100}},
            answer_spec={"expression": "n % 2 == 0"},
        )
        for seed in range(10):
            variant = generate_variant(template, seed=seed)
            expected = variant.variable_values["n"] % 2 == 0
            assert variant.answer["value"] is expected
            assert grade_answer("true_false", variant.answer, {"value": expected}).is_correct

    def test_fill_blank_partial_credit(self):
        template = make(
            question_type="fill_blank",
            prompt="{{a}} + {{b}} = [[1]], and {{a}} - {{b}} = [[2]]",
            variables={"a": {"type": "int", "min": 10, "max": 20},
                       "b": {"type": "int", "min": 1, "max": 9}},
            options={"blanks": [
                {"id": "1", "type": "numeric", "expression": "a + b"},
                {"id": "2", "type": "numeric", "expression": "a - b"},
            ]},
        )
        variant = generate_variant(template, seed=6)
        a, b = variant.variable_values["a"], variant.variable_values["b"]

        full = grade_answer("fill_blank", variant.answer, {"blanks": {"1": a + b, "2": a - b}})
        assert full.is_correct and full.score == 1.0

        half = grade_answer("fill_blank", variant.answer, {"blanks": {"1": a + b, "2": 0}})
        assert not half.is_correct and half.score == 0.5

    def test_matching(self):
        template = make(
            question_type="matching",
            prompt="Match each quantity to its SI unit.",
            options={"pairs": [
                {"left": "Force", "right": "newton"},
                {"left": "Energy", "right": "joule"},
                {"left": "Power", "right": "watt"},
            ]},
        )
        variant = generate_variant(template, seed=3)
        assert len(variant.rendered["left"]) == 3
        assert len(variant.rendered["right"]) == 3

        correct = grade_answer("matching", variant.answer,
                               {"mapping": variant.answer["mapping"]})
        assert correct.is_correct

        broken = dict(variant.answer["mapping"])
        broken["l1"] = "r_wrong"
        partial = grade_answer("matching", variant.answer, {"mapping": broken})
        assert not partial.is_correct and partial.score == pytest.approx(2 / 3)

    def test_ordering_is_shuffled_and_graded(self):
        template = make(
            question_type="ordering",
            prompt="Order these steps for solving 2x + 3 = 11.",
            options={"items": [
                "Subtract 3 from both sides",
                "Divide both sides by 2",
                "State x = 4",
            ]},
        )
        variant = generate_variant(template, seed=9)
        presented = [item["id"] for item in variant.rendered["items"]]
        assert presented != variant.answer["order"], "presented order must differ from the answer"

        assert grade_answer("ordering", variant.answer,
                            {"order": variant.answer["order"]}).is_correct

    def test_short_answer_keywords(self):
        template = make(
            question_type="short_answer",
            prompt="Why does a heavier object not fall faster in a vacuum?",
            answer_spec={
                "accepted": ["Because there is no air resistance"],
                "keywords": ["air resistance", "gravity"],
                "min_keywords": 1,
            },
        )
        variant = generate_variant(template, seed=1)
        assert grade_answer("short_answer", variant.answer,
                            {"value": "because there is NO air resistance"}).is_correct
        assert grade_answer("short_answer", variant.answer,
                            {"value": "there is no air resistance in a vacuum"}).is_correct
        assert not grade_answer("short_answer", variant.answer,
                                {"value": "because it is heavy"}).is_correct


class TestAlgebraEquivalence:
    @pytest.mark.parametrize(
        ("a", "b"),
        [
            ("2x + 6", "2*(x+3)"),
            ("x^2 - 1", "(x-1)(x+1)"),
            ("1/2 x", "x/2"),
            ("3 + x", "x + 3"),
        ],
    )
    def test_equivalent(self, a, b):
        assert expressions_equivalent(a, b)

    @pytest.mark.parametrize(("a", "b"), [("2x + 6", "2x + 5"), ("x^2", "x^3")])
    def test_not_equivalent(self, a, b):
        assert not expressions_equivalent(a, b)


class TestErrorHandling:
    def test_unknown_question_type(self):
        with pytest.raises(GenerationError, match="Unsupported question type"):
            generate_variant(make(question_type="telepathy"), seed=1)

    def test_missing_answer_spec(self):
        with pytest.raises(GenerationError):
            generate_variant(make(question_type="numeric", answer_spec={}), seed=1)

    def test_empty_submission_is_a_format_error(self):
        template = make(question_type="numeric", answer_spec={"value": 5})
        variant = generate_variant(template, seed=1)
        with pytest.raises(AnswerFormatError):
            grade_answer("numeric", variant.answer, {"value": ""})
