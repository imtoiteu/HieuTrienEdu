"""Interchange format converters, and the licence gate that protects them."""

from __future__ import annotations

import pytest

from app.content_io.formats import (
    ImportedQuestion,
    LicenseError,
    parse_gift,
    parse_perseus_item,
    parse_qti,
)
from app.exercise_engine import QuestionTemplate, generate_variant


def build(question: ImportedQuestion) -> QuestionTemplate:
    return QuestionTemplate(
        slug="imported",
        question_type=question.question_type,
        prompt=question.prompt,
        answer_spec=question.answer_spec,
        options=question.options,
    )


class TestGiftImport:
    def test_multiple_choice(self):
        questions = parse_gift("Which number is prime? { ~9 =11 ~15 }")
        assert len(questions) == 1
        question = questions[0]
        assert question.question_type == "multiple_choice"
        assert question.prompt == "Which number is prime?"

        # The imported question must actually generate and grade.
        variant = generate_variant(build(question), seed=1)
        correct = next(
            choice for choice in variant.rendered["choices"]
            if choice["id"] == variant.answer["choice_id"]
        )
        assert correct["label"] == "11"

    def test_true_false(self):
        question = parse_gift("The Earth is flat. {F}")[0]
        assert question.question_type == "true_false"
        assert question.answer_spec["value"] is False

    def test_numeric_with_tolerance(self):
        question = parse_gift("What is 2 + 2? {#4:0.1}")[0]
        assert question.question_type == "numeric"
        assert question.answer_spec["value"] == 4.0
        assert question.answer_spec["tolerance"] == 0.1

    def test_short_answer_with_several_accepted_forms(self):
        question = parse_gift("Capital of Vietnam? { =Hanoi =Hà Nội }")[0]
        assert question.question_type == "short_answer"
        assert "Hanoi" in question.answer_spec["accepted"]

    def test_matching(self):
        question = parse_gift(
            "Match the units. { =Force -> newton =Energy -> joule =Power -> watt }"
        )[0]
        assert question.question_type == "matching"
        assert len(question.options["pairs"]) == 3

    def test_multiple_select_when_several_answers_are_correct(self):
        question = parse_gift("Select the even numbers. { =2 =4 ~3 ~5 }")[0]
        assert question.question_type == "multiple_select"

    def test_titles_and_comments_are_stripped(self):
        source = "// a comment line\n::Question title::What is 1 + 1? {#2}"
        question = parse_gift(source)[0]
        assert question.prompt == "What is 1 + 1?"

    def test_several_questions_in_one_document(self):
        source = "First? {T}\n\nSecond? {F}\n\nThird? {#7}"
        assert len(parse_gift(source)) == 3

    def test_provenance_is_recorded(self):
        question = parse_gift(
            "A? {T}", license="CC-BY-4.0", attribution="Example Author"
        )[0]
        assert question.license == "CC-BY-4.0"
        assert question.attribution == "Example Author"
        assert question.source == "Moodle GIFT import"


class TestLicenceGate:
    def test_permitted_licence_passes(self):
        ImportedQuestion(prompt="x", question_type="true_false", license="CC-BY-4.0")\
            .validate_license()

    @pytest.mark.parametrize("licence", ["AGPL-3.0", "All rights reserved", None, ""])
    def test_other_licences_are_refused(self, licence):
        """An accidental licence violation is far harder to undo than an import that did not happen."""
        with pytest.raises(LicenseError):
            ImportedQuestion(prompt="x", question_type="true_false", license=licence)\
                .validate_license()


class TestQtiImport:
    CHOICE_ITEM = """<?xml version="1.0" encoding="UTF-8"?>
    <assessmentItem identifier="q1" title="Prime">
      <responseDeclaration identifier="RESPONSE" cardinality="single">
        <correctResponse><value>B</value></correctResponse>
      </responseDeclaration>
      <itemBody>
        <p>Which number is prime?</p>
        <choiceInteraction responseIdentifier="RESPONSE" maxChoices="1">
          <simpleChoice identifier="A">9</simpleChoice>
          <simpleChoice identifier="B">11</simpleChoice>
          <simpleChoice identifier="C">15</simpleChoice>
        </choiceInteraction>
      </itemBody>
    </assessmentItem>"""

    TEXT_ITEM = """<?xml version="1.0" encoding="UTF-8"?>
    <assessmentItem identifier="q2" title="Sum">
      <responseDeclaration identifier="RESPONSE" cardinality="single">
        <correctResponse><value>4</value></correctResponse>
      </responseDeclaration>
      <itemBody>
        <p>What is 2 + 2?</p>
        <textEntryInteraction responseIdentifier="RESPONSE"/>
      </itemBody>
    </assessmentItem>"""

    def test_choice_interaction(self):
        question = parse_qti(self.CHOICE_ITEM)
        assert question is not None
        assert question.question_type == "multiple_choice"
        assert question.prompt == "Which number is prime?"
        correct = [c for c in question.options["choices"] if c["correct"]]
        assert len(correct) == 1
        assert correct[0]["label"] == "11"

    def test_text_entry_becomes_numeric_when_the_answer_is_a_number(self):
        question = parse_qti(self.TEXT_ITEM)
        assert question is not None
        assert question.question_type == "numeric"
        assert question.answer_spec["value"] == 4.0

    def test_unsupported_interaction_returns_none_rather_than_mangling_it(self):
        unsupported = """<assessmentItem identifier="q3">
          <responseDeclaration identifier="R"><correctResponse><value>x</value></correctResponse>
          </responseDeclaration>
          <itemBody><p>Draw a graph</p><drawingInteraction responseIdentifier="R"/></itemBody>
        </assessmentItem>"""
        assert parse_qti(unsupported) is None

    def test_malformed_xml_returns_none(self):
        assert parse_qti("<not-closed>") is None


class TestPerseusImport:
    def test_radio_widget(self):
        item = {
            "question": {
                "content": "Which number is prime? [[☃ radio 1]]",
                "widgets": {
                    "radio 1": {
                        "type": "radio",
                        "options": {
                            "choices": [
                                {"content": "9", "correct": False},
                                {"content": "11", "correct": True},
                            ]
                        },
                    }
                },
            },
            "hints": [{"content": "A prime has exactly two factors."}],
        }
        question = parse_perseus_item(item)
        assert question is not None
        assert question.question_type == "multiple_choice"
        # The widget placeholder must be stripped from the prompt.
        assert "☃" not in question.prompt
        assert question.prompt == "Which number is prime?"
        assert question.hints[0]["text"].startswith("A prime")

    def test_numeric_widget(self):
        item = {
            "question": {
                "content": "What is 2 + 2? [[☃ numeric-input 1]]",
                "widgets": {
                    "numeric-input 1": {
                        "type": "numeric-input",
                        "options": {
                            "answers": [{"value": 4, "status": "correct", "maxError": 0.01}]
                        },
                    }
                },
            }
        }
        question = parse_perseus_item(item)
        assert question is not None
        assert question.question_type == "numeric"
        assert question.answer_spec["value"] == 4.0

    def test_unsupported_widget_returns_none(self):
        item = {
            "question": {
                "content": "Plot the line [[☃ interactive-graph 1]]",
                "widgets": {"interactive-graph 1": {"type": "interactive-graph", "options": {}}},
            }
        }
        assert parse_perseus_item(item) is None


class TestGiftExport:
    def test_round_trip_of_a_multiple_choice_question(self):
        """Export then re-import must preserve the question and its correct answer."""
        from app.content_io.formats import to_gift

        class FakeQuestion:
            slug = "test-mc"
            question_type = "multiple_choice"
            prompt = "Which number is prime?"
            variables: dict = {}
            constraints: list = []
            answer_spec: dict = {}
            options = {
                "choices": [
                    {"label": "9", "correct": False},
                    {"label": "11", "correct": True},
                    {"label": "15", "correct": False},
                ]
            }
            hints: list = []
            solution: list = []
            difficulty = 2

        gift = to_gift(FakeQuestion())
        reimported = parse_gift(gift)[0]

        assert reimported.question_type == "multiple_choice"
        assert reimported.prompt == "Which number is prime?"
        correct = [c for c in reimported.options["choices"] if c["correct"]]
        assert len(correct) == 1
        assert correct[0]["label"] == "11"
