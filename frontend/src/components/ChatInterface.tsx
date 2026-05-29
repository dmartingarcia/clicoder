'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { useConversation, ChatItem, AnalysisCard, AnalysisCode, PredictedCode } from '@/contexts/ConversationContext';
import { ConversationSidebar } from '@/components/ConversationSidebar';
import { useI18n } from '@/contexts/I18nContext';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { searchCie10, Cie10Result, getAncestors } from '@/lib/cie10';
import { config } from '@/lib/config';
import {
  Loader2, FileText, Stethoscope, CheckCircle2, XCircle,
  AlertCircle, ClipboardList, Lightbulb, Activity, Tag, ExternalLink,
} from 'lucide-react';

// ─── Card: Resumen clínico ────────────────────────────────────────────────────
function SummaryCard({ content }: { content: string }) {
  const { t } = useI18n();
  return (
    <Card className="p-4 border-l-4 border-l-blue-400 bg-blue-50">
      <div className="flex items-center gap-2 mb-2 text-blue-700">
        <ClipboardList className="h-4 w-4 shrink-0" />
        <span className="text-xs font-semibold uppercase tracking-wide">{t('cards.summary_title')}</span>
      </div>
      <p className="text-sm text-gray-700 leading-relaxed">{content}</p>
    </Card>
  );
}

// ─── Card: Códigos CIE-10 ─────────────────────────────────────────────────────
function CodesCard({
  codes,
  predictedCodes,
  validateCode,
  rejectCode,
}: {
  codes: AnalysisCode[];
  predictedCodes: PredictedCode[];
  validateCode: (id: string, code: string) => void;
  rejectCode: (id: string, code: string, reason: string) => void;
}) {
  const { t } = useI18n();
  const [rejectInputs, setRejectInputs] = useState<Record<string, string>>({});
  const [showReject, setShowReject] = useState<string | null>(null);

  // Match each code to its DB record for status + code_id
  const enriched = codes.map((c) => {
    const db = predictedCodes.find((p) => p.cie10_code === c.code);
    return { ...c, code_id: db?.code_id, status: db?.status ?? 'pending' };
  });

  return (
    <Card className="p-4 border-l-4 border-l-indigo-400 bg-indigo-50">
      <div className="flex items-center gap-2 mb-3 text-indigo-700">
        <Activity className="h-4 w-4 shrink-0" />
        <span className="text-xs font-semibold uppercase tracking-wide">
          {t('cards.codes_title', { count: codes.length })}
        </span>
      </div>

      <div className="space-y-3">
        {enriched.map((c, i) => (
          <div key={i} className="bg-white rounded-lg p-3 shadow-sm">
            <div className="flex items-start justify-between gap-2 mb-1">
              <div className="flex items-center gap-2 flex-wrap">
                <div className="flex flex-col gap-0.5">
                  <Link
                    href={`/codes/${c.code}`}
                    target="_blank"
                    className="font-bold text-indigo-700 hover:underline flex items-center gap-0.5"
                  >
                    {c.code} <ExternalLink className="h-3 w-3 opacity-60" />
                  </Link>
                  {getAncestors(c.code).length > 0 && (
                    <div className="flex items-center gap-0.5 flex-wrap text-[10px] text-gray-400">
                      {getAncestors(c.code).map((ancestor, idx) => (
                        <span key={ancestor} className="flex items-center gap-0.5">
                          {idx > 0 && <span className="opacity-50">›</span>}
                          <Link
                            href={`/codes/${ancestor}`}
                            target="_blank"
                            className="hover:text-indigo-500 hover:underline"
                          >
                            {ancestor}
                          </Link>
                        </span>
                      ))}
                      <span className="opacity-50">›</span>
                      <span className="font-medium text-gray-500">{c.code}</span>
                    </div>
                  )}
                </div>
                {c.description && <span className="text-xs text-gray-500">{c.description}</span>}
                <Badge
                  variant={c.status === 'rejected' ? 'destructive' : 'secondary'}
                  className={`text-xs ${c.status === 'validated' ? 'bg-green-100 text-green-700 border border-green-300' : ''}`}
                >
                  {c.status === 'validated' ? t('cards.status_validated') : c.status === 'rejected' ? t('cards.status_rejected') : t('cards.pending')}
                </Badge>
              </div>
              <span className="text-xs font-semibold text-green-600 shrink-0">
                {((c.confidence ?? 0) * 100).toFixed(0)}%
              </span>
            </div>

            <p className="text-xs text-gray-600 mb-2">{c.reason ?? c.reasoning}</p>

            {c.status === 'pending' && c.code_id && (
              <div className="space-y-2">
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    className="flex-1 bg-green-600 hover:bg-green-700 text-xs h-7"
                    onClick={() => validateCode(c.code_id!, c.code)}
                  >
                    <CheckCircle2 className="h-3 w-3 mr-1" /> {t('cards.validate')}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    className="flex-1 text-xs h-7 border-red-200 text-red-600 hover:bg-red-50"
                    onClick={() => setShowReject((prev) => (prev === c.code_id ? null : c.code_id!))}
                  >
                    <XCircle className="h-3 w-3 mr-1" /> {t('cards.reject')}
                  </Button>
                </div>

                {showReject === c.code_id && (
                  <div className="space-y-1">
                    <input
                      type="text"
                      autoFocus
                      placeholder={t('cards.reject_placeholder')}
                      value={rejectInputs[c.code_id!] ?? ''}
                      onChange={(e) => setRejectInputs((prev) => ({ ...prev, [c.code_id!]: e.target.value }))}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && rejectInputs[c.code_id!]?.trim()) {
                          rejectCode(c.code_id!, c.code, rejectInputs[c.code_id!]);
                          setShowReject(null);
                        }
                      }}
                      className="w-full text-xs border rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-red-400"
                    />
                    <Button
                      size="sm"
                      variant="destructive"
                      className="w-full text-xs h-7"
                      disabled={!rejectInputs[c.code_id!]?.trim()}
                      onClick={() => {
                        rejectCode(c.code_id!, c.code, rejectInputs[c.code_id!]);
                        setShowReject(null);
                      }}
                    >
                      {t('cards.confirm_reject')}
                    </Button>
                  </div>
                )}
              </div>
            )}

            {c.status === 'validated' && (
              <p className="text-xs text-green-600 flex items-center gap-1">
                <CheckCircle2 className="h-3 w-3" /> {t('cards.validated')}
              </p>
            )}
            {c.status === 'rejected' && (
              <p className="text-xs text-red-500 flex items-center gap-1">
                <XCircle className="h-3 w-3" /> {t('cards.rejected')}
              </p>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}

// ─── Card: Recomendaciones ────────────────────────────────────────────────────
function RecommendationsCard({ content }: { content: string }) {
  const { t } = useI18n();
  return (
    <Card className="p-4 border-l-4 border-l-amber-400 bg-amber-50">
      <div className="flex items-center gap-2 mb-2 text-amber-700">
        <Lightbulb className="h-4 w-4 shrink-0" />
        <span className="text-xs font-semibold uppercase tracking-wide">{t('cards.recommendations_title')}</span>
      </div>
      <p className="text-sm text-gray-700 leading-relaxed">{content}</p>
    </Card>
  );
}

// ─── Card: Sugerencia de código ───────────────────────────────────────────────
function SuggestionCard({ content }: { content: string }) {
  const { t } = useI18n();
  const { suggestCode } = useConversation();
  const [selectedText, setSelectedText] = useState('');
  const [codeInput, setCodeInput] = useState('');
  const [suggestions, setSuggestions] = useState<Cie10Result[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedSuggestion, setSelectedSuggestion] = useState<Cie10Result | null>(null);
  const [submitted, setSubmitted] = useState<{ text: string; code: string; description?: string }[]>([]);
  const textRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchSuggestions = useCallback(async (q: string) => {
    if (q.length < 2) { setSuggestions([]); setShowSuggestions(false); return; }
    const results = await searchCie10(q, 8);
    setSuggestions(results);
    setShowSuggestions(results.length > 0);
  }, []);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => fetchSuggestions(codeInput), 300);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [codeInput, fetchSuggestions]);

  const handleMouseUp = () => {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed) return;
    const text = sel.toString().trim();
    if (text.length < 2) return;
    if (textRef.current && !textRef.current.contains(sel.anchorNode)) return;
    setSelectedText(text);
    setCodeInput('');
    setSelectedSuggestion(null);
    setSuggestions([]);
    setShowSuggestions(false);
  };

  const pickSuggestion = (s: Cie10Result) => {
    setCodeInput(s.code);
    setSelectedSuggestion(s);
    setShowSuggestions(false);
  };

  const handleSubmit = () => {
    if (!selectedText || !codeInput.trim()) return;
    const code = codeInput.trim().toUpperCase();
    suggestCode(selectedText, code);
    setSubmitted((prev) => [...prev, { text: selectedText, code, description: selectedSuggestion?.description }]);
    setSelectedText('');
    setCodeInput('');
    setSelectedSuggestion(null);
    setSuggestions([]);
    window.getSelection()?.removeAllRanges();
  };

  const typeLabel = (type: string) =>
    type === 'diagnosis' ? t('cie10.type_diagnosis') : type === 'procedure' ? t('cie10.type_procedure') : t('cie10.type_chemical');

  return (
    <Card className="p-4 border-l-4 border-l-purple-400 bg-purple-50">
      <div className="flex items-center gap-2 mb-2 text-purple-700">
        <Tag className="h-4 w-4 shrink-0" />
        <span className="text-xs font-semibold uppercase tracking-wide">{t('cards.suggest_title')}</span>
      </div>
      <p className="text-xs text-purple-600 mb-3">{t('cards.suggest_hint')}</p>

      <div
        ref={textRef}
        onMouseUp={handleMouseUp}
        className="text-sm text-gray-700 bg-white rounded-lg p-3 leading-relaxed select-text cursor-text border border-purple-100"
      >
        {content}
      </div>

      {selectedText && (
        <div className="mt-3 bg-white border border-purple-200 rounded-lg p-3 space-y-2">
          <p className="text-xs text-gray-500">
            <span className="font-medium text-purple-700">{t('cards.suggest_selected')}:</span>{' '}
            &ldquo;{selectedText}&rdquo;
          </p>
          <div className="relative">
            <div className="flex gap-2">
              <input
                autoFocus
                type="text"
                placeholder={t('cards.suggest_code_placeholder')}
                value={codeInput}
                onChange={(e) => { setCodeInput(e.target.value.toUpperCase()); setSelectedSuggestion(null); }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') { setShowSuggestions(false); handleSubmit(); }
                  if (e.key === 'Escape') {
                    if (showSuggestions) { setShowSuggestions(false); }
                    else { setSelectedText(''); window.getSelection()?.removeAllRanges(); }
                  }
                }}
                onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
                className="flex-1 text-sm border rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-purple-400"
              />
              <Button
                size="sm"
                className="bg-purple-600 hover:bg-purple-700 text-xs h-8"
                disabled={!codeInput.trim()}
                onClick={handleSubmit}
              >
                {t('cards.suggest_submit')}
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="text-xs h-8"
                onClick={() => { setSelectedText(''); window.getSelection()?.removeAllRanges(); }}
              >
                <XCircle className="h-3 w-3" />
              </Button>
            </div>

            {showSuggestions && suggestions.length > 0 && (
              <div className="absolute top-full left-0 right-0 z-50 mt-1 bg-white border border-purple-200 rounded-lg shadow-lg overflow-hidden">
                {suggestions.map((s) => (
                  <button
                    key={s.code}
                    type="button"
                    onMouseDown={(e) => { e.preventDefault(); pickSuggestion(s); }}
                    className="w-full text-left px-3 py-2 hover:bg-purple-50 flex items-start gap-2 border-b border-gray-100 last:border-0"
                  >
                    <span className="font-bold text-purple-700 text-xs shrink-0 mt-0.5">{s.code}</span>
                    <span className="text-xs text-gray-600 line-clamp-1 flex-1">{s.description}</span>
                    <Badge variant="outline" className="text-[10px] shrink-0 px-1">{typeLabel(s.type)}</Badge>
                  </button>
                ))}
              </div>
            )}
          </div>

          {selectedSuggestion && (
            <p className="text-xs text-purple-700 bg-purple-50 rounded px-2 py-1">
              {selectedSuggestion.description}
            </p>
          )}
        </div>
      )}

      {submitted.length > 0 && (
        <div className="mt-3 space-y-1">
          {submitted.map((s, i) => (
            <div key={i} className="flex items-center gap-2 text-xs bg-purple-100 text-purple-800 rounded px-2 py-1">
              <CheckCircle2 className="h-3 w-3 shrink-0 text-purple-600" />
              <span className="truncate">&ldquo;{s.text}&rdquo;</span>
              <span className="font-bold shrink-0">→</span>
              <Link
                href={`/codes/${s.code}`}
                target="_blank"
                className="font-bold hover:underline flex items-center gap-0.5 shrink-0"
              >
                {s.code} <ExternalLink className="h-2.5 w-2.5" />
              </Link>
              {s.description && <span className="text-purple-600 truncate">{s.description}</span>}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

// ─── Card: texto genérico ─────────────────────────────────────────────────────
function TextCard({ content }: { content: string }) {
  return (
    <Card className="p-4 border-l-4 border-l-gray-300 bg-gray-50">
      <p className="text-sm text-gray-700 leading-relaxed">{content}</p>
    </Card>
  );
}

// ─── Chat item renderer ───────────────────────────────────────────────────────
function ChatItemView({
  item,
  predictedCodes,
  validateCode,
  rejectCode,
}: {
  item: ChatItem;
  predictedCodes: PredictedCode[];
  validateCode: (id: string, code: string) => void;
  rejectCode: (id: string, code: string, reason: string) => void;
}) {
  if (item.kind === 'user') {
    return (
      <div className="flex justify-end gap-3">
        <div className="bg-white border rounded-xl px-4 py-3 text-sm text-gray-800 max-w-2xl shadow-sm">
          <p className="whitespace-pre-wrap">{item.content}</p>
          <span className="block text-xs text-gray-400 mt-1 text-right">
            {new Date(item.timestamp).toLocaleTimeString()}
          </span>
        </div>
        <div className="h-8 w-8 rounded-full bg-green-100 flex items-center justify-center shrink-0 mt-1">
          <span className="text-xs font-bold text-green-700">MD</span>
        </div>
      </div>
    );
  }

  // Card item
  const card = item as AnalysisCard;

  const wrapper = (children: React.ReactNode) => (
    <div className="flex gap-3">
      <div className="h-8 w-8 rounded-full bg-blue-100 flex items-center justify-center shrink-0 mt-1">
        <Stethoscope className="h-4 w-4 text-blue-600" />
      </div>
      <div className="flex-1 max-w-2xl">{children}</div>
    </div>
  );

  switch (card.card_type) {
    case 'summary':
      return wrapper(<SummaryCard content={card.content as string} />);
    case 'codes':
      return wrapper(
        <CodesCard
          codes={card.content as AnalysisCode[]}
          predictedCodes={predictedCodes}
          validateCode={validateCode}
          rejectCode={rejectCode}
        />
      );
    case 'recommendations':
      return wrapper(<RecommendationsCard content={card.content as string} />);
    case 'suggest':
      return wrapper(<SuggestionCard content={card.content as string} />);
    default:
      return wrapper(<TextCard content={card.content as string} />);
  }
}

// ─── Main interface ───────────────────────────────────────────────────────────
export function ChatInterface() {
  const { activeConversationId, pendingConversation, chatItems, predictedCodes, isAnalyzing, engine, analyzeReport, validateCode, rejectCode, createConversation } = useConversation();
  const { t } = useI18n();
  const MAX_TOKENS = 1024;
  const [reportText, setReportText] = useState('');
  const [serverTokenEntry, setServerTokenEntry] = useState<{ text: string; count: number } | null>(null);
  // approxTokenCount is computed synchronously; serverTokenEntry refines it after 300ms debounce.
  // Deriving null from text mismatch avoids a synchronous setState inside the effect.
  const serverTokenCount = serverTokenEntry?.text === reportText ? serverTokenEntry.count : null;
  const approxTokenCount = Math.ceil(reportText.length / 4);
  const tokenCount = serverTokenCount ?? approxTokenCount;

  useEffect(() => {
    if (!reportText) return;
    const timer = setTimeout(async () => {
      try {
        const res = await fetch(`${config.apiUrl}/ai/count-tokens`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: reportText }),
        });
        if (res.ok) {
          const data = await res.json();
          setServerTokenEntry({ text: reportText, count: data.token_count });
        }
      } catch {
        // keep approxTokenCount
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [reportText]);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [chatItems, isAnalyzing]);

  const handleAnalyze = () => {
    const text = reportText.trim();
    if (!text || text.length < 20 || tokenCount > MAX_TOKENS) return;
    analyzeReport(text);
    setReportText('');
  };

  return (
    <div className="flex h-screen bg-gray-100">
      <ConversationSidebar />

      {!activeConversationId && !pendingConversation ? (
        <div className="flex-1 flex flex-col items-center justify-center gap-6 text-center p-8">
          <Stethoscope className="h-16 w-16 text-blue-400" />
          <div>
            <h1 className="text-2xl font-bold text-gray-800">{t('chat.welcome_title')}</h1>
            <p className="text-gray-500 mt-2 max-w-sm">{t('chat.welcome_body')}</p>
          </div>
          <Button onClick={createConversation} className="bg-blue-600 hover:bg-blue-700 gap-2">
            <FileText className="h-4 w-4" />
            {t('chat.new_analysis')}
          </Button>
        </div>
      ) : (
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Header */}
          <div className="bg-white border-b px-6 py-4 flex items-center gap-3">
            <Stethoscope className="h-5 w-5 text-blue-600" />
            <div>
              <h2 className="font-semibold text-gray-800">{t('chat.analysis_header')}</h2>
              <p className="text-xs text-gray-400">
                ID: {activeConversationId}
                {engine && <span className="ml-3 text-blue-500 font-medium">{t('chat.engine_label')}: {engine}</span>}
              </p>
            </div>
          </div>

          {/* Chat stream */}
          <div className="flex-1 overflow-y-auto px-6 py-4" ref={scrollRef}>
            <div className="space-y-4 max-w-3xl mx-auto">
              {chatItems.length === 0 && !isAnalyzing && (
                <div className="flex flex-col items-center gap-3 py-16 text-gray-400">
                  <AlertCircle className="h-10 w-10 opacity-40" />
                  <p className="text-sm">{t('chat.empty_state')}</p>
                </div>
              )}

              {(() => {
                const firstUser = chatItems.find((item) => item.kind === 'user');
                const rest = firstUser ? chatItems.filter((item) => item !== firstUser) : chatItems;
                return (
                  <>
                    {firstUser && firstUser.kind === 'user' && (
                      <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
                        <div className="flex items-center gap-2 mb-2 text-gray-500">
                          <FileText className="h-4 w-4 shrink-0" />
                          <span className="text-xs font-semibold uppercase tracking-wide">{t('chat.report_label')}</span>
                          <span className="ml-auto text-xs text-gray-400">
                            {new Date(firstUser.timestamp).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' })}
                          </span>
                        </div>
                        <p className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">{firstUser.content}</p>
                      </div>
                    )}
                    {rest.map((item, i) => (
                      <ChatItemView
                        key={item.kind === 'user' ? item.message_id : item.card_id + i}
                        item={item}
                        predictedCodes={predictedCodes}
                        validateCode={validateCode}
                        rejectCode={rejectCode}
                      />
                    ))}
                  </>
                );
              })()}

              {isAnalyzing && (
                <div className="flex gap-3">
                  <div className="h-8 w-8 rounded-full bg-blue-100 flex items-center justify-center shrink-0">
                    <Stethoscope className="h-4 w-4 text-blue-600" />
                  </div>
                  <div className="bg-blue-50 border border-blue-100 rounded-xl px-4 py-3 flex items-center gap-2 text-sm text-gray-600">
                    <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
                    {t('chat.analyzing')}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Report input */}
          <div className="bg-white border-t px-6 py-4">
            <div className="max-w-3xl mx-auto">
              <label className="text-xs font-medium text-gray-500 uppercase tracking-wider block mb-2">
                {t('chat.report_label')}
              </label>
              <Textarea
                value={reportText}
                onChange={(e) => setReportText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && e.ctrlKey) {
                    e.preventDefault();
                    handleAnalyze();
                  }
                }}
                placeholder={t('chat.report_placeholder')}
                className="resize-none text-sm"
                rows={4}
                disabled={isAnalyzing}
              />
              {reportText.length > 0 && reportText.trim().length < 20 && (
                <p className="text-xs text-amber-600 mt-1">
                  {t('chat.min_chars', { min: 20, remaining: 20 - reportText.trim().length })}
                </p>
              )}
              {tokenCount > MAX_TOKENS && (
                <p className="text-xs text-red-600 mt-1">
                  {t('chat.max_words_error', { max: MAX_TOKENS })}
                </p>
              )}
              <div className="flex items-center justify-between mt-2">
                <span className={`text-xs ${tokenCount > MAX_TOKENS ? 'text-red-600 font-medium' : 'text-gray-400'}`}>
                  {t('chat.word_count', { count: tokenCount, max: MAX_TOKENS })}
                </span>
                <Button
                  onClick={handleAnalyze}
                  disabled={isAnalyzing || reportText.trim().length < 20 || tokenCount > MAX_TOKENS}
                  className="bg-blue-600 hover:bg-blue-700 gap-2"
                  size="sm"
                >
                  {isAnalyzing
                    ? <Loader2 className="h-4 w-4 animate-spin" />
                    : <FileText className="h-4 w-4" />}
                  {t('chat.analyze_button')}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
