import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { AnswerInput, hasAnswer, initialAnswer } from '@/components/exercise/answer-input';
import type { ServedQuestion } from '@/lib/api';
import { renderWithProviders, screen } from '@/test/render';

function makeQuestion(overrides: Partial<ServedQuestion> = {}): ServedQuestion {
  return {
    variant_id: 1,
    question_id: 1,
    question_slug: 'test-question',
    question_type: 'numeric',
    difficulty: 2,
    estimated_seconds: 60,
    prompt: 'What is 2 + 2?',
    skill: { id: 1, slug: 'addition', name: 'Addition' },
    hints: [],
    hint_count: 0,
    ...overrides,
  };
}

describe('AnswerInput', () => {
  describe('multiple choice', () => {
    const question = makeQuestion({
      question_type: 'multiple_choice',
      choices: [
        { id: 'a', label: '3' },
        { id: 'b', label: '4' },
        { id: 'c', label: '5' },
      ],
    });

    it('renders every choice', () => {
      renderWithProviders(<AnswerInput question={question} value={{}} onChange={() => {}} />);
      expect(screen.getByText('3')).toBeInTheDocument();
      expect(screen.getByText('4')).toBeInTheDocument();
      expect(screen.getByText('5')).toBeInTheDocument();
    });

    it('reports the selected choice id in the shape the API expects', async () => {
      const onChange = vi.fn();
      renderWithProviders(<AnswerInput question={question} value={{}} onChange={onChange} />);
      await userEvent.click(screen.getByRole('radio', { name: /4/ }));
      expect(onChange).toHaveBeenCalledWith({ choice_id: 'b' });
    });

    it('does not allow input when disabled', async () => {
      const onChange = vi.fn();
      renderWithProviders(
        <AnswerInput question={question} value={{}} onChange={onChange} disabled />,
      );
      await userEvent.click(screen.getByRole('radio', { name: /4/ }));
      expect(onChange).not.toHaveBeenCalled();
    });
  });

  describe('multiple select', () => {
    const question = makeQuestion({
      question_type: 'multiple_select',
      choices: [
        { id: 'a', label: 'Gravity' },
        { id: 'b', label: 'Friction' },
      ],
    });

    it('accumulates selections rather than replacing them', async () => {
      const onChange = vi.fn();
      renderWithProviders(
        <AnswerInput question={question} value={{ choice_ids: ['a'] }} onChange={onChange} />,
      );
      await userEvent.click(screen.getByRole('checkbox', { name: /Friction/ }));
      expect(onChange).toHaveBeenCalledWith({ choice_ids: ['a', 'b'] });
    });

    it('deselects an already-selected choice', async () => {
      const onChange = vi.fn();
      renderWithProviders(
        <AnswerInput question={question} value={{ choice_ids: ['a'] }} onChange={onChange} />,
      );
      await userEvent.click(screen.getByRole('checkbox', { name: /Gravity/ }));
      expect(onChange).toHaveBeenCalledWith({ choice_ids: [] });
    });
  });

  describe('numeric', () => {
    it('reports typed text under `value`', async () => {
      const onChange = vi.fn();
      renderWithProviders(
        <AnswerInput question={makeQuestion()} value={{}} onChange={onChange} />,
      );
      await userEvent.type(screen.getByRole('textbox'), '4');
      expect(onChange).toHaveBeenLastCalledWith({ value: '4' });
    });

    it('shows the unit when the question has one', () => {
      renderWithProviders(
        <AnswerInput question={makeQuestion({ unit: 'km/h' })} value={{}} onChange={() => {}} />,
      );
      expect(screen.getByText('km/h')).toBeInTheDocument();
    });
  });

  describe('true / false', () => {
    it('reports a boolean, not a string', async () => {
      const onChange = vi.fn();
      renderWithProviders(
        <AnswerInput
          question={makeQuestion({ question_type: 'true_false' })}
          value={{}}
          onChange={onChange}
        />,
      );
      await userEvent.click(screen.getByRole('radio', { name: 'True' }));
      expect(onChange).toHaveBeenCalledWith({ value: true });
    });
  });

  describe('ordering', () => {
    const question = makeQuestion({
      question_type: 'ordering',
      items: [
        { id: 'i1', label: 'First step' },
        { id: 'i2', label: 'Second step' },
        { id: 'i3', label: 'Third step' },
      ],
    });

    it('offers keyboard-accessible reorder controls rather than drag-and-drop', () => {
      renderWithProviders(<AnswerInput question={question} value={{}} onChange={() => {}} />);
      // Every item has a labelled move-down control; the first item's move-up is disabled.
      expect(screen.getAllByRole('button', { name: /Move .* down/ })).toHaveLength(3);
      expect(screen.getByRole('button', { name: /Move First step up/ })).toBeDisabled();
    });

    it('swaps adjacent items and reports the new order', async () => {
      const onChange = vi.fn();
      renderWithProviders(<AnswerInput question={question} value={{}} onChange={onChange} />);
      await userEvent.click(screen.getByRole('button', { name: /Move First step down/ }));
      expect(onChange).toHaveBeenCalledWith({ order: ['i2', 'i1', 'i3'] });
    });
  });

  describe('matching', () => {
    const question = makeQuestion({
      question_type: 'matching',
      left: [{ id: 'l1', label: 'Force' }],
      right: [
        { id: 'r1', label: 'newton' },
        { id: 'r2', label: 'joule' },
      ],
    });

    it('reports a left-to-right mapping', async () => {
      const onChange = vi.fn();
      renderWithProviders(<AnswerInput question={question} value={{}} onChange={onChange} />);
      await userEvent.selectOptions(screen.getByLabelText('Force'), 'r1');
      expect(onChange).toHaveBeenCalledWith({ mapping: { l1: 'r1' } });
    });
  });
});

describe('hasAnswer', () => {
  it('requires a choice for multiple choice', () => {
    const question = makeQuestion({ question_type: 'multiple_choice', choices: [] });
    expect(hasAnswer(question, {})).toBe(false);
    expect(hasAnswer(question, { choice_id: 'a' })).toBe(true);
  });

  it('requires at least one selection for multiple select', () => {
    const question = makeQuestion({ question_type: 'multiple_select' });
    expect(hasAnswer(question, { choice_ids: [] })).toBe(false);
    expect(hasAnswer(question, { choice_ids: ['a'] })).toBe(true);
  });

  it('treats a whitespace-only text answer as empty', () => {
    expect(hasAnswer(makeQuestion(), { value: '   ' })).toBe(false);
    expect(hasAnswer(makeQuestion(), { value: '42' })).toBe(true);
  });

  it('accepts false as a real true/false answer', () => {
    // A plain truthiness check would wrongly reject "False", which is a valid answer.
    const question = makeQuestion({ question_type: 'true_false' });
    expect(hasAnswer(question, { value: false })).toBe(true);
  });

  it('requires every blank to be filled', () => {
    const question = makeQuestion({
      question_type: 'fill_blank',
      blanks: [
        { id: '1', type: 'numeric', label: null, unit: null },
        { id: '2', type: 'numeric', label: null, unit: null },
      ],
    });
    expect(hasAnswer(question, { blanks: { '1': '5' } })).toBe(false);
    expect(hasAnswer(question, { blanks: { '1': '5', '2': '3' } })).toBe(true);
  });

  it('requires every pair to be matched', () => {
    const question = makeQuestion({
      question_type: 'matching',
      left: [
        { id: 'l1', label: 'a' },
        { id: 'l2', label: 'b' },
      ],
    });
    expect(hasAnswer(question, { mapping: { l1: 'r1' } })).toBe(false);
    expect(hasAnswer(question, { mapping: { l1: 'r1', l2: 'r2' } })).toBe(true);
  });
});

describe('initialAnswer', () => {
  it('pre-populates ordering with the presented order', () => {
    const question = makeQuestion({
      question_type: 'ordering',
      items: [
        { id: 'i1', label: 'a' },
        { id: 'i2', label: 'b' },
      ],
    });
    expect(initialAnswer(question)).toEqual({ order: ['i1', 'i2'] });
  });

  it('starts other types empty', () => {
    expect(initialAnswer(makeQuestion())).toEqual({});
    expect(initialAnswer(makeQuestion({ question_type: 'multiple_select' }))).toEqual({
      choice_ids: [],
    });
  });
});
