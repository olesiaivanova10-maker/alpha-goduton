import type { NewsFeedResponse } from '../types/feed';
import example from '../mocks/feed.example.json';

const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";

export async function getFeed(companyId = "U_14366", role = "CFO"): Promise<NewsFeedResponse> {
  if (USE_MOCK) {
    return example as unknown as NewsFeedResponse;
  }
  const res = await fetch(`/api/feed?company_id=${encodeURIComponent(companyId)}&role=${encodeURIComponent(role)}`);
  if (!res.ok) throw new Error(`Feed request failed: ${res.status}`);
  return res.json();
}