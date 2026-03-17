import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '../helpers';

// ── ConversationContext mock ────────────────────────────────────────────────────
const mockAnalyzeReport = vi.fn();
const mockCreateConversation = vi.fn();
const mockValidateCode = vi.fn();
const mockRejectCode = vi.fn();

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
  });
});
