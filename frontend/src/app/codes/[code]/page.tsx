'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { fetchCie10Code, fetchCie10Children, getAncestors, Cie10Result, Cie10Child } from '@/lib/cie10';
import { useI18n } from '@/contexts/I18nContext';
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import { Loader2, ArrowLeft, Stethoscope, Activity, FlaskConical, AlertCircle, ChevronRight, FolderOpen } from 'lucide-react';

const TYPE_COLORS = {
  diagnosis: 'border-l-blue-400 bg-blue-50',
  procedure: 'border-l-indigo-400 bg-indigo-50',
  chemical: 'border-l-amber-400 bg-amber-50',
} as const;

const TYPE_ICONS = {
  diagnosis: Stethoscope,
  procedure: Activity,
  chemical: FlaskConical,
} as const;

const CHILD_ACCENT = {
  diagnosis: 'text-blue-700 hover:bg-blue-50 border-blue-100',
  procedure: 'text-indigo-700 hover:bg-indigo-50 border-indigo-100',
  chemical: 'text-amber-700 hover:bg-amber-50 border-amber-100',
} as const;

function MetaRow({ label, value }: { label: string; value: string | number | boolean | null | undefined }) {
  if (value === null || value === undefined || value === '' || value === false) return null;
  return (
    <div className="flex gap-2 py-1 border-b border-gray-100 last:border-0 text-sm">
      <span className="text-gray-500 w-40 shrink-0">{label}</span>
      <span className="text-gray-800 font-medium">{String(value)}</span>
    </div>
  );
}

function DiagnosisDetail({ meta }: { meta: Record<string, unknown> }) {
  const { t } = useI18n();
  const flag = (v: unknown) => v === true ? '✓' : null;
  return (
    <div>
      <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">{t('cie10.age_groups')}</h3>
      <div className="bg-white rounded-lg p-3 space-y-0">
        <MetaRow label={t('cie10.perinatal')} value={flag(meta.perinatal)} />
        <MetaRow label={t('cie10.pediatric')} value={flag(meta.pediatric)} />
        <MetaRow label={t('cie10.maternity')} value={flag(meta.maternity)} />
        <MetaRow label={t('cie10.adult')} value={flag(meta.adult)} />
        <MetaRow label={t('cie10.exclusive_gender')} value={meta.exclusive_gender as string} />
        <MetaRow label={t('cie10.poa_exempt')} value={flag(meta.poa_exempt)} />
        <MetaRow label={t('cie10.no_principal')} value={flag(meta.no_principal)} />
      </div>
    </div>
  );
}

function ProcedureDetail({ meta }: { meta: Record<string, unknown> }) {
  const { t } = useI18n();
  return (
    <div>
      <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">{t('cie10.procedure_details')}</h3>
      <div className="bg-white rounded-lg p-3 space-y-0">
        <MetaRow label={t('cie10.class')} value={meta.class_name as string} />
        <MetaRow label={t('cie10.subclass')} value={meta.subclass_name as string} />
        <MetaRow label={t('cie10.procedure')} value={meta.procedure as string} />
        <MetaRow label={t('cie10.localization')} value={meta.localization as string} />
        <MetaRow label={t('cie10.approach')} value={meta.approach as string} />
        <MetaRow label={t('cie10.device')} value={meta.device as string} />
        <MetaRow label={t('cie10.calification')} value={meta.calification as string} />
        <MetaRow label={t('cie10.gender')} value={meta.gender as string} />
        <MetaRow label={t('cie10.times_selected')} value={meta.times_selected as number} />
      </div>
      {meta.definition && (
        <div className="mt-3 bg-white rounded-lg p-3">
          <p className="text-xs text-gray-500 mb-1">{t('cie10.definition')}</p>
          <p className="text-sm text-gray-700">{meta.definition as string}</p>
        </div>
      )}
    </div>
  );
}

function ChemicalDetail({ meta }: { meta: Record<string, unknown> }) {
  const { t } = useI18n();
  const allCodes = Array.isArray(meta.all_codes) ? meta.all_codes as string[] : [];
  const intents = [
    t('cie10.chem_accidental'),
    t('cie10.chem_self_harm'),
    t('cie10.chem_assault'),
    t('cie10.chem_undetermined'),
    t('cie10.chem_adverse'),
    t('cie10.chem_underdosing'),
  ];
  return (
    <div>
      <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">{t('cie10.variant_codes')}</h3>
      <div className="bg-white rounded-lg p-3 space-y-2">
        {allCodes.map((code, i) => (
          <div key={code} className="flex items-center gap-3">
            <Link href={`/codes/${code}`} className="font-mono font-bold text-amber-700 hover:underline text-sm">
              {code}
            </Link>
            <span className="text-xs text-gray-500">{intents[i] ?? ''}</span>
          </div>
        ))}
      </div>
      {meta.notes && (
        <div className="mt-3 bg-white rounded-lg p-3">
          <p className="text-xs text-gray-500 mb-1">{t('cie10.notes')}</p>
          <p className="text-sm text-gray-700">{meta.notes as string}</p>
        </div>
      )}
    </div>
  );
}

function ChildrenGrid({ items }: { items: Cie10Child[] }) {
  const { t } = useI18n();
  const inferredType = items.find(c => c.type)?.type ?? 'diagnosis';
  const accent = CHILD_ACCENT[inferredType] ?? CHILD_ACCENT.diagnosis;

  return (
    <Card className="p-4">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-3 flex items-center gap-1">
        <FolderOpen className="h-3.5 w-3.5" />
        {t('cie10.subcategories')} ({items.length})
      </h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
        {items.map((child) => (
          <Link
            key={child.code}
            href={`/codes/${child.code}`}
            className={`flex items-start gap-2 p-2.5 rounded-lg border transition-colors ${accent}`}
          >
            <span className="font-mono font-bold text-sm shrink-0 w-20">{child.code}</span>
            <span className="text-xs text-gray-600 leading-snug line-clamp-2">
              {child.description ?? <span className="italic text-gray-400">{t('cie10.category')}</span>}
            </span>
            <ChevronRight className="h-3.5 w-3.5 shrink-0 ml-auto mt-0.5 text-gray-400" />
          </Link>
        ))}
      </div>
    </Card>
  );
}

export default function CodeDetailPage() {
  const params = useParams();
  const code = (Array.isArray(params.code) ? params.code[0] : (params.code ?? '')).toUpperCase();
  const { t } = useI18n();
  const [entry, setEntry] = useState<Cie10Result | null>(null);
  const [children, setChildren] = useState<Cie10Child[]>([]);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  const ancestors = getAncestors(code);

  useEffect(() => {
    if (!code) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setEntry(null);
    setChildren([]);
    setNotFound(false);

    Promise.all([
      fetchCie10Code(code),
      fetchCie10Children(code),
    ]).then(([result, childrenResult]) => {
      if (result) {
        setEntry(result);
      } else if (childrenResult.children.length === 0) {
        setNotFound(true);
      }
      setChildren(childrenResult.children);
      setLoading(false);
    });
  }, [code]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
      </div>
    );
  }

  if (notFound) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4 bg-gray-50">
        <AlertCircle className="h-12 w-12 text-gray-300" />
        <p className="text-gray-500">{t('cie10.not_found', { code })}</p>
        <Link href="/" className="text-sm text-blue-600 hover:underline flex items-center gap-1">
          <ArrowLeft className="h-3 w-3" /> {t('cie10.back')}
        </Link>
      </div>
    );
  }

  const colorClass = entry ? (TYPE_COLORS[entry.type] ?? 'border-l-gray-300 bg-gray-50') : 'border-l-gray-300 bg-gray-50';
  const Icon = entry ? (TYPE_ICONS[entry.type] ?? Stethoscope) : FolderOpen;

  const typeLabel = entry
    ? (entry.type === 'diagnosis'
        ? t('cie10.type_diagnosis')
        : entry.type === 'procedure'
          ? t('cie10.type_procedure')
          : t('cie10.type_chemical'))
    : null;

  return (
    <div className="min-h-screen bg-gray-100 py-10 px-4">
      <div className="max-w-2xl mx-auto space-y-4">

        {/* Back + breadcrumb */}
        <nav className="flex items-center gap-1 text-sm text-gray-500 flex-wrap">
          <Link href="/" className="hover:text-gray-700 flex items-center gap-1">
            <ArrowLeft className="h-3 w-3" /> {t('cie10.back')}
          </Link>
          {ancestors.map((ancestor) => (
            <span key={ancestor} className="flex items-center gap-1">
              <ChevronRight className="h-3 w-3" />
              <Link href={`/codes/${ancestor}`} className="font-mono hover:text-gray-800 hover:underline">
                {ancestor}
              </Link>
            </span>
          ))}
          <span className="flex items-center gap-1">
            <ChevronRight className="h-3 w-3" />
            <span className="font-mono font-semibold text-gray-800">{code}</span>
          </span>
        </nav>

        {/* Code card (if exact match exists) */}
        {entry ? (
          <Card className={`p-6 border-l-4 ${colorClass}`}>
            <div className="flex items-start gap-4">
              <div className="h-10 w-10 rounded-full bg-white flex items-center justify-center shadow-sm shrink-0">
                <Icon className="h-5 w-5 text-gray-600" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap mb-1">
                  <span className="font-mono font-bold text-xl text-gray-800">{entry.code}</span>
                  {typeLabel && <Badge variant="outline" className="text-xs">{typeLabel}</Badge>}
                </div>
                <p className="text-gray-700 text-base leading-relaxed">{entry.description}</p>
              </div>
            </div>
          </Card>
        ) : (
          /* Virtual category header (no exact DB match, but has children) */
          <Card className="p-6 border-l-4 border-l-gray-300 bg-gray-50">
            <div className="flex items-start gap-4">
              <div className="h-10 w-10 rounded-full bg-white flex items-center justify-center shadow-sm shrink-0">
                <FolderOpen className="h-5 w-5 text-gray-400" />
              </div>
              <div className="flex-1 min-w-0">
                <span className="font-mono font-bold text-xl text-gray-800">{code}</span>
                <p className="text-sm text-gray-400 mt-1">{t('cie10.category')}</p>
              </div>
            </div>
          </Card>
        )}

        {/* Metadata */}
        {entry?.metadata && Object.keys(entry.metadata).length > 0 && (
          <Card className="p-4">
            {entry.type === 'diagnosis' && <DiagnosisDetail meta={entry.metadata} />}
            {entry.type === 'procedure' && <ProcedureDetail meta={entry.metadata} />}
            {entry.type === 'chemical' && <ChemicalDetail meta={entry.metadata} />}
          </Card>
        )}

        {/* Children */}
        {children.length > 0 && (
          <ChildrenGrid items={children} />
        )}
      </div>
    </div>
  );
}
