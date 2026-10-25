import type { CompanyContext } from '../types/company';

export async function getCompanyContext(companyId: string): Promise<CompanyContext> {
  const res = await fetch(`/api/companies/${encodeURIComponent(companyId)}/context`);
  if (res.status === 404) throw new Error('Компания не найдена');
  if (!res.ok) throw new Error(`Не удалось загрузить профиль: ${res.status}`);
  return res.json();
}