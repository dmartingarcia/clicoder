import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '../helpers';

const mockAnalyzeReport = vi.fn();
const mockCreateConversation = vi.fn();
const mockValidateCode = vi.fn();
const mockRejectCode = vi.fn();
const mockSuggestCode = vi.fn();
const mockVerifyTrigger = vi.fn();

let mockState = {
  activeConversationId: 'conv-test-1',
  pendingConversation: false,
  chatItems: [] as Array<{ kind: string; message_id?: string; card_id?: string; content: string; timestamp?: string; card_type?: string }>,
  predictedCodes: [] as Array<{ code_id: string; cie10_code: string; reasoning: string; confidence: number; status: string; verified_triggers?: string[] }>,
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
    verifyTrigger: mockVerifyTrigger,
  }),
}));

vi.mock('@/components/ConversationSidebar', () => ({
  ConversationSidebar: () => <div data-testid="sidebar" />,
}));

// Sustituye solo searchCie10 (evita llamadas de red reales); getAncestors se mantiene real.
const { mockSearchCie10 } = vi.hoisted(() => ({ mockSearchCie10: vi.fn() }));
vi.mock('@/lib/cie10', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...(actual as object), searchCie10: mockSearchCie10 };
});

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
    mockSearchCie10.mockReset();
    mockSearchCie10.mockResolvedValue([]);
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

      await user.click(screen.getByText('cards.reject'));
      const input = screen.getByPlaceholderText('cards.reject_placeholder');
      expect(input).toBeInTheDocument();

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

  describe('evidencias (triggers) de un código', () => {
    it('distingue el término que viene del diccionario del que detectó el modelo, y permite marcar o desmarcar cada uno', async () => {
      mockState.chatItems = [
        { kind: 'user', message_id: 'msg-1', content: 'Patient report long enough to show', timestamp: new Date().toISOString() },
        {
          kind: 'card',
          card_id: 'card-1',
          message_id: 'msg-1',
          card_type: 'codes',
          content: [{
            code: 'I10',
            description: 'Hipertensión',
            reason: 'High BP',
            confidence: 0.94,
            triggers: ['hipertensión', 'presión alta'],
            trigger_detail: [
              { term: 'hipertensión', source: 'dict', weight: null },
              { term: 'presión alta', source: 'bert', weight: 0.8 },
            ],
          }],
        },
      ] as typeof mockState.chatItems;
      mockState.predictedCodes = [
        {
          code_id: 'code-uuid-1',
          cie10_code: 'I10',
          reasoning: 'High BP',
          confidence: 0.94,
          status: 'pending',
          verified_triggers: ['presión alta'],
        },
      ];
      const user = userEvent.setup();
      render(<ChatInterface />);

      // se muestra con "✓ " delante por estar verificada
      await user.click(screen.getByText(/presión alta/));
      expect(mockVerifyTrigger).toHaveBeenCalledWith('code-uuid-1', 'presión alta', false);

      await user.click(screen.getByText('hipertensión'));
      expect(mockVerifyTrigger).toHaveBeenCalledWith('code-uuid-1', 'hipertensión', true);
    });

    it('avisa mientras el resto de evidencias todavía se están calculando', () => {
      mockState.chatItems = [
        { kind: 'user', message_id: 'msg-1', content: 'Patient report long enough to show', timestamp: new Date().toISOString() },
        {
          kind: 'card',
          card_id: 'card-1',
          message_id: 'msg-1',
          card_type: 'codes',
          content: [{
            code: 'I10',
            description: 'Hipertensión',
            reason: 'High BP',
            confidence: 0.94,
            triggers: [],
            triggers_complete: false,
          }],
        },
      ] as typeof mockState.chatItems;
      render(<ChatInterface />);
      expect(screen.getByText('cards.triggers_loading')).toBeInTheDocument();
    });
  });

  describe('max tokens warning', () => {
    it('shows max_words_error when token count exceeds 512', () => {
      render(<ChatInterface />);
      const textarea = screen.getByPlaceholderText('chat.report_placeholder');
      // 4097 chars → ceil(4097/4) = 1025 tokens
      const longText = 'a'.repeat(4097);
      fireEvent.change(textarea, { target: { value: longText } });
      expect(screen.getByText(/chat\.max_words_error/)).toBeInTheDocument();
    });

    it('disables analyze button when token count exceeds 512', () => {
      render(<ChatInterface />);
      const textarea = screen.getByPlaceholderText('chat.report_placeholder');
      const longText = 'a'.repeat(4097);
      fireEvent.change(textarea, { target: { value: longText } });
      const btn = screen.getByRole('button', { name: /chat\.analyze_button/i });
      expect(btn).toBeDisabled();
    });

    it('does NOT show max_words_error when token count is exactly 512', () => {
      render(<ChatInterface />);
      const textarea = screen.getByPlaceholderText('chat.report_placeholder');
      // 2048 chars → ceil(2048/4) = 512 tokens, not exceeding
      const text = 'a'.repeat(2048);
      fireEvent.change(textarea, { target: { value: text } });
      expect(screen.queryByText(/chat\.max_words_error/)).not.toBeInTheDocument();
    });
  });

  describe('recuento de tokens que responde el servidor', () => {
    it('bloquea el envío si el tokenizador real dice que el texto es más largo de lo que parece por caracteres', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ token_count: 600 }),
      }) as unknown as typeof fetch;

      render(<ChatInterface />);
      const textarea = screen.getByPlaceholderText('chat.report_placeholder');
      // 25 caracteres → estimación rápida de 7 tokens, muy por debajo del límite de 512
      fireEvent.change(textarea, { target: { value: 'a'.repeat(25) } });

      await waitFor(() => expect(screen.getByText(/chat\.max_words_error/)).toBeInTheDocument(), { timeout: 1000 });
      expect(screen.getByRole('button', { name: /chat\.analyze_button/i })).toBeDisabled();
    });
  });

  describe('el atajo Ctrl+Enter respeta las mismas validaciones que el botón', () => {
    it('no envía el informe por Ctrl+Enter si el texto supera el límite de tokens', async () => {
      const user = userEvent.setup();
      render(<ChatInterface />);
      const textarea = screen.getByPlaceholderText('chat.report_placeholder');
      fireEvent.change(textarea, { target: { value: 'a'.repeat(4097) } });
      (textarea as HTMLTextAreaElement).focus();

      await user.keyboard('{Control>}{Enter}{/Control}');

      // el atajo de teclado no pasa por el botón (deshabilitado): repite su propia comprobación
      expect(mockAnalyzeReport).not.toHaveBeenCalled();
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

      // The cancel button is inside the form container: scope with within()
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

      expect(screen.getByText(/submitted text/)).toBeInTheDocument();
      expect(screen.getByText('I10')).toBeInTheDocument();
    });

    it('ignora el mouseup si la selección está colapsada (no hay texto realmente marcado)', () => {
      const content = setupSuggestionCard();
      render(<ChatInterface />);
      const textDiv = screen.getByText(content);
      vi.spyOn(window, 'getSelection').mockReturnValue({ isCollapsed: true } as unknown as Selection);

      fireEvent.mouseUp(textDiv);

      expect(screen.queryByPlaceholderText('cards.suggest_code_placeholder')).not.toBeInTheDocument();
    });

    it('ignora selecciones de un solo carácter, probablemente un clic accidental', () => {
      const content = setupSuggestionCard();
      render(<ChatInterface />);
      const textDiv = screen.getByText(content);
      vi.spyOn(window, 'getSelection').mockReturnValue({
        isCollapsed: false,
        toString: () => 'x',
        anchorNode: textDiv,
      } as unknown as Selection);

      fireEvent.mouseUp(textDiv);

      expect(screen.queryByPlaceholderText('cards.suggest_code_placeholder')).not.toBeInTheDocument();
    });

    it('ignora selecciones hechas fuera del texto de la propia tarjeta', () => {
      const content = setupSuggestionCard();
      render(<ChatInterface />);
      const textDiv = screen.getByText(content);
      vi.spyOn(window, 'getSelection').mockReturnValue({
        isCollapsed: false,
        toString: () => 'texto seleccionado en otro sitio',
        anchorNode: document.body,
      } as unknown as Selection);

      fireEvent.mouseUp(textDiv);

      expect(screen.queryByPlaceholderText('cards.suggest_code_placeholder')).not.toBeInTheDocument();
    });

    it('Enter sin haber escrito ningún código todavía no envía ninguna sugerencia', async () => {
      const content = setupSuggestionCard();
      const user = userEvent.setup();
      render(<ChatInterface />);
      const textDiv = screen.getByText(content);
      vi.spyOn(window, 'getSelection').mockReturnValue({
        isCollapsed: false,
        toString: () => 'texto sin código todavía',
        anchorNode: textDiv,
        removeAllRanges: vi.fn(),
      } as unknown as Selection);
      fireEvent.mouseUp(textDiv);

      const input = screen.getByPlaceholderText('cards.suggest_code_placeholder');
      input.focus();
      await user.keyboard('{Enter}');

      expect(mockSuggestCode).not.toHaveBeenCalled();
    });

    it('busca en el catálogo CIE-10 mientras se escribe el código y deja elegir una coincidencia', async () => {
      const content = setupSuggestionCard();
      mockSearchCie10.mockResolvedValue([
        { code: 'I10', description: 'Hipertensión esencial', type: 'diagnosis', metadata: {} },
      ]);
      const user = userEvent.setup();
      render(<ChatInterface />);

      const textDiv = screen.getByText(content);
      vi.spyOn(window, 'getSelection').mockReturnValue({
        isCollapsed: false,
        toString: () => 'hipertensión arterial',
        anchorNode: textDiv,
        removeAllRanges: vi.fn(),
      } as unknown as Selection);
      fireEvent.mouseUp(textDiv);

      const input = screen.getByPlaceholderText('cards.suggest_code_placeholder');
      await user.type(input, 'HI');

      await waitFor(() => expect(screen.getByText('Hipertensión esencial')).toBeInTheDocument(), { timeout: 1000 });
      expect(screen.getByText('cie10.type_diagnosis')).toBeInTheDocument();

      await user.click(screen.getByText('Hipertensión esencial'));

      expect(input).toHaveValue('I10');
      expect(screen.queryByText('cie10.type_diagnosis')).not.toBeInTheDocument();
    });

    it('con el desplegable de sugerencias abierto, Escape solo lo cierra sin cancelar la selección de texto', async () => {
      const content = setupSuggestionCard();
      mockSearchCie10.mockResolvedValue([
        { code: 'E11', description: 'Diabetes mellitus tipo 2', type: 'diagnosis', metadata: {} },
      ]);
      const user = userEvent.setup();
      render(<ChatInterface />);

      const textDiv = screen.getByText(content);
      vi.spyOn(window, 'getSelection').mockReturnValue({
        isCollapsed: false,
        toString: () => 'diabetes tipo 2',
        anchorNode: textDiv,
        removeAllRanges: vi.fn(),
      } as unknown as Selection);
      fireEvent.mouseUp(textDiv);

      const input = screen.getByPlaceholderText('cards.suggest_code_placeholder');
      await user.type(input, 'DI');
      await waitFor(() => expect(screen.getByText('Diabetes mellitus tipo 2')).toBeInTheDocument());

      await user.keyboard('{Escape}');

      // el primer Escape solo cierra el desplegable, no cancela la selección de texto
      expect(screen.queryByText('Diabetes mellitus tipo 2')).not.toBeInTheDocument();
      expect(screen.getByPlaceholderText('cards.suggest_code_placeholder')).toBeInTheDocument();
    });

    it('cierra el desplegable de sugerencias al perder el foco, aunque no se elija ninguna', async () => {
      const content = setupSuggestionCard();
      mockSearchCie10.mockResolvedValue([
        { code: 'J45', description: 'Asma', type: 'diagnosis', metadata: {} },
      ]);
      const user = userEvent.setup();
      render(<ChatInterface />);

      const textDiv = screen.getByText(content);
      vi.spyOn(window, 'getSelection').mockReturnValue({
        isCollapsed: false,
        toString: () => 'dificultad para respirar',
        anchorNode: textDiv,
        removeAllRanges: vi.fn(),
      } as unknown as Selection);
      fireEvent.mouseUp(textDiv);

      const input = screen.getByPlaceholderText('cards.suggest_code_placeholder');
      await user.type(input, 'AS');
      await waitFor(() => expect(screen.getByText('Asma')).toBeInTheDocument());

      fireEvent.blur(input);

      await waitFor(() => expect(screen.queryByText('cie10.type_diagnosis')).not.toBeInTheDocument(), { timeout: 1000 });
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
