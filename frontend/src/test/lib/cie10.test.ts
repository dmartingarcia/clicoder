import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import '../helpers';

import { searchCie10, fetchCie10Code, fetchCie10Children, getAncestors } from '@/lib/cie10';

function mockFetch(body: unknown, ok = true, status = 200) {
  global.fetch = vi.fn().mockResolvedValue({
    ok,
    status,
    json: async () => body,
  } as Response);
}

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('searchCie10', () => {
  it('returns empty array when query is < 2 chars', async () => {
    mockFetch({ results: [{ code: 'I10' }] });
    const result = await searchCie10('a');
    expect(result).toEqual([]);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('returns empty array when query is blank', async () => {
    mockFetch({ results: [{ code: 'I10' }] });
    const result = await searchCie10('  ');
    expect(result).toEqual([]);
  });

  it('fetches with trimmed query and default limit 8', async () => {
    mockFetch({ results: [] });
    await searchCie10('  hiper  ');
    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain('q=hiper');
    expect(url).toContain('limit=8');
  });

  it('uses custom limit when provided', async () => {
    mockFetch({ results: [] });
    await searchCie10('diabetes', 20);
    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain('limit=20');
  });

  it('returns the results array from the response', async () => {
    const results = [
      { code: 'I10', description: 'Hypertension', type: 'diagnosis' as const, metadata: {} },
    ];
    mockFetch({ results });
    const data = await searchCie10('hiper');
    expect(data).toEqual(results);
  });

  it('returns empty array when response has no results key', async () => {
    mockFetch({});
    const data = await searchCie10('hiper');
    expect(data).toEqual([]);
  });

  it('returns empty array when fetch response is not ok', async () => {
    mockFetch({}, false, 500);
    const data = await searchCie10('hiper');
    expect(data).toEqual([]);
  });

  it('URL-encodes the query', async () => {
    mockFetch({ results: [] });
    await searchCie10('diabetes tipo 2');
    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain(encodeURIComponent('diabetes tipo 2'));
  });
});

describe('fetchCie10Code', () => {
  it('returns the result object on success', async () => {
    const result = { code: 'I10', description: 'Hypertension', type: 'diagnosis' as const, metadata: {} };
    mockFetch({ result });
    const data = await fetchCie10Code('I10');
    expect(data).toEqual(result);
  });

  it('returns null when response is not ok', async () => {
    mockFetch({}, false, 404);
    const data = await fetchCie10Code('ZZZZ');
    expect(data).toBeNull();
  });

  it('returns null when response has no result key', async () => {
    mockFetch({});
    const data = await fetchCie10Code('I10');
    expect(data).toBeNull();
  });

  it('fetches the correct URL with encoded code', async () => {
    mockFetch({ result: null });
    await fetchCie10Code('I10.0');
    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe('http://localhost:4000/cie10/codes/I10.0');
  });
});

describe('fetchCie10Children', () => {
  it('returns children and is_leaf on success', async () => {
    const body = { children: [{ code: 'I10.0', description: 'Essential', type: 'diagnosis', metadata: {}, is_virtual: false }], is_leaf: false };
    mockFetch(body);
    const data = await fetchCie10Children('I10');
    expect(data.children).toHaveLength(1);
    expect(data.is_leaf).toBe(false);
  });

  it('returns empty children and is_leaf=true when response is not ok', async () => {
    mockFetch({}, false, 404);
    const data = await fetchCie10Children('ZZZZ');
    expect(data).toEqual({ children: [], is_leaf: true });
  });

  it('fetches the correct URL', async () => {
    mockFetch({ children: [], is_leaf: true });
    await fetchCie10Children('I10');
    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe('http://localhost:4000/cie10/codes/I10/children');
  });
});

describe('getAncestors', () => {
  it('returns empty array for single-char code', () => {
    expect(getAncestors('I')).toEqual([]);
  });

  it('returns chapter only for two-char code', () => {
    expect(getAncestors('I1')).toEqual(['I']);
  });

  it('returns correct ancestors for 3-char code without dot', () => {
    expect(getAncestors('I10')).toEqual(['I', 'I1']);
  });

  it('returns correct ancestors for code with dot', () => {
    expect(getAncestors('I10.0')).toEqual(['I', 'I10']);
  });

  it('returns correct ancestors for deeper code with dot', () => {
    expect(getAncestors('J45.00')).toEqual(['J', 'J45', 'J45.0']);
  });

  it('filters out the code itself from ancestors', () => {
    const ancestors = getAncestors('I1');
    expect(ancestors).not.toContain('I1');
  });

  it('returns empty array for single-char code (length <= 1)', () => {
    expect(getAncestors('A')).toEqual([]);
  });
});
