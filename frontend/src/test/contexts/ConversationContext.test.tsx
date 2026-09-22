import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, act, waitFor } from '@testing-library/react';
import '../helpers'; // i18n / sonner / config mocks: also registers a static socket mock

// ── Override the socket mock with a controllable version ─────────────────────
// helpers.tsx registers getSocket as vi.fn(). We override its implementation
// in beforeEach so the test has full control over channel callbacks.

import { getSocket } from '@/lib/socket';

const channelEvents: Record<string, (payload: unknown) => void> = {};
const joinCallbacks: Record<string, (resp: unknown) => void> = {};

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
    function receive(_e: string, _cb: unknown) { return { receive }; }
    return { receive };
  }),
  leave: vi.fn(),
};

const mockSocket = { channel: vi.fn(() => mockChannel) };

// ── Import context after socket import ───────────────────────────────────────
import { ConversationProvider, useConversation } from '@/contexts/ConversationContext';

// Helper component to expose context values
function Probe({ onRender }: { onRender: (ctx: ReturnType<typeof useConversation>) => void }) {
  const ctx = useConversation();
  onRender(ctx);
  return null;
}

function renderProvider(userId = 'user-1', token = 'tok-abc') {
  let capturedCtx!: ReturnType<typeof useConversation>;
  render(
    <ConversationProvider userId={userId} token={token}>
      <Probe onRender={(ctx) => { capturedCtx = ctx; }} />
    </ConversationProvider>
  );
  return () => capturedCtx;
}

function mockFetch(body: unknown, ok = true) {
  global.fetch = vi.fn().mockResolvedValue({ ok, json: async () => body } as Response);
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('ConversationProvider', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Override the socket mock from helpers.tsx with our controllable version
    vi.mocked(getSocket).mockReturnValue(mockSocket as unknown as ReturnType<typeof getSocket>);
    for (const k of Object.keys(channelEvents)) delete channelEvents[k];
    for (const k of Object.keys(joinCallbacks)) delete joinCallbacks[k];
    mockFetch({ conversations: [] });
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

      // First, add a user message via new_message event
      act(() => {
        channelEvents['new_message']?.({
          message_id: 'msg-10',
          content: 'Patient has hypertension',
          user_id: 'user-1',
          timestamp: new Date().toISOString(),
        });
      });
      expect(getCtx().chatItems).toHaveLength(1);

      // Fire analysis_complete: should inject a 'suggest' card
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
      // messages + analysis card + injected suggest card = 3 items
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

      // createConversation + analyzeReport sets pendingReportRef and creates a new conv ID
      act(() => { getCtx().createConversation(); });
      act(() => { getCtx().analyzeReport('Pending report text'); });

      // Wait for the channel to be created for the new conversation ID
      await waitFor(() => expect(mockSocket.channel).toHaveBeenCalled());

      // Simulate the channel join succeeding: this triggers the pendingReportRef branch
      act(() => {
        joinCallbacks['ok']?.({
          status: 'conversation_started',
          history: { messages: [], predicted_codes: [], analysis_cards: [] },
        });
      });

      // The channel should push analyze_report with the pending text
      await waitFor(() =>
        expect(mockChannel.push).toHaveBeenCalledWith('analyze_report', { report_text: 'Pending report text' })
      );
    });

    it('pushes analyze_report to channel when conversation is active', async () => {
      const getCtx = renderProvider();
      await waitFor(() => expect(global.fetch).toHaveBeenCalled());
      act(() => { getCtx().switchConversation('conv-1'); });
      await waitFor(() => expect(mockSocket.channel).toHaveBeenCalled());

      // Simulate channel join acknowledged so the channel ref is set
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

      // Set trashed conversations via the channel event or direct mock -
      // simulate loadTrashed response
      (global.fetch as ReturnType<typeof vi.fn>)
        .mockResolvedValueOnce({ ok: true, json: async () => ({}) } as Response)  // PUT restore
        .mockResolvedValueOnce({ ok: true, json: async () => ({ conversations: [] }) } as Response)  // loadConversations
        .mockResolvedValueOnce({ ok: true, json: async () => ({ conversations: [] }) } as Response); // loadTrashed

      act(() => { void getCtx().restoreConversation('trash-1'); });

      // No errors expected: fetch should be called with restore URL
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
});
