import type { NewsFeedResponse } from '../types/feed';
import example from '../mocks/feed.example.json';

const USE_MOCK = true;

export async function getFeed(): Promise<NewsFeedResponse> {
  if (USE_MOCK) {
    return example as unknown as NewsFeedResponse;
  }
  const res = await fetch('/api/feed');
  if (!res.ok) throw new Error(`Feed request failed: ${res.status}`);
  return res.json();
}