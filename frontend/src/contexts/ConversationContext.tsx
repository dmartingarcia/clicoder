'use client';

import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { Channel } from 'phoenix';
import { getSocket } from '@/lib/socket';

interface Message {
  message_id: string;
  content: string;
  user_id: string;
  timestamp: string;
  type: 'user_message' | 'ai_response';
}

interface PredictedCode {
  code_id: string;
  cie10_code: string;
  reasoning: string;
  confidence: number;
  status: 'pending' | 'validated' | 'rejected';
}

interface ConversationContextType {
  conversationId: string;
  messages: Message[];
  predictedCodes: PredictedCode[];
  isAnalyzing: boolean;
  sendMessage: (content: string) => void;
  analyzeReport: (reportText: string) => void;
  validateCode: (codeId: string, cie10Code: string) => void;
  rejectCode: (codeId: string, cie10Code: string, reason: string) => void;
}

const ConversationContext = createContext<ConversationContextType | undefined>(undefined);

export function ConversationProvider({ children, userId }: { children: ReactNode; userId: string }) {
  const [conversationId] = useState(() => `conv-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`);
  const [channel, setChannel] = useState<Channel | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [predictedCodes, setPredictedCodes] = useState<PredictedCode[]>([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  useEffect(() => {
    const socket = getSocket(userId);
    const ch = socket.channel(`conversation:${conversationId}`, {});

    ch.join()
      .receive('ok', (resp: any) => {
        console.log('Joined successfully', resp);
        if (resp.history) {
          setMessages(resp.history.messages || []);
          setPredictedCodes(resp.history.predicted_codes || []);
        }
      })
      .receive('error', (resp: any) => console.log('Unable to join', resp));

    // Eventos del canal
    ch.on('new_message', (payload: any) => {
      setMessages((prev) => [...prev, {
        message_id: payload.message_id,
        content: payload.content,
        user_id: payload.user_id,
        timestamp: payload.timestamp,
        type: 'user_message'
      }]);
    });

    ch.on('analysis_started', () => {
      setIsAnalyzing(true);
    });

    ch.on('ai_prediction_received', (payload: any) => {
      setIsAnalyzing(false);

      // Agregar respuesta de IA como mensaje
      setMessages((prev) => [...prev, {
        message_id: `${payload.message_id}_response`,
        content: `Códigos CIE-10 detectados: ${payload.codes.map((c: any) => c.code).join(', ')}`,
        user_id: 'system_ai',
        timestamp: new Date().toISOString(),
        type: 'ai_response'
      }]);

      // Agregar códigos predichos
      const newCodes = payload.codes.map((code: any) => ({
        code_id: code.code_id || `code-${Date.now()}-${Math.random()}`,
        cie10_code: code.code,
        reasoning: code.reasoning,
        confidence: code.confidence,
        status: 'pending' as const
      }));

      setPredictedCodes((prev) => [...prev, ...newCodes]);
    });

    ch.on('analysis_failed', (payload: any) => {
      setIsAnalyzing(false);
      alert(`Análisis fallido: ${payload.error}`);
    });

    ch.on('code_validated', (payload: any) => {
      setPredictedCodes((prev) =>
        prev.map((code) =>
          code.code_id === payload.code_id
            ? { ...code, status: 'validated' as const }
            : code
        )
      );
    });

    ch.on('code_rejected', (payload: any) => {
      setPredictedCodes((prev) =>
        prev.map((code) =>
          code.code_id === payload.code_id
            ? { ...code, status: 'rejected' as const }
            : code
        )
      );
    });

    setChannel(ch);

    return () => {
      ch.leave();
    };
  }, [conversationId, userId]);

  const sendMessage = useCallback((content: string) => {
    if (!channel) return;

    channel.push('send_message', { content })
      .receive('ok', (resp: any) => console.log('Message sent', resp))
      .receive('error', (resp: any) => console.error('Failed to send', resp));
  }, [channel]);

  const analyzeReport = useCallback((reportText: string) => {
    if (!channel) return;

    channel.push('analyze_report', { report_text: reportText })
      .receive('ok', (resp: any) => console.log('Analysis started', resp))
      .receive('error', (resp: any) => console.error('Failed to analyze', resp));
  }, [channel]);

  const validateCode = useCallback((codeId: string, cie10Code: string) => {
    if (!channel) return;

    channel.push('validate_code', { code_id: codeId, cie10_code: cie10Code })
      .receive('ok', (resp: any) => console.log('Code validated', resp))
      .receive('error', (resp: any) => console.error('Failed to validate', resp));
  }, [channel]);

  const rejectCode = useCallback((codeId: string, cie10Code: string, reason: string) => {
    if (!channel) return;

    channel.push('reject_code', { code_id: codeId, cie10_code: cie10Code, reason })
      .receive('ok', (resp: any) => console.log('Code rejected', resp))
      .receive('error', (resp: any) => console.error('Failed to reject', resp));
  }, [channel]);

  return (
    <ConversationContext.Provider
      value={{
        conversationId,
        messages,
        predictedCodes,
        isAnalyzing,
        sendMessage,
        analyzeReport,
        validateCode,
        rejectCode,
      }}
    >
      {children}
    </ConversationContext.Provider>
  );
}

export function useConversation() {
  const context = useContext(ConversationContext);
  if (!context) {
    throw new Error('useConversation must be used within ConversationProvider');
  }
  return context;
}
