import type { NewsFeedResponse } from '../types/feed';
export async function getFeed(companyId = "U_14366", role = "CFO"): Promise<NewsFeedResponse> {
  const res = await fetch(`/api/feed?company_id=${encodeURIComponent(companyId)}&role=${encodeURIComponent(role)}`);
  if (!res.ok) throw new Error(`Feed request failed: ${res.status}`);
  return res.json();
}