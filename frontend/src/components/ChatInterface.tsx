'use client';

import { useState, useEffect, useRef } from 'react';
import { useConversation } from '@/contexts/ConversationContext';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Send, Loader2, CheckCircle2, XCircle } from 'lucide-react';

export function ChatInterface() {
  const { messages, predictedCodes, isAnalyzing, sendMessage, analyzeReport, validateCode, rejectCode } = useConversation();
  const [input, setInput] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = () => {
    if (!input.trim()) return;

    // Detectar si es un informe clínico (más de 50 caracteres) para analizarlo
    if (input.length > 50) {
      analyzeReport(input);
    } else {
      sendMessage(input);
    }

    setInput('');
  };

  return (
    <div className="flex h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      {/* Panel principal del chat */}
      <div className="flex-1 flex flex-col max-w-4xl mx-auto w-full p-4">
        <Card className="flex-1 flex flex-col shadow-2xl">
          {/* Header */}
          <div className="p-4 border-b bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-t-lg">
            <h2 className="text-2xl font-bold">Clasificador CIE-10</h2>
            <p className="text-sm opacity-90">Asistente médico inteligente</p>
          </div>

          {/* Mensajes */}
          <ScrollArea className="flex-1 p-4" ref={scrollRef}>
            <div className="space-y-4">
              {messages.map((msg) => (
                <div
                  key={msg.message_id}
                  className={`flex ${msg.user_id === 'system_ai' ? 'justify-start' : 'justify-end'}`}
                >
                  <div className={`flex gap-3 max-w-[80%] ${msg.user_id === 'system_ai' ? 'flex-row' : 'flex-row-reverse'}`}>
                    <Avatar className={msg.user_id === 'system_ai' ? 'bg-blue-500' : 'bg-green-500'}>
                      <AvatarFallback className="text-white">
                        {msg.user_id === 'system_ai' ? 'AI' : 'MD'}
                      </AvatarFallback>
                    </Avatar>
                    <div
                      className={`rounded-2xl px-4 py-3 ${
                        msg.user_id === 'system_ai'
                          ? 'bg-gray-100 text-gray-900'
                          : 'bg-blue-600 text-white'
                      }`}
                    >
                      <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                      <span className="text-xs opacity-70 mt-1 block">
                        {new Date(msg.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                  </div>
                </div>
              ))}

              {isAnalyzing && (
                <div className="flex justify-start">
                  <div className="flex gap-3 items-center bg-gray-100 rounded-2xl px-4 py-3">
                    <Loader2 className="h-5 w-5 animate-spin text-blue-600" />
                    <span className="text-sm text-gray-700">Analizando informe clínico...</span>
                  </div>
                </div>
              )}
            </div>
          </ScrollArea>

          {/* Input */}
          <div className="p-4 border-t bg-gray-50">
            <div className="flex gap-2">
              <Textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                placeholder="Escribe un informe clínico o mensaje..."
                className="resize-none"
                rows={3}
              />
              <Button onClick={handleSend} size="icon" className="h-full px-4 bg-blue-600 hover:bg-blue-700">
                <Send className="h-5 w-5" />
              </Button>
            </div>
            <p className="text-xs text-gray-500 mt-2">
              💡 Pega un informe clínico (&gt;50 caracteres) para análisis automático
            </p>
          </div>
        </Card>
      </div>

      {/* Panel lateral de códigos CIE-10 */}
      <div className="w-96 p-4 bg-white border-l overflow-y-auto">
        <h3 className="text-xl font-bold mb-4 text-gray-800">Códigos CIE-10</h3>

        {predictedCodes.length === 0 ? (
          <div className="text-center text-gray-500 mt-8">
            <p>No hay códigos detectados aún</p>
            <p className="text-sm mt-2">Los códigos aparecerán aquí tras el análisis</p>
          </div>
        ) : (
          <div className="space-y-3">
            {predictedCodes.map((code) => (
              <Card key={code.code_id} className="p-4 hover:shadow-md transition-shadow">
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <h4 className="font-bold text-lg text-blue-700">{code.cie10_code}</h4>
                    <Badge variant={code.status === 'validated' ? 'default' : code.status === 'rejected' ? 'destructive' : 'secondary'}>
                      {code.status}
                    </Badge>
                  </div>
                  <div className="text-right">
                    <span className="text-sm text-gray-600">Confianza:</span>
                    <p className="font-bold text-green-600">{(code.confidence * 100).toFixed(1)}%</p>
                  </div>
                </div>

                <p className="text-sm text-gray-700 mb-3">{code.reasoning}</p>

                {code.status === 'pending' && (
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="default"
                      className="flex-1 bg-green-600 hover:bg-green-700"
                      onClick={() => validateCode(code.code_id, code.cie10_code)}
                    >
                      <CheckCircle2 className="h-4 w-4 mr-1" />
                      Validar
                    </Button>
                    <Button
                      size="sm"
                      variant="destructive"
                      className="flex-1"
                      onClick={() => {
                        const reason = prompt('Motivo del rechazo:');
                        if (reason) rejectCode(code.code_id, code.cie10_code, reason);
                      }}
                    >
                      <XCircle className="h-4 w-4 mr-1" />
                      Rechazar
                    </Button>
                  </div>
                )}
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
