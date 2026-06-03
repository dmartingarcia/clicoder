import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '../helpers';

// ── ConversationContext mock ────────────────────────────────────────────────────
const mockAnalyzeReport = vi.fn();
const mockCreateConversation = vi.fn();
const mockValidateCode = vi.fn();
const mockRejectCode = vi.fn();
const mockSuggestCode = vi.fn();

let mockState = {
  activeConversationId: 'conv-test-1',
  pendingConversation: false,
  chatItems: [] as Array<{ kind: string; message_id?: string; card_id?: string; content: string; timestamp?: string; card_type?: string }>,
  predictedCodes: [] as Array<{ code_id: string; cie10_code: string; reasoning: string; confidence: number; status: string }>,
  isAnalyzing: false,
};

vi.mock('@/contexts/ConversationContext', () => ({
  useConversation: () => ({
    ...mockState,
    userId: 'user-1',
    conversations: [],
    trashedConversations: [],
    analyzeReport: mockAnalyzeReport,
    createConversation: mockCreateConversation,
    validateCode: mockValidateCode,
    rejectCode: mockRejectCode,
    switchConversation: vi.fn(),
    deleteConversation: vi.fn(),
    restoreConversation: vi.fn(),
    suggestCode: mockSuggestCode,
  }),
}));

// Mock sidebar — avoid rendering the full sidebar in these tests
vi.mock('@/components/ConversationSidebar', () => ({
  ConversationSidebar: () => <div data-testid="sidebar" />,
}));

import { ChatInterface } from '@/components/ChatInterface';

describe('ChatInterface', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockState = {
      activeConversationId: 'conv-test-1',
      pendingConversation: false,
      chatItems: [],
      predictedCodes: [],
      isAnalyzing: false,
    };
  });

  describe('welcome screen', () => {
    it('shows welcome state when no conversation is active', () => {
      mockState.activeConversationId = null as unknown as string;
      mockState.pendingConversation = false;
      render(<ChatInterface />);
      expect(screen.getByText('chat.welcome_title')).toBeInTheDocument();
    });

    it('calls createConversation when "new analysis" button clicked', async () => {
      mockState.activeConversationId = null as unknown as string;
      mockState.pendingConversation = false;
      const user = userEvent.setup();
      render(<ChatInterface />);
      await user.click(screen.getByText('chat.new_analysis'));
      expect(mockCreateConversation).toHaveBeenCalledOnce();
    });
  });

  describe('report input', () => {
    it('shows the report textarea when a conversation is active', () => {
      render(<ChatInterface />);
      expect(screen.getByPlaceholderText('chat.report_placeholder')).toBeInTheDocument();
    });

    it('shows min-chars warning when text is short (< 20 chars)', async () => {
      const user = userEvent.setup();
      render(<ChatInterface />);
      const textarea = screen.getByPlaceholderText('chat.report_placeholder');
      await user.type(textarea, 'short text');
      // Our mock t() returns "chat.min_chars" with vars interpolated into key
      expect(screen.getByText(/chat\.min_chars/)).toBeInTheDocument();
    });

    it('does NOT show min-chars warning when text is empty', () => {
      render(<ChatInterface />);
      expect(screen.queryByText(/chat\.min_chars/)).not.toBeInTheDocument();
    });

    it('does NOT show min-chars warning when text is ≥ 20 chars', async () => {
      const user = userEvent.setup();
      render(<ChatInterface />);
      const textarea = screen.getByPlaceholderText('chat.report_placeholder');
      await user.type(textarea, 'This report is long enough to pass validation');
      expect(screen.queryByText(/chat\.min_chars/)).not.toBeInTheDocument();
    });

    it('disables the analyze button when text is < 20 chars', async () => {
      const user = userEvent.setup();
      render(<ChatInterface />);
      const textarea = screen.getByPlaceholderText('chat.report_placeholder');
      await user.type(textarea, 'too short');
      const btn = screen.getByRole('button', { name: /chat\.analyze_button/i });
      expect(btn).toBeDisabled();
    });

    it('enables the analyze button when text is ≥ 20 chars', async () => {
      const user = userEvent.setup();
      render(<ChatInterface />);
      const textarea = screen.getByPlaceholderText('chat.report_placeholder');
      await user.type(textarea, 'This report is long enough to pass');
      const btn = screen.getByRole('button', { name: /chat\.analyze_button/i });
      expect(btn).not.toBeDisabled();
    });

    it('calls analyzeReport and clears input on submit', async () => {
      const user = userEvent.setup();
      render(<ChatInterface />);
      const textarea = screen.getByPlaceholderText('chat.report_placeholder');
      const report = 'Patient has hypertension and diabetes type 2';
      await user.type(textarea, report);
      await user.click(screen.getByRole('button', { name: /chat\.analyze_button/i }));
      expect(mockAnalyzeReport).toHaveBeenCalledWith(report);
      expect(textarea).toHaveValue('');
    });

    it('also submits via Ctrl+Enter', async () => {
      const user = userEvent.setup();
      render(<ChatInterface />);
      const textarea = screen.getByPlaceholderText('chat.report_placeholder');
      await user.type(textarea, 'Patient has hypertension and diabetes type 2');
      await user.keyboard('{Control>}{Enter}{/Control}');
      expect(mockAnalyzeReport).toHaveBeenCalledOnce();
    });
  });

  describe('chat thread', () => {
    it('shows empty state when no chat items', () => {
      render(<ChatInterface />);
      expect(screen.getByText('chat.empty_state')).toBeInTheDocument();
    });

    it('renders the first user message as the report card', () => {
      mockState.chatItems = [
        { kind: 'user', message_id: 'msg-1', content: 'Patient report content here', timestamp: new Date().toISOString() },
      ];
      render(<ChatInterface />);
      expect(screen.getByText('Patient report content here')).toBeInTheDocument();
      // The report label is shown above the first message
      expect(screen.getAllByText('chat.report_label').length).toBeGreaterThan(0);
    });

    it('shows analyzing spinner while isAnalyzing is true', () => {
      mockState.isAnalyzing = true;
      render(<ChatInterface />);
      expect(screen.getByText('chat.analyzing')).toBeInTheDocument();
    });
  });

  describe('codes card validation', () => {
    it('shows validate/reject buttons for pending codes with code_id', () => {
      mockState.chatItems = [
        { kind: 'user', message_id: 'msg-1', content: 'Report text here for patient visit', timestamp: new Date().toISOString() },
        {
          kind: 'card',
          card_id: 'card-1',
          message_id: 'msg-1',
          card_type: 'codes',
          content: [{ code: 'I10', description: 'Hypertension', reason: 'High BP', confidence: 0.94 }],
        },
      ] as typeof mockState.chatItems;
      mockState.predictedCodes = [
        { code_id: 'code-uuid-1', cie10_code: 'I10', reasoning: 'High BP', confidence: 0.94, status: 'pending' },
      ];
      render(<ChatInterface />);
      expect(screen.getByText('cards.validate')).toBeInTheDocument();
      expect(screen.getByText('cards.reject')).toBeInTheDocument();
    });

    it('calls validateCode when validate button clicked', async () => {
      mockState.chatItems = [
        { kind: 'user', message_id: 'msg-1', content: 'Patient report long enough to show', timestamp: new Date().toISOString() },
        {
          kind: 'card',
          card_id: 'card-1',
          message_id: 'msg-1',
          card_type: 'codes',
          content: [{ code: 'I10', description: 'Hypertension', reason: 'High BP', confidence: 0.94 }],
        },
      ] as typeof mockState.chatItems;
      mockState.predictedCodes = [
        { code_id: 'code-uuid-1', cie10_code: 'I10', reasoning: 'High BP', confidence: 0.94, status: 'pending' },
      ];
      const user = userEvent.setup();
      render(<ChatInterface />);
      await user.click(screen.getByText('cards.validate'));
      expect(mockValidateCode).toHaveBeenCalledWith('code-uuid-1', 'I10');
    });

    it('shows reject input and calls rejectCode via confirm button', async () => {
      mockState.chatItems = [
        { kind: 'user', message_id: 'msg-1', content: 'Patient report long enough to show', timestamp: new Date().toISOString() },
        {
          kind: 'card',
          card_id: 'card-1',
          message_id: 'msg-1',
          card_type: 'codes',
          content: [{ code: 'I10', description: 'Hypertension', reason: 'High BP', confidence: 0.94 }],
        },
      ] as typeof mockState.chatItems;
      mockState.predictedCodes = [
        { code_id: 'code-uuid-1', cie10_code: 'I10', reasoning: 'High BP', confidence: 0.94, status: 'pending' },
      ];
      const user = userEvent.setup();
      render(<ChatInterface />);

      // Click reject to open input
      await user.click(screen.getByText('cards.reject'));
      const input = screen.getByPlaceholderText('cards.reject_placeholder');
      expect(input).toBeInTheDocument();

      // Type a reason and click confirm
      await user.type(input, 'Wrong diagnosis');
      await user.click(screen.getByText('cards.confirm_reject'));
      expect(mockRejectCode).toHaveBeenCalledWith('code-uuid-1', 'I10', 'Wrong diagnosis');
    });

    it('calls rejectCode via Enter key in reject input', async () => {
      mockState.chatItems = [
        { kind: 'user', message_id: 'msg-1', content: 'Patient report long enough to show', timestamp: new Date().toISOString() },
        {
          kind: 'card',
          card_id: 'card-1',
          message_id: 'msg-1',
          card_type: 'codes',
          content: [{ code: 'J45', description: 'Asthma', reason: 'Breathing issues', confidence: 0.87 }],
        },
      ] as typeof mockState.chatItems;
      mockState.predictedCodes = [
        { code_id: 'code-uuid-2', cie10_code: 'J45', reasoning: 'Breathing issues', confidence: 0.87, status: 'pending' },
      ];
      const user = userEvent.setup();
      render(<ChatInterface />);

      await user.click(screen.getByText('cards.reject'));
      const input = screen.getByPlaceholderText('cards.reject_placeholder');
      await user.type(input, 'Not correct{Enter}');
      expect(mockRejectCode).toHaveBeenCalledWith('code-uuid-2', 'J45', 'Not correct');
    });

    it('shows validated status for validated codes', () => {
      mockState.chatItems = [
        { kind: 'user', message_id: 'msg-1', content: 'Patient report long enough to show', timestamp: new Date().toISOString() },
        {
          kind: 'card',
          card_id: 'card-1',
          message_id: 'msg-1',
          card_type: 'codes',
          content: [{ code: 'I10', description: 'Hypertension', reason: 'High BP', confidence: 0.94 }],
        },
      ] as typeof mockState.chatItems;
      mockState.predictedCodes = [
        { code_id: 'code-uuid-1', cie10_code: 'I10', reasoning: 'High BP', confidence: 0.94, status: 'validated' },
      ];
      render(<ChatInterface />);
      expect(screen.getByText('cards.validated')).toBeInTheDocument();
      expect(screen.queryByText('cards.validate')).not.toBeInTheDocument();
    });
  });

  describe('max tokens warning', () => {
    it('shows max_words_error when token count exceeds 1024', () => {
      render(<ChatInterface />);
      const textarea = screen.getByPlaceholderText('chat.report_placeholder');
      // 4097 chars → ceil(4097/4) = 1025 tokens
      const longText = 'a'.repeat(4097);
      fireEvent.change(textarea, { target: { value: longText } });
      expect(screen.getByText(/chat\.max_words_error/)).toBeInTheDocument();
    });

    it('disables analyze button when token count exceeds 1024', () => {
      render(<ChatInterface />);
      const textarea = screen.getByPlaceholderText('chat.report_placeholder');
      const longText = 'a'.repeat(4097);
      fireEvent.change(textarea, { target: { value: longText } });
      const btn = screen.getByRole('button', { name: /chat\.analyze_button/i });
      expect(btn).toBeDisabled();
    });

    it('does NOT show max_words_error when token count is exactly 1024', () => {
      render(<ChatInterface />);
      const textarea = screen.getByPlaceholderText('chat.report_placeholder');
      // 4096 chars → ceil(4096/4) = 1024 tokens, not exceeding
      const text = 'a'.repeat(4096);
      fireEvent.change(textarea, { target: { value: text } });
      expect(screen.queryByText(/chat\.max_words_error/)).not.toBeInTheDocument();
    });
  });

  describe('SuggestionCard interaction', () => {
    function setupSuggestionCard() {
      const content = 'El paciente presenta hipertensión arterial severa';
      mockState.chatItems = [
        { kind: 'user', message_id: 'msg-1', content: 'Report here', timestamp: new Date().toISOString() },
        {
          kind: 'card',
          card_id: 'card-s',
          message_id: 'msg-1',
          card_type: 'suggest',
          content,
        },
      ] as typeof mockState.chatItems;
      return content;
    }

    it('shows the code input form when text is selected inside the SuggestionCard', () => {
      const content = setupSuggestionCard();
      render(<ChatInterface />);

      const textDiv = screen.getByText(content);
      const mockSel = {
        isCollapsed: false,
        toString: () => 'hipertensión arterial',
        anchorNode: textDiv,
        removeAllRanges: vi.fn(),
      };
      vi.spyOn(window, 'getSelection').mockReturnValue(mockSel as unknown as Selection);

      fireEvent.mouseUp(textDiv);

      expect(screen.getByPlaceholderText('cards.suggest_code_placeholder')).toBeInTheDocument();
      expect(screen.getByText(/cards\.suggest_selected/)).toBeInTheDocument();
    });

    it('submits a suggestion via the submit button', async () => {
      const content = setupSuggestionCard();
      const user = userEvent.setup();
      render(<ChatInterface />);

      const textDiv = screen.getByText(content);
      const mockSel = {
        isCollapsed: false,
        toString: () => 'hipertensión arterial',
        anchorNode: textDiv,
        removeAllRanges: vi.fn(),
      };
      vi.spyOn(window, 'getSelection').mockReturnValue(mockSel as unknown as Selection);
      fireEvent.mouseUp(textDiv);

      const input = screen.getByPlaceholderText('cards.suggest_code_placeholder');
      await user.type(input, 'I10');

      await user.click(screen.getByText('cards.suggest_submit'));
      // selectedText is passed as-is (not uppercased); only the code is uppercased
      expect(mockSuggestCode).toHaveBeenCalledWith('hipertensión arterial', 'I10');
    });

    it('submits a suggestion via Enter key', async () => {
      const content = setupSuggestionCard();
      const user = userEvent.setup();
      render(<ChatInterface />);

      const textDiv = screen.getByText(content);
      const mockSel = {
        isCollapsed: false,
        toString: () => 'diabetes tipo 2',
        anchorNode: textDiv,
        removeAllRanges: vi.fn(),
      };
      vi.spyOn(window, 'getSelection').mockReturnValue(mockSel as unknown as Selection);
      fireEvent.mouseUp(textDiv);

      const input = screen.getByPlaceholderText('cards.suggest_code_placeholder');
      await user.type(input, 'E11{Enter}');
      expect(mockSuggestCode).toHaveBeenCalledWith('diabetes tipo 2', 'E11');
    });

    it('closes the form when Escape is pressed', async () => {
      const content = setupSuggestionCard();
      const user = userEvent.setup();
      render(<ChatInterface />);

      const textDiv = screen.getByText(content);
      const mockSel = {
        isCollapsed: false,
        toString: () => 'some diagnosis text',
        anchorNode: textDiv,
        removeAllRanges: vi.fn(),
      };
      vi.spyOn(window, 'getSelection').mockReturnValue(mockSel as unknown as Selection);
      fireEvent.mouseUp(textDiv);

      screen.getByPlaceholderText('cards.suggest_code_placeholder');
      await user.keyboard('{Escape}');
      expect(screen.queryByPlaceholderText('cards.suggest_code_placeholder')).not.toBeInTheDocument();
    });

    it('cancel button hides the form', async () => {
      const content = setupSuggestionCard();
      const user = userEvent.setup();
      render(<ChatInterface />);

      const textDiv = screen.getByText(content);
      const mockSel = {
        isCollapsed: false,
        toString: () => 'cancel test text here',
        anchorNode: textDiv,
        removeAllRanges: vi.fn(),
      };
      vi.spyOn(window, 'getSelection').mockReturnValue(mockSel as unknown as Selection);
      fireEvent.mouseUp(textDiv);

      // The cancel button is inside the form container — scope with within()
      const { within } = await import('@testing-library/react');
      const input = screen.getByPlaceholderText('cards.suggest_code_placeholder');
      const formRow = input.parentElement!; // the flex gap-2 div
      const cancelBtn = within(formRow).getAllByRole('button').at(-1)!;
      await user.click(cancelBtn);
      expect(screen.queryByPlaceholderText('cards.suggest_code_placeholder')).not.toBeInTheDocument();
    });

    it('shows submitted suggestions after successful submit', async () => {
      const content = setupSuggestionCard();
      const user = userEvent.setup();
      render(<ChatInterface />);

      const textDiv = screen.getByText(content);
      const mockSel = {
        isCollapsed: false,
        toString: () => 'submitted text',
        anchorNode: textDiv,
        removeAllRanges: vi.fn(),
      };
      vi.spyOn(window, 'getSelection').mockReturnValue(mockSel as unknown as Selection);
      fireEvent.mouseUp(textDiv);

      await user.type(screen.getByPlaceholderText('cards.suggest_code_placeholder'), 'I10');
      await user.click(screen.getByText('cards.suggest_submit'));

      // After submit, submitted list should show
      expect(screen.getByText(/submitted text/)).toBeInTheDocument();
      expect(screen.getByText('I10')).toBeInTheDocument();
    });
  });

  describe('text and suggestion cards', () => {
    it('renders TextCard for unknown card_type', () => {
      mockState.chatItems = [
        { kind: 'user', message_id: 'msg-1', content: 'Patient report text here', timestamp: new Date().toISOString() },
        {
          kind: 'card',
          card_id: 'card-2',
          message_id: 'msg-1',
          card_type: 'text',
          content: 'This is a generic text card',
        },
      ] as typeof mockState.chatItems;
      render(<ChatInterface />);
      expect(screen.getByText('This is a generic text card')).toBeInTheDocument();
    });

    it('renders SuggestionCard with hint text', () => {
      mockState.chatItems = [
        { kind: 'user', message_id: 'msg-1', content: 'Patient report text here', timestamp: new Date().toISOString() },
        {
          kind: 'card',
          card_id: 'card-3',
          message_id: 'msg-1',
          card_type: 'suggest',
          content: 'Seleccione un fragmento de texto para sugerir un código',
        },
      ] as typeof mockState.chatItems;
      render(<ChatInterface />);
      // SuggestionCard renders suggest_title and suggest_hint via t()
      expect(screen.getByText('cards.suggest_title')).toBeInTheDocument();
      expect(screen.getByText('cards.suggest_hint')).toBeInTheDocument();
    });

    it('renders SuggestionCard content text', () => {
      const content = 'El paciente presenta síntomas respiratorios agudos';
      mockState.chatItems = [
        { kind: 'user', message_id: 'msg-1', content: 'Patient report text here', timestamp: new Date().toISOString() },
        {
          kind: 'card',
          card_id: 'card-3',
          message_id: 'msg-1',
          card_type: 'suggest',
          content,
        },
      ] as typeof mockState.chatItems;
      render(<ChatInterface />);
      expect(screen.getByText(content)).toBeInTheDocument();
    });
  });

  describe('subsequent user messages', () => {
    it('renders a second user message through ChatItemView', () => {
      mockState.chatItems = [
        { kind: 'user', message_id: 'msg-1', content: 'First patient report', timestamp: new Date().toISOString() },
        { kind: 'user', message_id: 'msg-2', content: 'Follow-up patient report', timestamp: new Date().toISOString() },
      ];
      render(<ChatInterface />);
      expect(screen.getByText('Follow-up patient report')).toBeInTheDocument();
    });

    it('shows MD badge on user messages in ChatItemView', () => {
      mockState.chatItems = [
        { kind: 'user', message_id: 'msg-1', content: 'First message here', timestamp: new Date().toISOString() },
        { kind: 'user', message_id: 'msg-2', content: 'Second message rendered via ChatItemView', timestamp: new Date().toISOString() },
      ];
      render(<ChatInterface />);
      // MD badge appears for user messages rendered through ChatItemView
      expect(screen.getAllByText('MD').length).toBeGreaterThan(0);
    });
  });

  describe('summary and recommendations cards', () => {
    it('renders SummaryCard content', () => {
      mockState.chatItems = [
        { kind: 'user', message_id: 'msg-1', content: 'Patient report text here', timestamp: new Date().toISOString() },
        {
          kind: 'card',
          card_id: 'card-s',
          message_id: 'msg-1',
          card_type: 'summary',
          content: 'Patient summary text here',
        },
      ] as typeof mockState.chatItems;
      render(<ChatInterface />);
      expect(screen.getByText('Patient summary text here')).toBeInTheDocument();
      expect(screen.getByText('cards.summary_title')).toBeInTheDocument();
    });

    it('does not render recommendations cards (handled externally)', () => {
      mockState.chatItems = [
        { kind: 'user', message_id: 'msg-1', content: 'Patient report text here', timestamp: new Date().toISOString() },
        {
          kind: 'card',
          card_id: 'card-r',
          message_id: 'msg-1',
          card_type: 'recommendations',
          content: 'Follow up in 2 weeks',
        },
      ] as typeof mockState.chatItems;
      render(<ChatInterface />);
      expect(screen.queryByText('Follow up in 2 weeks')).not.toBeInTheDocument();
    });
  });
});
