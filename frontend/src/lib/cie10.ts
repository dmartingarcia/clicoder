import { config } from '@/lib/config';

export interface Cie10Result {
  code: string;
  description: string;
  type: 'diagnosis' | 'procedure' | 'chemical';
  metadata: Record<string, unknown>;
}

export async function searchCie10(q: string, limit = 8): Promise<Cie10Result[]> {
  if (q.trim().length < 2) return [];
  const url = `${config.apiUrl}/cie10/search?q=${encodeURIComponent(q.trim())}&limit=${limit}`;
  const res = await fetch(url);
  if (!res.ok) return [];
  const data = await res.json();
  return data.results ?? [];
}

export async function fetchCie10Code(code: string): Promise<Cie10Result | null> {
  const res = await fetch(`${config.apiUrl}/cie10/codes/${encodeURIComponent(code)}`);
  if (!res.ok) return null;
  const data = await res.json();
  return data.result ?? null;
}

export interface Cie10Child extends Cie10Result {
  is_virtual: boolean;
}

export interface Cie10ChildrenResult {
  children: Cie10Child[];
  is_leaf: boolean;
}

export async function fetchCie10Children(code: string): Promise<Cie10ChildrenResult> {
  const res = await fetch(`${config.apiUrl}/cie10/codes/${encodeURIComponent(code)}/children`);
  if (!res.ok) return { children: [], is_leaf: true };
  return res.json();
}

export function getAncestors(code: string): string[] {
  if (code.length <= 1) return [];

  const ancestors: string[] = [code[0]];
  const dotIdx = code.indexOf('.');

  if (dotIdx === -1) {
    for (let i = 2; i < code.length; i++) {
      ancestors.push(code.slice(0, i));
    }
  } else {
    if (dotIdx > 1) ancestors.push(code.slice(0, dotIdx));
    for (let i = dotIdx + 2; i < code.length; i++) {
      ancestors.push(code.slice(0, i));
    }
  }

  return ancestors.filter((a) => a !== code);
}
