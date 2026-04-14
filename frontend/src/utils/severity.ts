export type SeverityTone = 'high' | 'medium' | 'low';

export function normalizeSeverity(value: string | null | undefined): SeverityTone {
  const raw = (value ?? '').trim().toLowerCase();

  if (raw === 'high' || raw === 'h' || raw === '高' || raw.includes('高')) {
    return 'high';
  }

  if (raw === 'low' || raw === 'l' || raw === '低' || raw.includes('低')) {
    return 'low';
  }

  return 'medium';
}

export function severityLabel(value: string | null | undefined): string {
  const normalized = normalizeSeverity(value);
  if (normalized === 'high') return '高'; 
  if (normalized === 'low') return '低';
  return '中';
}
