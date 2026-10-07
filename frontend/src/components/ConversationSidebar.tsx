'use client';

import { useState } from 'react';
import { useConversation } from '@/contexts/ConversationContext';
import { useAuth } from '@/contexts/AuthContext';
import { useI18n } from '@/contexts/I18nContext';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { config } from '@/lib/config';
import { PrivacyModal } from '@/components/PrivacyModal';
import { toast } from 'sonner';
import {
  PlusCircle,
  MessageSquare,
  LogOut,
  Trash2,
  RotateCcw,
  ChevronDown,
  ChevronRight,
  Download,
  UserX,
  ShieldCheck,
} from 'lucide-react';

export function ConversationSidebar() {
  const {
    conversations,
    trashedConversations,
    activeConversationId,
    createConversation,
    switchConversation,
    deleteConversation,
    restoreConversation,
  } = useConversation();
  const { user, token, logout } = useAuth();
  const { locale, setLocale, t } = useI18n();
  const [trashOpen, setTrashOpen] = useState(false);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [localeOpen, setLocaleOpen] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deletingAccount, setDeletingAccount] = useState(false);
  const [showPrivacyModal, setShowPrivacyModal] = useState(false);

  const handleExportData = async () => {
    const res = await fetch(`${config.apiUrl}/users/export`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.status === 401) {
      toast.error(t('errors.session_expired'));
      logout();
      return;
    }
    if (!res.ok) return;
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'datos_usuario.json';
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleDeleteAccount = async () => {
    setDeletingAccount(true);
    try {
      const res = await fetch(`${config.apiUrl}/users/account`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.status === 401) {
        toast.error(t('errors.session_expired'));
        logout();
        return;
      }
      if (res.ok) {
        logout();
      }
    } finally {
      setDeletingAccount(false);
      setShowDeleteModal(false);
    }
  };

  const LOCALES: { code: string; flag: string }[] = [
    { code: 'es', flag: '🇪🇸' },
    { code: 'en', flag: '🇬🇧' },
    { code: 'fr', flag: '🇫🇷' },
    { code: 'it', flag: '🇮🇹' },
    { code: 'de', flag: '🇩🇪' },
  ];

  const formatDate = (dateStr: string) =>
    new Date(dateStr).toLocaleDateString(locale, { day: '2-digit', month: 'short' });

  return (
    <div className="w-64 flex flex-col bg-gray-900 text-white h-screen">
      <div className="p-4 border-b border-gray-700">
        <p className="text-xs text-gray-400 uppercase tracking-wider mb-1">{t('app.doctor')}</p>
        <p className="text-sm font-semibold truncate">
          {user?.first_name} {user?.last_name}
        </p>
        <p className="text-xs text-gray-400 truncate">@{user?.username}</p>
        <div className="mt-2">
          <div className="relative">
            <button
              onClick={() => setLocaleOpen((o) => !o)}
              className="p-1 rounded text-gray-400 hover:text-white hover:bg-gray-700 transition-colors flex items-center gap-1"
            >
              <span>{LOCALES.find((l) => l.code === locale)?.flag}</span>
              <span className="text-xs font-medium uppercase">{locale}</span>
            </button>
            {localeOpen && (
              <div className="absolute right-0 top-full mt-1 bg-gray-800 border border-gray-600 rounded shadow-lg z-50 min-w-15">
                {LOCALES.map(({ code, flag }) => (
                  <button
                    key={code}
                    onClick={() => {
                      setLocale(code, token ?? undefined);
                      setLocaleOpen(false);
                    }}
                    className={`w-full text-left px-3 py-1.5 text-xs font-medium uppercase transition-colors flex items-center gap-2 ${
                      code === locale
                        ? 'text-white bg-gray-700'
                        : 'text-gray-400 hover:text-white hover:bg-gray-700'
                    }`}
                  >
                    <span>{flag}</span>
                    {code}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="p-3">
        <Button
          onClick={createConversation}
          className="w-full bg-blue-600 hover:bg-blue-700 text-white gap-2"
          size="sm"
        >
          <PlusCircle className="h-4 w-4" />
          {t('sidebar.new_analysis')}
        </Button>
      </div>

      <ScrollArea className="flex-1 px-2">
        {conversations.length === 0 ? (
          <p className="text-xs text-gray-500 text-center mt-6 px-2">{t('sidebar.no_previous')}</p>
        ) : (
          <div className="space-y-1 pb-2">
            {conversations.map((conv) => {
              const isActive = conv.conversation_id === activeConversationId;
              const preview = conv.last_message?.content?.slice(0, 60) ?? '…';
              const msgLabel =
                conv.message_count === 1 ? t('sidebar.messages_one') : t('sidebar.messages_other');

              return (
                <div
                  key={conv.conversation_id}
                  className="relative group"
                  onMouseEnter={() => setHoveredId(conv.conversation_id)}
                  onMouseLeave={() => setHoveredId(null)}
                >
                  <button
                    onClick={() => switchConversation(conv.conversation_id)}
                    className={`w-full text-left rounded-lg px-3 py-2 pr-8 transition-colors ${
                      isActive ? 'bg-blue-700 text-white' : 'text-gray-300 hover:bg-gray-700'
                    }`}
                  >
                    <div className="flex items-start gap-2">
                      <MessageSquare className="h-4 w-4 mt-0.5 shrink-0 opacity-70" />
                      <div className="min-w-0">
                        <p className="text-xs font-medium truncate">
                          {formatDate(conv.started_at)}
                        </p>
                        <p className="text-xs opacity-70 truncate">{preview}</p>
                        <p className="text-xs opacity-50 mt-0.5">
                          {conv.message_count} {msgLabel}
                        </p>
                      </div>
                    </div>
                  </button>

                  {hoveredId === conv.conversation_id && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteConversation(conv.conversation_id);
                      }}
                      title={t('sidebar.delete')}
                      className="absolute right-1 top-1/2 -translate-y-1/2 p-1 rounded text-gray-400 hover:text-red-400 hover:bg-gray-600 transition-colors"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {trashedConversations.length > 0 && (
          <div className="border-t border-gray-700 pt-2 pb-4">
            <button
              onClick={() => setTrashOpen((o) => !o)}
              className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-gray-400 hover:text-gray-200 transition-colors"
            >
              {trashOpen ? (
                <ChevronDown className="h-3 w-3" />
              ) : (
                <ChevronRight className="h-3 w-3" />
              )}
              <Trash2 className="h-3 w-3" />
              {t('sidebar.trash')} ({trashedConversations.length})
            </button>

            {trashOpen && (
              <div className="space-y-1 mt-1">
                {trashedConversations.map((conv) => (
                  <div key={conv.conversation_id} className="flex items-center gap-1 px-2">
                    <div className="flex-1 min-w-0 px-2 py-1 rounded text-gray-500">
                      <p className="text-xs truncate opacity-60">
                        {formatDate(conv.started_at)} ·{' '}
                        {conv.last_message?.content?.slice(0, 40) ?? '…'}
                      </p>
                    </div>
                    <button
                      onClick={() => restoreConversation(conv.conversation_id)}
                      title={t('sidebar.restore')}
                      className="shrink-0 p-1 rounded text-gray-500 hover:text-green-400 hover:bg-gray-700 transition-colors"
                    >
                      <RotateCcw className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </ScrollArea>

      <div className="border-t border-gray-700 p-2 flex flex-col gap-0.5">
        <button
          onClick={() => setShowPrivacyModal(true)}
          className="w-full flex items-center gap-2 px-3 py-1.5 rounded text-xs text-gray-400 hover:text-white hover:bg-gray-700 transition-colors"
        >
          <ShieldCheck className="h-3.5 w-3.5 shrink-0" />
          {t('privacy.title')}
        </button>
        <button
          onClick={handleExportData}
          className="w-full flex items-center gap-2 px-3 py-1.5 rounded text-xs text-gray-400 hover:text-white hover:bg-gray-700 transition-colors"
        >
          <Download className="h-3.5 w-3.5 shrink-0" />
          {t('sidebar.export_data')}
        </button>
        <button
          onClick={() => setShowDeleteModal(true)}
          className="w-full flex items-center gap-2 px-3 py-1.5 rounded text-xs text-gray-400 hover:text-red-400 hover:bg-gray-700 transition-colors"
        >
          <UserX className="h-3.5 w-3.5 shrink-0" />
          {t('sidebar.delete_account')}
        </button>
        <button
          onClick={logout}
          className="w-full flex items-center gap-2 px-3 py-1.5 rounded text-xs text-gray-400 hover:text-white hover:bg-gray-700 transition-colors"
        >
          <LogOut className="h-3.5 w-3.5 shrink-0" />
          {t('auth.logout')}
        </button>
      </div>

      {showPrivacyModal && (
        <PrivacyModal
          onClose={() => setShowPrivacyModal(false)}
          onExport={() => {
            handleExportData();
            setShowPrivacyModal(false);
          }}
          onDeleteAccount={() => {
            setShowPrivacyModal(false);
            setShowDeleteModal(true);
          }}
        />
      )}

      {showDeleteModal && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <div className="bg-gray-800 border border-gray-600 rounded-lg shadow-xl max-w-sm w-full p-6 space-y-4">
            <h3 className="text-white font-semibold text-base">
              {t('sidebar.delete_account_title')}
            </h3>
            <p className="text-gray-300 text-sm leading-relaxed">
              {t('sidebar.delete_account_body')}
            </p>
            <div className="flex gap-3 pt-1">
              <button
                onClick={() => setShowDeleteModal(false)}
                disabled={deletingAccount}
                className="flex-1 px-4 py-2 text-sm rounded-md border border-gray-500 text-gray-300 hover:bg-gray-700 transition-colors disabled:opacity-50"
              >
                {t('sidebar.cancel')}
              </button>
              <button
                onClick={handleDeleteAccount}
                disabled={deletingAccount}
                className="flex-1 px-4 py-2 text-sm rounded-md bg-red-600 hover:bg-red-700 text-white font-medium transition-colors disabled:opacity-50"
              >
                {deletingAccount ? '…' : t('sidebar.delete_account_confirm')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
