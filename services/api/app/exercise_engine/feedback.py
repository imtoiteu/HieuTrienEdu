"""Localised grading feedback.

The message a student reads after submitting an answer is content, not chrome: "your answer is ten
times too large — check your decimal point" is the most useful sentence on the page, and a
Vietnamese student who gets it in English gets nothing from it.

Graders stay pure and language-free. Each one emits a stable **key** plus the numbers that go into
the sentence, and the key is turned into prose here, once, at the edge — the same separation that
keeps ``answer_spec`` out of the translation layer. Adding a language is a new column in this
table; it never touches grading logic.

Format strings use ``str.format`` placeholders, so a translator can reorder them freely: Vietnamese
puts the count after the noun in a way English does not.
"""

from __future__ import annotations

from typing import Any

from app.core.i18n import DEFAULT_LOCALE

__all__ = [
    "FEEDBACK",
    "FORMAT_ERRORS",
    "RECOMMENDATION_REASONS",
    "render_feedback",
    "render_format_error",
    "render_recommendation",
]


FEEDBACK: dict[str, dict[str, str]] = {
    "correct": {
        "en": "Correct!",
        "vi": "Chính xác!",
    },
    "correct_order": {
        "en": "Correct order!",
        "vi": "Thứ tự đúng!",
    },
    "correct_equivalent": {
        "en": "Correct — that is equivalent.",
        "vi": "Chính xác — biểu thức này tương đương.",
    },
    "wrong_generic": {
        "en": "Not quite.",
        "vi": "Chưa đúng.",
    },
    "wrong_review_solution": {
        "en": "Not quite — review the worked solution.",
        "vi": "Chưa đúng — em hãy xem lại lời giải chi tiết.",
    },
    "wrong_work_through_steps": {
        "en": "Not quite — work through the solution steps.",
        "vi": "Chưa đúng — em hãy làm lại theo từng bước của lời giải.",
    },
    "wrong_order": {
        "en": "Not the right order yet.",
        "vi": "Thứ tự vẫn chưa đúng.",
    },
    "not_equivalent": {
        "en": "That expression is not equivalent to the answer.",
        "vi": "Biểu thức này không tương đương với đáp án.",
    },
    "ten_times_too_large": {
        "en": "Close — your answer is ten times too large. Check your units or decimal point.",
        "vi": (
            "Gần đúng rồi — kết quả của em lớn gấp mười lần. "
            "Hãy kiểm tra lại đơn vị hoặc dấu phẩy thập phân."
        ),
    },
    "ten_times_too_small": {
        "en": "Close — your answer is ten times too small. Check your units or decimal point.",
        "vi": (
            "Gần đúng rồi — kết quả của em nhỏ gấp mười lần. "
            "Hãy kiểm tra lại đơn vị hoặc dấu phẩy thập phân."
        ),
    },
    "wrong_sign": {
        "en": "You have the right magnitude but the wrong sign.",
        "vi": "Độ lớn đã đúng nhưng dấu thì chưa.",
    },
    "unreadable_expression": {
        "en": "We could not read that expression: {error}",
        "vi": "Không đọc được biểu thức này: {error}",
    },
    "found_some": {
        "en": "You found {hits} of {total}.",
        "vi": "Em đã chọn đúng {hits} trong {total} phương án.",
    },
    "found_some_with_errors": {
        "en": "You found {hits} of {total}, with {wrong} incorrect.",
        "vi": "Em đã chọn đúng {hits} trong {total} phương án, và chọn sai {wrong} phương án.",
    },
    "blanks_correct": {
        "en": "{correct} of {total} blanks correct.",
        "vi": "Em điền đúng {correct} trong {total} chỗ trống.",
    },
    "pairs_matched": {
        "en": "{correct} of {total} pairs matched.",
        "vi": "Em ghép đúng {correct} trong {total} cặp.",
    },
    "key_ideas_mentioned": {
        "en": "Mentioned {hits} of the {total} key ideas we were looking for.",
        "vi": "Bài làm của em nêu được {hits} trong {total} ý chính cần có.",
    },
}


# Why the recommender picked a skill. ``detail_params`` supplies the skill name or the number
# of days, so Vietnamese can put them where Vietnamese puts them.
RECOMMENDATION_REASONS: dict[str, dict[str, str]] = {
    "prerequisite_gap": {
        "en": "Needed before you can start {skill}",
        "vi": "Cần nắm vững trước khi học {skill}",
    },
    "review_due": {
        "en": "Keep {skill} sharp — last practised {days} days ago",
        "vi": "Ôn lại {skill} cho nhớ — em đã luyện tập cách đây {days} ngày",
    },
    "new_skill": {
        "en": "A new skill you are ready to start",
        "vi": "Một kĩ năng mới mà em đã sẵn sàng để bắt đầu",
    },
    "weak_skill": {
        "en": "This one needs more work — let's build it up",
        "vi": "Phần này em cần luyện thêm — hãy cùng củng cố nhé",
    },
    "in_progress": {
        "en": "You have made a start — keep going to reach mastery",
        "vi": "Em đã bắt đầu rồi — hãy tiếp tục để thành thạo nhé",
    },
}


# Raised before grading even starts — "you did not fill this in" rather than "you got it wrong".
FORMAT_ERRORS: dict[str, dict[str, str]] = {
    "select_an_option": {
        "en": "Select an option before submitting",
        "vi": "Hãy chọn một phương án trước khi nộp bài",
    },
    "select_at_least_one": {
        "en": "Select at least one option before submitting",
        "vi": "Hãy chọn ít nhất một phương án trước khi nộp bài",
    },
    "expected_option_list": {
        "en": "Expected a list of selected options",
        "vi": "Cần một danh sách các phương án đã chọn",
    },
    "enter_an_expression": {
        "en": "Enter an expression before submitting",
        "vi": "Hãy nhập một biểu thức trước khi nộp bài",
    },
    "enter_an_answer": {
        "en": "Enter an answer before submitting",
        "vi": "Hãy nhập câu trả lời trước khi nộp bài",
    },
    "expected_blank_map": {
        "en": "Expected an object mapping blank ids to answers",
        "vi": "Cần một đối tượng ánh xạ mã chỗ trống tới câu trả lời",
    },
    "expected_matching_map": {
        "en": "Expected an object mapping left ids to right ids",
        "vi": "Cần một đối tượng ánh xạ mã bên trái tới mã bên phải",
    },
    "expected_order_list": {
        "en": "Expected a list of item ids in order",
        "vi": "Cần một danh sách mã các mục theo thứ tự",
    },
    "choose_true_or_false": {
        "en": "Choose True or False",
        "vi": "Hãy chọn Đúng hoặc Sai",
    },
    "expected_a_number": {
        "en": "Expected a number",
        "vi": "Cần nhập một số",
    },
    "answer_is_empty": {
        "en": "Answer is empty",
        "vi": "Em chưa nhập câu trả lời",
    },
    "division_by_zero": {
        "en": "Division by zero",
        "vi": "Không thể chia cho 0",
    },
    "answer_must_be_object": {
        "en": "Answer payload must be an object",
        "vi": "Dữ liệu câu trả lời phải là một đối tượng",
    },
}


def _render(table: dict[str, dict[str, str]], key: str, locale: str, params: dict[str, Any]) -> str:
    entry = table.get(key)
    if entry is None:
        # An unknown key is a programming error, not a student's problem. Returning the key
        # rather than raising keeps a missing entry from turning a graded answer into a 500.
        return key
    template = entry.get(locale) or entry[DEFAULT_LOCALE]
    if not params:
        return template
    try:
        return template.format(**params)
    except (KeyError, IndexError):
        return entry[DEFAULT_LOCALE].format(**params)


def render_feedback(key: str, locale: str, params: dict[str, Any] | None = None) -> str:
    """Turn a grader's message key into a sentence in ``locale``."""
    return _render(FEEDBACK, key, locale, params or {})


def render_format_error(key: str, locale: str) -> str:
    """Turn a submission-format error key into a sentence in ``locale``."""
    return _render(FORMAT_ERRORS, key, locale, {})


def render_recommendation(reason: str, locale: str, params: dict[str, Any] | None = None) -> str:
    """Turn a recommender reason code into a sentence in ``locale``."""
    return _render(RECOMMENDATION_REASONS, reason, locale, params or {})
