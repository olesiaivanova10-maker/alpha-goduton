import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getFeed } from '../api/feed';
import type { NewsFeedResponse } from '../types/feed';

export default function Feed() {
  const [feed, setFeed] = useState<NewsFeedResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getFeed().then(setFeed).catch((e) => setError(String(e)));
  }, []);

  if (error) return <p className="muted">Не удалось загрузить ленту: {error}</p>;
  if (!feed) return <p className="muted">Загрузка…</p>;

  return (
    <>
      <h1>Новостная аналитика</h1>
      <p className="muted">
        {feed.company_name} · роль: {feed.target_role} · событий: {feed.total_events}, критичных:{' '}
        {feed.critical_events_count}
      </p>
      {feed.events.map((ev) => (
        <Link key={ev.card_id} to={`/news/${ev.card_id}`} className="card event">
          <div className="event-head">
            {ev.relevance.is_critical && <span className="badge critical">Критично</span>}
            <span className="muted">
              {ev.published_at ? new Date(ev.published_at).toLocaleDateString('ru-RU') : ''}
            </span>
            <span className="muted">Релевантность: {Math.round(ev.relevance.score * 100)}%</span>
          </div>
          <h3>{ev.title}</h3>
          <p className="muted">{ev.relevance.rationale}</p>
        </Link>
      ))}
    </>
  );
}