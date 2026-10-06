import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, act, waitFor } from '@testing-library/react';
import '../helpers';

import { getSocket } from '@/lib/socket';

const channelEvents: Record<string, (payload: unknown) => void> = {};
const joinCallbacks: Record<string, (resp: unknown) => void> = {};

let pushRespondeCon: 'ninguno' | 'ok' | 'error' = 'ninguno';

const mockChannel = {
  join: vi.fn(() => {
    for (const k of Object.keys(joinCallbacks)) delete joinCallbacks[k];
    function receive(event: string, cb: (resp: unknown) => void) {
      joinCallbacks[event] = cb;
      return { receive };
    }
    return { receive };
  }),
  on: vi.fn((event: string, cb: (payload: unknown) => void) => {
    channelEvents[event] = cb;
  }),
  push: vi.fn(() => {
    // Los .receive() encadenados solo se disparan si el test lo pide
    function receive(evento: string, cb: (resp?: unknown) => void) {
      if (evento === pushRespondeCon) cb({});
      return { receive };
    }
    return { receive };
  }),
  leave: vi.fn(),
};

const mockSocket = { channel: vi.fn(() => mockChannel) };

import { ConversationProvider, useConversation } from '@/contexts/ConversationContext';

function Probe({ onRender }: { onRender: (ctx: ReturnType<typeof useConversation>) => void }) {
  const ctx = useConversation();
  onRender(ctx);
  return null;
}

function renderProvider(userId = 'user-1', token = 'tok-abc', onUnauthorized?: () => void) {
  let capturedCtx!: ReturnType<typeof useConversation>;
  render(
    <ConversationProvider userId={userId} token={token} onUnauthorized={onUnauthorized}>
      <Probe onRender={(ctx) => { capturedCtx = ctx; }} />
    </ConversationProvider>
  );
  return () => capturedCtx;
}

function mockFetch(body: unknown, ok = true) {
  global.fetch = vi.fn().mockResolvedValue({ ok, json: async () => body } as Response);
}

describe('ConversationProvider', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getSocket).mockReturnValue(mockSocket as unknown as ReturnType<typeof getSocket>);
    for (const k of Object.keys(channelEvents)) delete channelEvents[k];
    for (const k of Object.keys(joinCallbacks)) delete joinCallbacks[k];
    mockFetch({ conversations: [] });
    pushRespondeCon = 'ninguno';
  });

  describe('initial state', () => {
    it('starts with empty chatItems and predictedCodes', async () => {
      const getCtx = renderProvider();
      await waitFor(() => expect(global.fetch).toHaveBeenCalled());
      expect(getCtx().chatItems).toEqual([]);
      expect(getCtx().predictedCodes).toEqual([]);
    });

    it('starts with isAnalyzing=false and pendingConversation=false', async () => {
      const getCtx = renderProvider();
      await waitFor(() => expect(global.fetch).toHaveBeenCalled());
      expect(getCtx().isAnalyzing).toBe(false);
      expect(getCtx().pendingConversation).toBe(false);
    });

    it('starts with activeConversationId=null', async () => {
      const getCtx = renderProvider();
      await waitFor(() => expect(global.fetch).toHaveBeenCalled());
      expect(getCtx().activeConversationId).toBeNull();
    });
  });

  describe('loadConversations on mount', () => {
    it('fetches active conversations on mount', async () => {
      const convs = [{ conversation_id: 'c1', started_at: new Date().toISOString(), status: 'active', deleted_at: null, message_count: 0, last_message: null }];
      mockFetch({ conversations: convs });

      const getCtx = renderProvider();
      await waitFor(() => expect(getCtx().conversations).toHaveLength(1));
      expect(getCtx().conversations[0].conversation_id).toBe('c1');
    });

    it('fetches with Authorization header', async () => {
      renderProvider('user-1', 'my-token');
      await waitFor(() => expect(global.fetch).toHaveBeenCalled());

      const [, options] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
      expect((options as RequestInit).headers).toMatchObject({ Authorization: 'Bearer my-token' });
    });

    it('passes the userId as query param', async () => {
      renderProvider('uid-xyz');
      await waitFor(() => expect(global.fetch).toHaveBeenCalled());

      const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
      expect(url).toContain('user_id=uid-xyz');
    });
  });

  describe('createConversation', () => {
    it('sets pendingConversation=true and clears activeConversationId', async () => {
      const getCtx = renderProvider();
      await waitFor(() => expect(global.fetch).toHaveBeenCalled());
      act(() => { getCtx().createConversation(); });
      expect(getCtx().pendingConversation).toBe(true);
      expect(getCtx().activeConversationId).toBeNull();
    });

    it('clears chatItems and predictedCodes', async () => {
      const getCtx = renderProvider();
      await waitFor(() => expect(global.fetch).toHaveBeenCalled());
      act(() => { getCtx().createConversation(); });
      expect(getCtx().chatItems).toEqual([]);
      expect(getCtx().predictedCodes).toEqual([]);
    });
  });

  describe('switchConversation', () => {
    it('sets activeConversationId and clears pendingConversation', async () => {
      const getCtx = renderProvider();
      await waitFor(() => expect(global.fetch).toHaveBeenCalled());
      act(() => { getCtx().createConversation(); });
      act(() => { getCtx().switchConversation('conv-abc'); });
      expect(getCtx().activeConversationId).toBe('conv-abc');
      expect(getCtx().pendingConversation).toBe(false);
    });
  });

  describe('channel setup after switchConversation', () => {
    async function setupWithChannel() {
      const getCtx = renderProvider();
      await waitFor(() => expect(global.fetch).toHaveBeenCalled());
      act(() => { getCtx().switchConversation('conv-1'); });
      await waitFor(() => expect(mockSocket.channel).toHaveBeenCalledWith('conversation:conv-1', {}));
      return getCtx;
    }

    it('creates a socket channel for the active conversation', async () => {
      await setupWithChannel();
      expect(mockSocket.channel).toHaveBeenCalledWith('conversation:conv-1', {});
    });

    it('registers event handlers on the channel', async () => {
      await setupWithChannel();
      expect(mockChannel.on).toHaveBeenCalledWith('analysis_started', expect.any(Function));
      expect(mockChannel.on).toHaveBeenCalledWith('analysis_complete', expect.any(Function));
      expect(mockChannel.on).toHaveBeenCalledWith('code_validated', expect.any(Function));
      expect(mockChannel.on).toHaveBeenCalledWith('code_rejected', expect.any(Function));
    });
  });

  describe('channel event handlers', () => {
    async function setupWithChannel() {
      const getCtx = renderProvider();
      await waitFor(() => expect(global.fetch).toHaveBeenCalled());
      act(() => { getCtx().switchConversation('conv-1'); });
      await waitFor(() => expect(mockSocket.channel).toHaveBeenCalled());
      return getCtx;
    }

    it('analysis_started sets isAnalyzing=true', async () => {
      const getCtx = await setupWithChannel();
      act(() => { channelEvents['analysis_started']?.({}); });
      expect(getCtx().isAnalyzing).toBe(true);
    });

    it('analysis_complete sets isAnalyzing=false and populates predictedCodes', async () => {
      const getCtx = await setupWithChannel();
      act(() => { channelEvents['analysis_started']?.({}); });
      act(() => {
        channelEvents['analysis_complete']?.({
          message_id: 'msg-1',
          predicted_codes: [{ code_id: 'c1', cie10_code: 'I10', reasoning: 'HTN', confidence: 0.9, status: 'pending' }],
        });
      });
      expect(getCtx().isAnalyzing).toBe(false);
      expect(getCtx().predictedCodes).toHaveLength(1);
      expect(getCtx().predictedCodes[0].cie10_code).toBe('I10');
    });

    it('code_validated updates the code status to validated', async () => {
      const getCtx = await setupWithChannel();
      act(() => {
        channelEvents['analysis_complete']?.({
          message_id: 'msg-1',
          predicted_codes: [{ code_id: 'c1', cie10_code: 'I10', reasoning: 'HTN', confidence: 0.9, status: 'pending' }],
        });
      });
      act(() => { channelEvents['code_validated']?.({ code_id: 'c1' }); });
      expect(getCtx().predictedCodes[0].status).toBe('validated');
    });

    it('analysis_complete injects a suggest card when chatItems has a user message', async () => {
      const getCtx = await setupWithChannel();

      act(() => {
        channelEvents['new_message']?.({
          message_id: 'msg-10',
          content: 'Patient has hypertension',
          user_id: 'user-1',
          timestamp: new Date().toISOString(),
        });
      });
      expect(getCtx().chatItems).toHaveLength(1);

      act(() => {
        channelEvents['analysis_complete']?.({
          message_id: 'msg-10',
          predicted_codes: [{ code_id: 'c1', cie10_code: 'I10', reasoning: 'HTN', confidence: 0.9, status: 'pending' }],
        });
      });

      await waitFor(() => expect(getCtx().chatItems.length).toBeGreaterThan(1));
      const suggestCard = getCtx().chatItems.find((item) => item.kind === 'card' && item.card_type === 'suggest');
      expect(suggestCard).toBeDefined();
    });

    it('analysis_failed sets isAnalyzing=false and shows toast', async () => {
      const getCtx = await setupWithChannel();
      act(() => { channelEvents['analysis_started']?.({}); });
      expect(getCtx().isAnalyzing).toBe(true);

      act(() => { channelEvents['analysis_failed']?.({ error: 'Connection timeout' }); });
      expect(getCtx().isAnalyzing).toBe(false);
    });

    it('code_rejected updates the code status to rejected', async () => {
      const getCtx = await setupWithChannel();
      act(() => {
        channelEvents['analysis_complete']?.({
          message_id: 'msg-1',
          predicted_codes: [{ code_id: 'c2', cie10_code: 'J45', reasoning: 'Asthma', confidence: 0.8, status: 'pending' }],
        });
      });
      act(() => { channelEvents['code_rejected']?.({ code_id: 'c2' }); });
      expect(getCtx().predictedCodes[0].status).toBe('rejected');
    });

    it('new_message appends item to chatItems', async () => {
      const getCtx = await setupWithChannel();
      act(() => {
        channelEvents['new_message']?.({
          message_id: 'msg-10',
          content: 'Hello',
          user_id: 'user-1',
          timestamp: new Date().toISOString(),
        });
      });
      expect(getCtx().chatItems).toHaveLength(1);
      expect(getCtx().chatItems[0].kind).toBe('user');
    });

    it('analysis_card_received appends a card item', async () => {
      const getCtx = await setupWithChannel();
      act(() => {
        channelEvents['analysis_card_received']?.({
          message_id: 'msg-1',
          card_id: 'card-1',
          card_type: 'summary',
          content: 'Summary text',
        });
      });
      expect(getCtx().chatItems).toHaveLength(1);
      const item = getCtx().chatItems[0];
      expect(item.kind).toBe('card');
      if (item.kind === 'card') expect(item.card_type).toBe('summary');
    });
  });

  describe('history restoration on join', () => {
    it('restores messages and analysis cards from history, injects suggest card', async () => {
      const getCtx = renderProvider();
      await waitFor(() => expect(global.fetch).toHaveBeenCalled());
      act(() => { getCtx().switchConversation('conv-hist'); });
      await waitFor(() => expect(mockSocket.channel).toHaveBeenCalled());

      act(() => {
        joinCallbacks['ok']?.({
          status: 'joined',
          history: {
            messages: [
              { message_id: 'msg-h1', content: 'Patient has asthma', user_id: 'user-1', timestamp: new Date().toISOString() },
            ],
            predicted_codes: [{ code_id: 'c1', cie10_code: 'J45', reasoning: 'Asthma', confidence: 0.88, status: 'pending' }],
            analysis_cards: [
              { card_id: 'card-h1', card_type: 'summary', content: 'Summary', position: 0, message_id: 'msg-h1' },
            ],
          },
        });
      });

      await waitFor(() => expect(getCtx().chatItems.length).toBeGreaterThan(0));
      const hasUserMsg = getCtx().chatItems.some((i) => i.kind === 'user');
      const hasCard = getCtx().chatItems.some((i) => i.kind === 'card' && i.card_type === 'summary');
      const hasSuggest = getCtx().chatItems.some((i) => i.kind === 'card' && i.card_type === 'suggest');
      expect(hasUserMsg).toBe(true);
      expect(hasCard).toBe(true);
      expect(hasSuggest).toBe(true);
    });
  });

  describe('analyzeReport', () => {
    it('creates a new conversation when activeConversationId is null', async () => {
      const getCtx = renderProvider();
      await waitFor(() => expect(global.fetch).toHaveBeenCalled());
      act(() => { getCtx().createConversation(); });
      act(() => { getCtx().analyzeReport('Patient report text here'); });
      await waitFor(() => expect(getCtx().activeConversationId).not.toBeNull());
      expect(getCtx().pendingConversation).toBe(false);
    });

    it('sends pending report via channel after auto-created conversation joins', async () => {
      const getCtx = renderProvider();
      await waitFor(() => expect(global.fetch).toHaveBeenCalled());

      act(() => { getCtx().createConversation(); });
      act(() => { getCtx().analyzeReport('Pending report text'); });

      await waitFor(() => expect(mockSocket.channel).toHaveBeenCalled());

      act(() => {
        joinCallbacks['ok']?.({
          status: 'conversation_started',
          history: { messages: [], predicted_codes: [], analysis_cards: [] },
        });
      });

      await waitFor(() =>
        expect(mockChannel.push).toHaveBeenCalledWith('analyze_report', { report_text: 'Pending report text' })
      );
    });

    it('pushes analyze_report to channel when conversation is active', async () => {
      const getCtx = renderProvider();
      await waitFor(() => expect(global.fetch).toHaveBeenCalled());
      act(() => { getCtx().switchConversation('conv-1'); });
      await waitFor(() => expect(mockSocket.channel).toHaveBeenCalled());

      act(() => {
        joinCallbacks['ok']?.({
          status: 'joined',
          history: { messages: [], predicted_codes: [], analysis_cards: [] },
        });
      });

      act(() => { getCtx().analyzeReport('Clinical report text'); });
      expect(mockChannel.push).toHaveBeenCalledWith('analyze_report', { report_text: 'Clinical report text' });
    });
  });

  describe('validateCode / rejectCode', () => {
    async function setupWithActiveChannel() {
      const getCtx = renderProvider();
      await waitFor(() => expect(global.fetch).toHaveBeenCalled());
      act(() => { getCtx().switchConversation('conv-1'); });
      await waitFor(() => expect(mockSocket.channel).toHaveBeenCalled());
      act(() => {
        joinCallbacks['ok']?.({
          status: 'joined',
          history: { messages: [], predicted_codes: [], analysis_cards: [] },
        });
      });
      return getCtx;
    }

    it('validateCode pushes validate_code to channel', async () => {
      const getCtx = await setupWithActiveChannel();
      act(() => { getCtx().validateCode('code-uuid-1', 'I10'); });
      expect(mockChannel.push).toHaveBeenCalledWith('validate_code', { code_id: 'code-uuid-1', cie10_code: 'I10' });
    });

    it('rejectCode pushes reject_code to channel', async () => {
      const getCtx = await setupWithActiveChannel();
      act(() => { getCtx().rejectCode('code-uuid-2', 'J45', 'wrong code'); });
      expect(mockChannel.push).toHaveBeenCalledWith('reject_code', { code_id: 'code-uuid-2', cie10_code: 'J45', reason: 'wrong code' });
    });

    it('validateCode does nothing when channel is null', async () => {
      const getCtx = renderProvider();
      await waitFor(() => expect(global.fetch).toHaveBeenCalled());
      act(() => { getCtx().validateCode('cid', 'I10'); });
      expect(mockChannel.push).not.toHaveBeenCalled();
    });

    it('suggestCode pushes suggest_code to channel', async () => {
      const getCtx = await setupWithActiveChannel();
      act(() => { getCtx().suggestCode('hipertensión', 'I10'); });
      expect(mockChannel.push).toHaveBeenCalledWith('suggest_code', {
        selected_text: 'hipertensión',
        suggested_code: 'I10',
      });
    });

    it('suggestCode does nothing when channel is null', async () => {
      const getCtx = renderProvider();
      await waitFor(() => expect(global.fetch).toHaveBeenCalled());
      act(() => { getCtx().suggestCode('text', 'I10'); });
      expect(mockChannel.push).not.toHaveBeenCalled();
    });
  });

  describe('deleteConversation', () => {
    it('removes the conversation from the list on success', async () => {
      const convs = [
        { conversation_id: 'del-1', started_at: new Date().toISOString(), status: 'active', deleted_at: null, message_count: 0, last_message: null },
        { conversation_id: 'keep-2', started_at: new Date().toISOString(), status: 'active', deleted_at: null, message_count: 0, last_message: null },
      ];
      mockFetch({ conversations: convs });
      const getCtx = renderProvider();
      await waitFor(() => expect(getCtx().conversations).toHaveLength(2));

      (global.fetch as ReturnType<typeof vi.fn>)
        .mockResolvedValueOnce({ ok: true, json: async () => ({}) } as Response)
        .mockResolvedValueOnce({ ok: true, json: async () => ({ conversations: [] }) } as Response);

      act(() => { void getCtx().deleteConversation('del-1'); });

      await waitFor(() =>
        expect(getCtx().conversations.find((c) => c.conversation_id === 'del-1')).toBeUndefined()
      );
      expect(getCtx().conversations.find((c) => c.conversation_id === 'keep-2')).toBeDefined();
    });

    it('clears active conversation when deleting the active one', async () => {
      const convs = [{ conversation_id: 'active-1', started_at: new Date().toISOString(), status: 'active', deleted_at: null, message_count: 0, last_message: null }];
      mockFetch({ conversations: convs });
      const getCtx = renderProvider();
      await waitFor(() => expect(getCtx().conversations).toHaveLength(1));

      act(() => { getCtx().switchConversation('active-1'); });

      (global.fetch as ReturnType<typeof vi.fn>)
        .mockResolvedValueOnce({ ok: true, json: async () => ({}) } as Response)
        .mockResolvedValueOnce({ ok: true, json: async () => ({ conversations: [] }) } as Response);

      act(() => { void getCtx().deleteConversation('active-1'); });

      await waitFor(() => expect(getCtx().activeConversationId).toBeNull());
    });

    it('shows toast error when deleteConversation fetch throws', async () => {
      const { toast } = await import('sonner');
      const convs = [{ conversation_id: 'err-1', started_at: new Date().toISOString(), status: 'active', deleted_at: null, message_count: 0, last_message: null }];
      mockFetch({ conversations: convs });
      const getCtx = renderProvider();
      await waitFor(() => expect(getCtx().conversations).toHaveLength(1));

      global.fetch = vi.fn().mockRejectedValue(new Error('Network error'));

      act(() => { void getCtx().deleteConversation('err-1'); });

      await waitFor(() => expect(toast.error).toHaveBeenCalled());
    });
  });

  describe('restoreConversation', () => {
    it('removes conversation from trashed list on success', async () => {
      mockFetch({ conversations: [] });
      const getCtx = renderProvider();
      await waitFor(() => expect(global.fetch).toHaveBeenCalled());

      (global.fetch as ReturnType<typeof vi.fn>)
        .mockResolvedValueOnce({ ok: true, json: async () => ({}) } as Response)
        .mockResolvedValueOnce({ ok: true, json: async () => ({ conversations: [] }) } as Response)
        .mockResolvedValueOnce({ ok: true, json: async () => ({ conversations: [] }) } as Response);

      act(() => { void getCtx().restoreConversation('trash-1'); });

      await waitFor(() => {
        const calls = (global.fetch as ReturnType<typeof vi.fn>).mock.calls;
        return expect(calls.some((call) => (call[0] as string).includes('trash-1/restore'))).toBe(true);
      });
    });

    it('shows toast error when restoreConversation fetch throws', async () => {
      const { toast } = await import('sonner');
      mockFetch({ conversations: [] });
      const getCtx = renderProvider();
      await waitFor(() => expect(global.fetch).toHaveBeenCalled());

      global.fetch = vi.fn().mockRejectedValue(new Error('Network error'));

      act(() => { void getCtx().restoreConversation('trash-2'); });

      await waitFor(() => expect(toast.error).toHaveBeenCalled());
    });
  });

  async function conCanalActivo(getCtx: () => ReturnType<typeof useConversation>) {
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    act(() => { getCtx().switchConversation('conv-1'); });
    await waitFor(() => expect(mockSocket.channel).toHaveBeenCalled());
    act(() => {
      joinCallbacks['ok']?.({
        status: 'joined',
        history: { messages: [], predicted_codes: [], analysis_cards: [] },
      });
    });
    return getCtx;
  }

  describe('sesión caducada', () => {
    it('un 401 avisa al usuario y dispara el cierre de sesión', async () => {
      const { toast } = await import('sonner');
      const onUnauthorized = vi.fn();
      global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 401, json: async () => ({}) } as Response);

      renderProvider('user-1', 'tok-caducado', onUnauthorized);

      await waitFor(() => expect(onUnauthorized).toHaveBeenCalled());
      expect(toast.error).toHaveBeenCalled();
    });
  });

  describe('papelera', () => {
    function fetchPorRuta(papelera: unknown[], activas: unknown[] = []) {
      global.fetch = vi.fn((url: string) =>
        Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ conversations: url.includes('/trash') ? papelera : activas }),
        } as Response)
      ) as unknown as typeof fetch;
    }

    const borrada = {
      conversation_id: 'papelera-1',
      started_at: new Date().toISOString(),
      status: 'active',
      deleted_at: new Date().toISOString(),
      message_count: 2,
      last_message: null,
    };

    it('carga las conversaciones borradas al montar', async () => {
      fetchPorRuta([borrada]);
      const getCtx = renderProvider();
      await waitFor(() => expect(getCtx().trashedConversations).toHaveLength(1));
      expect(getCtx().trashedConversations[0].conversation_id).toBe('papelera-1');
    });

    it('si la papelera no responde, el resto de la pantalla sigue funcionando', async () => {
      global.fetch = vi.fn((url: string) =>
        Promise.resolve({
          ok: !url.includes('/trash'),
          status: url.includes('/trash') ? 500 : 200,
          json: async () => ({ conversations: [] }),
        } as Response)
      ) as unknown as typeof fetch;

      const getCtx = renderProvider();
      await waitFor(() => expect(global.fetch).toHaveBeenCalled());
      expect(getCtx().trashedConversations).toEqual([]);
    });

    it('un fallo de red al listar conversaciones se le dice al usuario', async () => {
      const { toast } = await import('sonner');
      global.fetch = vi.fn().mockRejectedValue(new Error('sin red'));

      renderProvider();
      await waitFor(() => expect(toast.error).toHaveBeenCalled());
    });
  });

  describe('resumen en streaming', () => {
    it('el primer token crea la tarjeta de resumen', async () => {
      const getCtx = await conCanalActivo(renderProvider());
      act(() => { channelEvents['summary_token']?.({ message_id: 'm1', token: 'Paciente ' }); });

      const tarjeta = getCtx().chatItems[0];
      expect(tarjeta.kind).toBe('card');
      if (tarjeta.kind === 'card') {
        expect(tarjeta.card_id).toBe('streaming-summary-m1');
        expect(tarjeta.content).toBe('Paciente ');
      }
    });

    it('los tokens siguientes se van concatenando en la misma tarjeta', async () => {
      const getCtx = await conCanalActivo(renderProvider());
      act(() => { channelEvents['summary_token']?.({ message_id: 'm1', token: 'Paciente ' }); });
      act(() => { channelEvents['summary_token']?.({ message_id: 'm1', token: 'con disnea' }); });

      expect(getCtx().chatItems).toHaveLength(1);
      const tarjeta = getCtx().chatItems[0];
      if (tarjeta.kind === 'card') expect(tarjeta.content).toBe('Paciente con disnea');
    });

    it('la tarjeta definitiva sustituye al buffer en vez de duplicarlo', async () => {
      const getCtx = await conCanalActivo(renderProvider());
      act(() => { channelEvents['summary_token']?.({ message_id: 'm1', token: 'borrador' }); });
      act(() => {
        channelEvents['analysis_card_received']?.({
          message_id: 'm1',
          card_id: 'card-final',
          card_type: 'summary',
          content: 'Resumen definitivo',
        });
      });

      expect(getCtx().chatItems).toHaveLength(1);
      const tarjeta = getCtx().chatItems[0];
      if (tarjeta.kind === 'card') {
        expect(tarjeta.card_id).toBe('card-final');
        expect(tarjeta.content).toBe('Resumen definitivo');
      }
    });

    it('la misma tarjeta no se añade dos veces si el evento llega repetido', async () => {
      const getCtx = await conCanalActivo(renderProvider());
      const carga = { message_id: 'm1', card_id: 'card-1', card_type: 'summary', content: 'texto' };
      act(() => { channelEvents['analysis_card_received']?.(carga); });
      act(() => { channelEvents['analysis_card_received']?.(carga); });

      expect(getCtx().chatItems).toHaveLength(1);
    });

    it('al terminar el análisis el buffer deja de estar en curso', async () => {
      const getCtx = await conCanalActivo(renderProvider());
      act(() => { channelEvents['summary_token']?.({ message_id: 'm1', token: 'texto' }); });
      act(() => { channelEvents['analysis_complete']?.({ message_id: 'm1' }); });

      const tarjeta = getCtx().chatItems[0];
      // Con el id de streaming la tarjeta se quedaría "escribiendo" para siempre
      if (tarjeta.kind === 'card') expect(tarjeta.card_id).toBe('done-summary-m1');
    });
  });

  describe('términos explicativos en segunda petición', () => {
    async function conTarjetaDeCodigos(codigos: unknown[]) {
      const getCtx = await conCanalActivo(renderProvider());
      act(() => {
        channelEvents['analysis_card_received']?.({
          message_id: 'm1',
          card_id: 'card-codes',
          card_type: 'codes',
          content: codigos,
        });
      });
      return getCtx;
    }

    function codigosDe(getCtx: () => ReturnType<typeof useConversation>) {
      const tarjeta = getCtx().chatItems.find((i) => i.kind === 'card' && i.card_type === 'codes');
      if (!tarjeta || tarjeta.kind !== 'card') throw new Error('no hay tarjeta de códigos');
      return tarjeta.content as { code: string; triggers?: string[]; trigger_detail?: { term: string; source: string }[]; triggers_complete?: boolean }[];
    }

    it('rellena los términos cuando llegan', async () => {
      const getCtx = await conTarjetaDeCodigos([{ code: 'I10', confidence: 0.9 }]);
      act(() => {
        channelEvents['triggers_received']?.({
          message_id: 'm1',
          method: 'gradiente_filtrado',
          triggers: { I10: [{ term: 'hipertensión', source: 'bert', weight: 0.4 }] },
        });
      });

      const [codigo] = codigosDe(getCtx);
      expect(codigo.triggers).toEqual(['hipertensión']);
      expect(codigo.triggers_complete).toBe(true);
    });

    it('conserva los términos del diccionario y añade los del modelo', async () => {
      const getCtx = await conTarjetaDeCodigos([
        { code: 'I10', confidence: 0.9, trigger_detail: [{ term: 'HTA', source: 'dict', weight: null }] },
      ]);
      act(() => {
        channelEvents['triggers_received']?.({
          message_id: 'm1',
          method: 'gradiente_filtrado',
          triggers: { I10: [{ term: 'tensión', source: 'bert', weight: 0.3 }] },
        });
      });

      const [codigo] = codigosDe(getCtx);
      expect(codigo.trigger_detail?.map((d) => d.source)).toEqual(['dict', 'bert']);
    });

    it('un término que aportan los dos motores aparece una sola vez', async () => {
      const getCtx = await conTarjetaDeCodigos([
        { code: 'I10', confidence: 0.9, trigger_detail: [{ term: 'Hipertensión', source: 'dict', weight: null }] },
      ]);
      act(() => {
        channelEvents['triggers_received']?.({
          message_id: 'm1',
          method: 'gradiente_filtrado',
          triggers: { I10: [{ term: 'hipertensión', source: 'bert', weight: 0.5 }] },
        });
      });

      const [codigo] = codigosDe(getCtx);
      expect(codigo.triggers).toEqual(['Hipertensión']);
    });

    it('un código sin términos deja de esperar en vez de quedarse cargando', async () => {
      const getCtx = await conTarjetaDeCodigos([{ code: 'I10', confidence: 0.9 }, { code: 'J45', confidence: 0.6 }]);
      act(() => {
        channelEvents['triggers_received']?.({
          message_id: 'm1',
          method: 'gradiente_filtrado',
          triggers: { I10: [{ term: 'hipertensión', source: 'bert', weight: 0.4 }] },
        });
      });

      const [, segundo] = codigosDe(getCtx);
      expect(segundo.triggers_complete).toBe(true);
      expect(segundo.triggers).toBeUndefined();
    });

    it('no toca las tarjetas de otro mensaje ni las que no son de códigos', async () => {
      const getCtx = await conTarjetaDeCodigos([{ code: 'I10', confidence: 0.9 }]);
      act(() => {
        channelEvents['analysis_card_received']?.({
          message_id: 'm2',
          card_id: 'card-otro',
          card_type: 'summary',
          content: 'Resumen de otro mensaje',
        });
      });
      act(() => {
        channelEvents['triggers_received']?.({
          message_id: 'm2',
          method: 'gradiente_filtrado',
          triggers: { I10: [{ term: 'hipertensión', source: 'bert', weight: 0.4 }] },
        });
      });

      expect(codigosDe(getCtx)[0].triggers_complete).toBeUndefined();
      const otra = getCtx().chatItems.find((i) => i.kind === 'card' && i.card_id === 'card-otro');
      if (otra && otra.kind === 'card') expect(otra.content).toBe('Resumen de otro mensaje');
    });
  });

  describe('verificación de términos', () => {
    async function conCodigoPredicho() {
      const getCtx = await conCanalActivo(renderProvider());
      act(() => {
        channelEvents['analysis_complete']?.({
          message_id: 'm1',
          predicted_codes: [{ code_id: 'c1', cie10_code: 'I10', reasoning: 'HTA', confidence: 0.9, status: 'pending', verified_triggers: [] }],
        });
      });
      return getCtx;
    }

    it('marca el término antes de que responda el servidor', async () => {
      const getCtx = await conCodigoPredicho();
      act(() => { getCtx().verifyTrigger('c1', 'hipertensión', true); });

      expect(getCtx().predictedCodes[0].verified_triggers).toEqual(['hipertensión']);
      expect(mockChannel.push).toHaveBeenCalledWith('verify_trigger', {
        code_id: 'c1', trigger: 'hipertensión', verified: true,
      });
    });

    it('desmarcar quita el término', async () => {
      const getCtx = await conCodigoPredicho();
      act(() => { getCtx().verifyTrigger('c1', 'hipertensión', true); });
      act(() => { getCtx().verifyTrigger('c1', 'hipertensión', false); });

      expect(getCtx().predictedCodes[0].verified_triggers).toEqual([]);
    });

    it('marcar dos veces el mismo término no lo duplica', async () => {
      const getCtx = await conCodigoPredicho();
      act(() => { getCtx().verifyTrigger('c1', 'hipertensión', true); });
      act(() => { getCtx().verifyTrigger('c1', 'hipertensión', true); });

      expect(getCtx().predictedCodes[0].verified_triggers).toEqual(['hipertensión']);
    });

    it('no toca los códigos que no son el indicado', async () => {
      const getCtx = await conCodigoPredicho();
      act(() => { getCtx().verifyTrigger('otro-id', 'hipertensión', true); });

      expect(getCtx().predictedCodes[0].verified_triggers).toEqual([]);
    });

    it('sin canal no intenta enviar nada', async () => {
      const getCtx = renderProvider();
      await waitFor(() => expect(global.fetch).toHaveBeenCalled());
      act(() => { getCtx().verifyTrigger('c1', 'hipertensión', true); });

      expect(mockChannel.push).not.toHaveBeenCalled();
    });

    it('el servidor puede corregir la lista de términos verificados', async () => {
      const getCtx = await conCodigoPredicho();
      act(() => { channelEvents['trigger_verified']?.({ code_id: 'c1', verified_triggers: ['hipertensión', 'HTA'] }); });

      expect(getCtx().predictedCodes[0].verified_triggers).toEqual(['hipertensión', 'HTA']);
    });
  });

  describe('fallos al hablar con el canal', () => {
    it('un análisis fallido cierra la tarjeta de resumen a medio escribir', async () => {
      const getCtx = await conCanalActivo(renderProvider());
      act(() => { channelEvents['summary_token']?.({ message_id: 'm1', token: 'Paciente con' }); });

      const antes = getCtx().chatItems[0];
      if (antes.kind === 'card') expect(antes.card_id).toBe('streaming-summary-m1');

      act(() => { channelEvents['analysis_failed']?.({ error: 'el motor no responde' }); });

      // Sin esto la tarjeta se queda con el indicador de "escribiendo" para siempre, porque
      // el evento que lo retira es analysis_complete y ya no va a llegar.
      const despues = getCtx().chatItems[0];
      if (despues.kind === 'card') {
        expect(despues.card_id).toBe('done-summary-m1');
        expect(despues.content).toBe('Paciente con');
      }
    });

    it('avisa si no se puede entrar en la conversación', async () => {
      const { toast } = await import('sonner');
      const getCtx = renderProvider();
      await waitFor(() => expect(global.fetch).toHaveBeenCalled());
      act(() => { getCtx().switchConversation('conv-1'); });
      await waitFor(() => expect(mockSocket.channel).toHaveBeenCalled());

      act(() => { joinCallbacks['error']?.({}); });

      expect(toast.error).toHaveBeenCalled();
    });

    it('avisa si falla el envío del informe', async () => {
      const { toast } = await import('sonner');
      const getCtx = await conCanalActivo(renderProvider());
      pushRespondeCon = 'error';

      act(() => { getCtx().analyzeReport('Informe clínico'); });

      expect(toast.error).toHaveBeenCalled();
    });

    it('avisa si falla el envío del informe pendiente al entrar', async () => {
      const { toast } = await import('sonner');
      const getCtx = renderProvider();
      await waitFor(() => expect(global.fetch).toHaveBeenCalled());
      act(() => { getCtx().createConversation(); });
      act(() => { getCtx().analyzeReport('Informe pendiente'); });
      await waitFor(() => expect(mockSocket.channel).toHaveBeenCalled());

      pushRespondeCon = 'error';
      act(() => {
        joinCallbacks['ok']?.({ status: 'conversation_started', history: { messages: [], predicted_codes: [], analysis_cards: [] } });
      });

      expect(toast.error).toHaveBeenCalled();
    });

    it('avisa si falla la validación de un código', async () => {
      const { toast } = await import('sonner');
      const getCtx = await conCanalActivo(renderProvider());
      pushRespondeCon = 'error';

      act(() => { getCtx().validateCode('c1', 'I10'); });

      expect(toast.error).toHaveBeenCalled();
    });

    it('avisa si falla el rechazo de un código', async () => {
      const { toast } = await import('sonner');
      const getCtx = await conCanalActivo(renderProvider());
      pushRespondeCon = 'error';

      act(() => { getCtx().rejectCode('c1', 'I10', 'no procede'); });

      expect(toast.error).toHaveBeenCalled();
    });

    it('avisa si falla una sugerencia', async () => {
      const { toast } = await import('sonner');
      const getCtx = await conCanalActivo(renderProvider());
      pushRespondeCon = 'error';

      act(() => { getCtx().suggestCode('disnea', 'R06.0'); });

      expect(toast.error).toHaveBeenCalled();
    });

    it('confirma al usuario que la sugerencia quedó guardada', async () => {
      const { toast } = await import('sonner');
      const getCtx = await conCanalActivo(renderProvider());
      pushRespondeCon = 'ok';

      act(() => { getCtx().suggestCode('disnea', 'R06.0'); });

      expect(toast.success).toHaveBeenCalled();
    });

    it('rejectCode sin canal no envía nada', async () => {
      const getCtx = renderProvider();
      await waitFor(() => expect(global.fetch).toHaveBeenCalled());
      act(() => { getCtx().rejectCode('c1', 'I10', 'motivo'); });

      expect(mockChannel.push).not.toHaveBeenCalled();
    });
  });

  describe('cambio de conversación', () => {
    it('sale del canal anterior antes de entrar en el siguiente', async () => {
      const getCtx = renderProvider();
      await waitFor(() => expect(global.fetch).toHaveBeenCalled());
      act(() => { getCtx().switchConversation('conv-1'); });
      await waitFor(() => expect(mockSocket.channel).toHaveBeenCalledWith('conversation:conv-1', {}));

      act(() => { getCtx().switchConversation('conv-2'); });
      await waitFor(() => expect(mockSocket.channel).toHaveBeenCalledWith('conversation:conv-2', {}));

      // Si no, se acumulan suscripciones y cada evento llega varias veces
      expect(mockChannel.leave).toHaveBeenCalled();
    });

    it('vacía el chat al cambiar de conversación', async () => {
      const getCtx = renderProvider();
      await waitFor(() => expect(global.fetch).toHaveBeenCalled());
      act(() => { getCtx().switchConversation('conv-1'); });
      await waitFor(() => expect(mockSocket.channel).toHaveBeenCalled());
      act(() => { channelEvents['new_message']?.({ message_id: 'm1', content: 'hola', user_id: 'user-1', timestamp: new Date().toISOString() }); });
      expect(getCtx().chatItems).toHaveLength(1);

      act(() => { getCtx().switchConversation('conv-2'); });

      expect(getCtx().chatItems).toEqual([]);
    });

    it('guarda el motor que resolvió el análisis', async () => {
      const getCtx = await conCanalActivo(renderProvider());
      act(() => { channelEvents['analysis_complete']?.({ message_id: 'm1', engine: 'fused' }); });

      expect(getCtx().engine).toBe('fused');
    });
  });
});
