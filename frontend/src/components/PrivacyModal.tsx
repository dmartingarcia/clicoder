'use client';

import { useI18n } from '@/contexts/I18nContext';
import { Download, Trash2, UserX, Mail } from 'lucide-react';

interface Props {
  onClose: () => void;
  onExport?: () => void;
  onDeleteAccount?: () => void;
}

const RIGHTS = [
  { key: 'art15', inApp: true, icon: <Download className="h-3.5 w-3.5 shrink-0 text-blue-400" /> },
  { key: 'art16', inApp: false, icon: <Mail className="h-3.5 w-3.5 shrink-0 text-gray-400" /> },
  { key: 'art17', inApp: true, icon: <UserX className="h-3.5 w-3.5 shrink-0 text-red-400" /> },
  { key: 'art18', inApp: false, icon: <Mail className="h-3.5 w-3.5 shrink-0 text-gray-400" /> },
  { key: 'art20', inApp: true, icon: <Download className="h-3.5 w-3.5 shrink-0 text-blue-400" /> },
  { key: 'art21', inApp: false, icon: <Mail className="h-3.5 w-3.5 shrink-0 text-gray-400" /> },
] as const;

export function PrivacyModal({ onClose, onExport, onDeleteAccount }: Props) {
  const { t } = useI18n();

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 border border-gray-600 rounded-lg shadow-xl w-full max-w-md max-h-[90vh] flex flex-col">
        <div className="px-5 pt-5 pb-3 border-b border-gray-700">
          <h2 className="text-white font-semibold text-base">{t('privacy.title')}</h2>
          <p className="text-gray-400 text-xs mt-1 leading-relaxed">{t('privacy.intro')}</p>
        </div>

        <div className="overflow-y-auto flex-1 px-5 py-3 space-y-2">
          {RIGHTS.map(({ key, inApp, icon }) => (
            <div
              key={key}
              className="flex items-start gap-2.5 py-2 border-b border-gray-700/50 last:border-0"
            >
              <div className="mt-0.5">{icon}</div>
              <div className="flex-1 min-w-0">
                <p className="text-white text-xs font-medium">
                  {t(`privacy.${key}_title` as never)}
                </p>
                <p className="text-gray-400 text-xs mt-0.5 leading-relaxed">
                  {t(`privacy.${key}_desc` as never)}
                </p>
              </div>
              {inApp && key === 'art15' && onExport && (
                <button
                  onClick={onExport}
                  className="shrink-0 text-xs text-blue-400 hover:text-blue-300 underline"
                >
                  <Download className="h-3.5 w-3.5" />
                </button>
              )}
              {inApp && key === 'art17' && onDeleteAccount && (
                <button
                  onClick={onDeleteAccount}
                  className="shrink-0 text-xs text-red-400 hover:text-red-300 underline"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
          ))}
        </div>

        <div className="px-5 py-3 border-t border-gray-700 bg-gray-900/50 rounded-b-lg space-y-1">
          <p className="text-gray-300 text-xs font-medium">{t('privacy.contact_title')}</p>
          <p className="text-gray-400 text-xs">{t('privacy.contact_name')}</p>
          <a
            href={`mailto:${t('privacy.contact_email')}`}
            className="text-blue-400 hover:text-blue-300 text-xs underline block"
          >
            {t('privacy.contact_email')}
          </a>
          <p className="text-gray-500 text-xs pt-1">{t('privacy.contact_basis')}</p>
        </div>

        <div className="px-5 pb-4 pt-3">
          <button
            onClick={onClose}
            className="w-full px-4 py-2 text-sm rounded-md border border-gray-500 text-gray-300 hover:bg-gray-700 transition-colors"
          >
            {t('privacy.close')}
          </button>
        </div>
      </div>
    </div>
  );
}
