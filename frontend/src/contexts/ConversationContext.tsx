'use client';

import { createContext, useContext, useState, useEffect, useCallback, ReactNode, useRef } from 'react';
import { Channel } from 'phoenix';
import { toast } from 'sonner';
import { getSocket } from '@/lib/socket';
import { config } from '@/lib/config';
import { useI18n } from '@/contexts/I18nContext';

export interface UserMessage {
  kind: 'user';
  message_id: string;
  content: string;
  timestamp: string;
}

export interface AnalysisCard {
  kind: 'card';
  card_id: string;
  message_id: string;
  card_type: 'summary' | 'codes' | 'recommendations' | 'text' | 'suggest';
  content: string | AnalysisCode[];
}

export interface AnalysisCode {
  code: string;
  description?: string;
  reason?: string;
  reasoning?: string;
  confidence: number;
  // for validation (populated from predictedCodes)
  code_id?: string;
  status?: 'pending' | 'validated' | 'rejected';
}

export type ChatItem = UserMessage | AnalysisCard;

export interface PredictedCode {
  code_id: string;
  cie10_code: string;
  reasoning: string;
  confidence: number;
  status: 'pending' | 'validated' | 'rejected';
}

export interface ConversationSummary {
  conversation_id: string;
  started_at: string;
  status: string;
  deleted_at: string | null;
  message_count: number;
  last_message: { content: string; timestamp: string } | null;
}

interface ConversationContextType {
  userId: string;
  conversations: ConversationSummary[];
  trashedConversations: ConversationSummary[];
  activeConversationId: string | null;
  /** True when the user clicked "Nuevo análisis" but hasn't submitted a report yet */
  pendingConversation: boolean;
  chatItems: ChatItem[];
  predictedCodes: PredictedCode[];
  isAnalyzing: boolean;
  createConversation: () => void;
  switchConversation: (conversationId: string) => void;
  analyzeReport: (reportText: string) => void;
  validateCode: (codeId: string, cie10Code: string) => void;
  rejectCode: (codeId: string, cie10Code: string, reason: string) => void;
  suggestCode: (selectedText: string, suggestedCode: string) => void;
  deleteConversation: (conversationId: string) => void;
  restoreConversation: (conversationId: string) => void;
}

const ConversationContext = createContext<ConversationContextType | undefined>(undefined);

export function ConversationProvider({ children, userId, token }: { children: ReactNode; userId: string; token: string }) {
  const { t } = useI18n();
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [channel, setChannel] = useState<Channel | null>(null);
  const [chatItems, setChatItems] = useState<ChatItem[]>([]);
  const [predictedCodes, setPredictedCodes] = useState<PredictedCode[]>([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [pendingConversation, setPendingConversation] = useState(false);
  const [trashedConversations, setTrashedConversations] = useState<ConversationSummary[]>([]);
  const channelRef = useRef<Channel | null>(null);
  const pendingReportRef = useRef<string | null>(null);

  const loadTrashed = useCallback(async () => {
    try {
      const res = await fetch(`${config.apiUrl}/conversations/trash?user_id=${encodeURIComponent(userId)}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      setTrashedConversations(data.conversations ?? []);
    } catch {
      // silent — trash load failure is non-critical
    }
  }, [userId, token]);

  const loadConversations = useCallback(async () => {
    try {
      const res = await fetch(`${config.apiUrl}/conversations?user_id=${encodeURIComponent(userId)}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      setConversations(data.conversations ?? []);
    } catch {
      toast.error(t('errors.load_conversations'));
    }
  }, [userId, token, t]);

  useEffect(() => {
    loadConversations();
    loadTrashed();
  }, [loadConversations, loadTrashed]);

  useEffect(() => {
    if (!activeConversationId) return;

    if (channelRef.current) {
      channelRef.current.leave();
      channelRef.current = null;
    }

    setChatItems([]);
    setPredictedCodes([]);
    setIsAnalyzing(false);

    const socket = getSocket(token);
    const ch = socket.channel(`conversation:${activeConversationId}`, {});

    ch.join()
      .receive('ok', (resp: { status: string; history?: { messages: { message_id: string; content: string; user_id: string; timestamp: string }[]; predicted_codes: PredictedCode[]; analysis_cards: AnalysisCard[] } }) => {
        if (resp.history) {
          const items: ChatItem[] = [];
          for (const msg of resp.history.messages ?? []) {
            items.push({ kind: 'user', message_id: msg.message_id, content: msg.content, timestamp: msg.timestamp });
          }
          for (const card of resp.history.analysis_cards ?? []) {
            items.push({ ...card, kind: 'card' });
          }
          // Re-inject suggestion card if analysis was done
          const hasAnalysis = (resp.history.analysis_cards ?? []).length > 0;
          const reportMsg = items.find((item) => item.kind === 'user');
          if (hasAnalysis && reportMsg && reportMsg.kind === 'user') {
            items.push({
              kind: 'card' as const,
              card_id: `suggest-history-${reportMsg.message_id}`,
              message_id: reportMsg.message_id,
              card_type: 'suggest' as const,
              content: reportMsg.content,
            });
          }
          setChatItems(items);
          setPredictedCodes(resp.history.predicted_codes ?? []);
        }
        // Send pending report if this channel was created by analyzeReport
        if (pendingReportRef.current) {
          const text = pendingReportRef.current;
          pendingReportRef.current = null;
          ch.push('analyze_report', { report_text: text })
            .receive('error', () => toast.error(t('errors.analyze_failed')));
        }
        loadConversations();
      })
      .receive('error', () => toast.error(t('errors.join_failed')));

    ch.on('new_message', (payload: { message_id: string; content: string; user_id: string; timestamp: string }) => {
      setChatItems((prev) => [...prev, {
        kind: 'user',
        message_id: payload.message_id,
        content: payload.content,
        timestamp: payload.timestamp,
      }]);
      loadConversations();
    });

    ch.on('analysis_started', () => setIsAnalyzing(true));

    ch.on('analysis_card_received', (payload: { message_id: string; card_id: string; card_type: AnalysisCard['card_type']; content: string | AnalysisCode[] }) => {
      setChatItems((prev) => [...prev, {
        kind: 'card',
        card_id: payload.card_id,
        message_id: payload.message_id,
        card_type: payload.card_type,
        content: payload.content,
      }]);
    });

    ch.on('analysis_complete', (payload: { message_id: string; predicted_codes?: PredictedCode[] }) => {
      setIsAnalyzing(false);
      if (payload.predicted_codes?.length) setPredictedCodes(payload.predicted_codes);
      // Inject suggestion card so user can annotate the report text
      setChatItems((prev) => {
        if (prev.some((item) => item.kind === 'card' && item.card_type === 'suggest')) return prev;
        const reportMsg = prev.find((item) => item.kind === 'user');
        if (!reportMsg || reportMsg.kind !== 'user') return prev;
        return [...prev, {
          kind: 'card' as const,
          card_id: `suggest-${Date.now()}`,
          message_id: reportMsg.message_id,
          card_type: 'suggest' as const,
          content: reportMsg.content,
        }];
      });
      loadConversations();
    });

    ch.on('analysis_failed', (payload: { error: string }) => {
      setIsAnalyzing(false);
      toast.error(t('errors.analysis_failed', { error: payload.error }));
    });

    ch.on('code_validated', (payload: { code_id: string }) => {
      setPredictedCodes((prev) =>
        prev.map((c) => c.code_id === payload.code_id ? { ...c, status: 'validated' as const } : c)
      );
    });

    ch.on('code_rejected', (payload: { code_id: string }) => {
      setPredictedCodes((prev) =>
        prev.map((c) => c.code_id === payload.code_id ? { ...c, status: 'rejected' as const } : c)
      );
    });

    channelRef.current = ch;
    setChannel(ch);

    return () => {
      ch.leave();
      channelRef.current = null;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeConversationId, token, loadConversations]);

  const createConversation = useCallback(() => {
    setActiveConversationId(null);
    setChatItems([]);
    setPredictedCodes([]);
    setPendingConversation(true);
  }, []);

  const switchConversation = useCallback((conversationId: string) => {
    setPendingConversation(false);
    setActiveConversationId(conversationId);
  }, []);

  const analyzeReport = useCallback((reportText: string) => {
    if (!activeConversationId) {
      // First report in a new conversation — create the conversation now
      const newId = `conv-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
      pendingReportRef.current = reportText;
      setPendingConversation(false);
      setActiveConversationId(newId);
    } else if (channel) {
      channel.push('analyze_report', { report_text: reportText })
        .receive('error', () => toast.error(t('errors.analyze_failed')));
    }
  }, [activeConversationId, channel, t]);

  const validateCode = useCallback((codeId: string, cie10Code: string) => {
    if (!channel) return;
    channel.push('validate_code', { code_id: codeId, cie10_code: cie10Code })
      .receive('error', () => toast.error(t('errors.validate_failed')));
  }, [channel, t]);

  const rejectCode = useCallback((codeId: string, cie10Code: string, reason: string) => {
    if (!channel) return;
    channel.push('reject_code', { code_id: codeId, cie10_code: cie10Code, reason })
      .receive('error', () => toast.error(t('errors.reject_failed')));
  }, [channel, t]);

  const suggestCode = useCallback((selectedText: string, suggestedCode: string) => {
    if (!channel) return;
    channel.push('suggest_code', { selected_text: selectedText, suggested_code: suggestedCode })
      .receive('ok', () => toast.success(t('cards.suggestion_saved')))
      .receive('error', () => toast.error(t('errors.suggest_failed')));
  }, [channel, t]);

  const deleteConversation = useCallback(async (conversationId: string) => {
    try {
      await fetch(`${config.apiUrl}/conversations/${conversationId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      setConversations((prev) => prev.filter((c) => c.conversation_id !== conversationId));
      loadTrashed();
      if (activeConversationId === conversationId) {
        setActiveConversationId(null);
        setChatItems([]);
        setPredictedCodes([]);
      }
    } catch {
      toast.error(t('errors.delete_failed'));
    }
  }, [token, activeConversationId, loadTrashed, t]);

  const restoreConversation = useCallback(async (conversationId: string) => {
    try {
      await fetch(`${config.apiUrl}/conversations/${conversationId}/restore`, {
        method: 'PUT',
        headers: { Authorization: `Bearer ${token}` },
      });
      setTrashedConversations((prev) => prev.filter((c) => c.conversation_id !== conversationId));
      loadConversations();
    } catch {
      toast.error(t('errors.restore_failed'));
    }
  }, [token, loadConversations, t]);

  return (
    <ConversationContext.Provider
      value={{
        userId,
        conversations,
        trashedConversations,
        activeConversationId,
        pendingConversation,
        chatItems,
        predictedCodes,
        isAnalyzing,
        createConversation,
        switchConversation,
        analyzeReport,
        validateCode,
        rejectCode,
        suggestCode,
        deleteConversation,
        restoreConversation,
      }}
    >
      {children}
    </ConversationContext.Provider>
  );
}

export function useConversation() {
  const context = useContext(ConversationContext);
  if (!context) throw new Error('useConversation must be used within ConversationProvider');
  return context;
}
