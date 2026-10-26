import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { getFeed } from '../api/feed';
import CompanyProfile from '../components/CompanyProfile';
import type { NewsFeedResponse } from '../types/feed';

type SortKey = 'critical' | 'relevance' | 'date';

const SORT_LABELS: Record<SortKey, string> = {
  critical: 'Критичные сверху',
  relevance: 'По релевантности',
  date: 'Сначала новые',
};

const CLIENTS = [
  { id: 'U_14366', label: 'Компания U_14366' },
  { id: 'U_26030', label: 'Компания U_26030' },
];

export default function Feed() {
  const [feed, setFeed] = useState<NewsFeedResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [companyId, setCompanyId] = useState(CLIENTS[0].id);
  const [generation, setGeneration] = useState('');
  const [newsTitle, setNewsTitle] = useState('');
  const [newsBody, setNewsBody] = useState('');
  const [newsUrl, setNewsUrl] = useState('');
  const [busy, setBusy] = useState(false);
  const [sort, setSort] = useState<SortKey>('critical');
  const [onlyCritical, setOnlyCritical] = useState(false);
  const [areas, setAreas] = useState<string[]>([]);

  useEffect(() => {
    let cancelled = false;
    setError(null); setFeed(null);
    getFeed(companyId).then((f) => {if (!cancelled) setFeed(f);}).catch((e) => {if (!cancelled) setError(String(e));});
    return () => {cancelled = true;};
  }, [companyId]);

  async function generateLive(manual = false) {
    setBusy(true); setGeneration('Анализируем свежие новости и проверяем источники…');
    try {
      const response = manual
        ? await fetch('/api/insights/analyze', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({company_id:companyId, role:'CFO', news_title:newsTitle, news_body:newsBody, source_url:newsUrl || undefined, source_name:'Текст, предоставленный пользователем; достоверность не подтверждена'})})
        : await fetch(`/api/feed/refresh?company_id=${encodeURIComponent(companyId)}&role=CFO&limit=2`, {method:'POST'});
      const task = await response.json();
      if (!response.ok) throw new Error(task.detail || 'Не удалось запустить анализ');
      for (let i=0; i<180; i++) {
        await new Promise(resolve => setTimeout(resolve, 2000));
        const state = await (await fetch(`/api/feed/jobs/${task.job_id}`)).json();
        if (state.detail?.stage) setGeneration(state.detail.stage);
        if (state.status === 'completed' || state.status === 'failed') {
          setFeed(await getFeed(companyId));
          setGeneration(state.status === 'completed' ? `Опубликовано проверенных карточек: ${state.detail.published}` : 'Карточки не опубликованы: модель или проверка качества не дали подтверждённого результата.');
          return;
        }
      }
      setGeneration('Анализ продолжается. Обновите ленту позднее.');
    } catch (e) { setGeneration(String(e)); }
    finally { setBusy(false); }
  }

  const allAreas = useMemo(() => {
    const set = new Set<string>();
    feed?.events.forEach((e) => e.relevance.affected_areas.forEach((a) => set.add(a)));
    return Array.from(set).sort((a, b) => a.localeCompare(b, 'ru'));
  }, [feed]);

  const visible = useMemo(() => {
    if (!feed) return [];
    const list = feed.events.filter((e) => {
      if (onlyCritical && !e.relevance.is_critical) return false;
      if (areas.length > 0 && !areas.some((a) => e.relevance.affected_areas.includes(a))) {
        return false;
      }
      return true;
    });

    const time = (d?: string | null) => (d ? new Date(d).getTime() : 0);
    return [...list].sort((a, b) => {
      if (sort === 'date') return time(b.published_at) - time(a.published_at);
      if (sort === 'relevance') return b.relevance.score - a.relevance.score;
      const c = Number(b.relevance.is_critical) - Number(a.relevance.is_critical);
      return c !== 0 ? c : b.relevance.score - a.relevance.score;
    });
  }, [feed, sort, onlyCritical, areas]);

  const hasFilters = onlyCritical || areas.length > 0;

  function toggleArea(area: string) {
    setAreas((prev) => (prev.includes(area) ? prev.filter((a) => a !== area) : [...prev, area]));
  }

  function reset() {
    setOnlyCritical(false);
    setAreas([]);
  }

  if (error) return <p className="muted">Не удалось загрузить ленту: {error}</p>;
  if (!feed) return <p className="muted">Загрузка…</p>;

  return (
    <>
      <h1>Новостная аналитика</h1>
      <button className="btn-primary" disabled={busy} onClick={() => generateLive()}>{busy ? 'Идёт анализ…' : 'Сформировать живую ленту'}</button>
      <details className="card">
        <summary>Проверить новую новость</summary>
        <p className="muted">Вставьте ранее не показанную новость. Это пользовательский текст, а не подтверждённый первоисточник. Анализ проходит те же этапы отбора и аудита; публикация не гарантирована.</p>
        <label>Заголовок<br/><input style={{width:'100%'}} maxLength={1000} value={newsTitle} onChange={e => setNewsTitle(e.target.value)} /></label>
        <label>Ссылка на первоисточник (необязательно)<br/><input type="url" style={{width:'100%'}} maxLength={2000} value={newsUrl} onChange={e => setNewsUrl(e.target.value)} /></label>
        <label>Текст<br/><textarea style={{width:'100%',minHeight:120}} maxLength={30000} value={newsBody} onChange={e => setNewsBody(e.target.value)} /></label>
        <button className="btn-primary" disabled={busy || !newsTitle.trim() || !newsBody.trim()} onClick={() => generateLive(true)}>Проанализировать для выбранной компании</button>
      </details>
      {generation && <p className="muted">{generation}</p>}
      {feed.total_events === 0 && <p className="muted">Проверенных инсайтов пока нет. Запустите анализ свежих новостей.</p>}
      <p className="muted">
        {feed.company_name} · роль: {feed.target_role} · событий: {feed.total_events}, критичных:{' '}
        {feed.critical_events_count}
      </p>

      <label className="sort">
        <span className="muted small">Клиент</span>
        <select disabled={busy} value={companyId} onChange={(e) => setCompanyId(e.target.value)}>
          {CLIENTS.map((c) => (
            <option key={c.id} value={c.id}>
              {c.label}
            </option>
          ))}
        </select>
      </label>

      <CompanyProfile companyId={companyId} />

      <section className="filters">
        <div className="filters-row">
          <label className="toggle">
            <input
              type="checkbox"
              checked={onlyCritical}
              onChange={(e) => setOnlyCritical(e.target.checked)}
            />
            <span>Только критичные</span>
          </label>

          <label className="sort">
            <span className="muted small">Сортировка</span>
            <select value={sort} onChange={(e) => setSort(e.target.value as SortKey)}>
              {(Object.keys(SORT_LABELS) as SortKey[]).map((k) => (
                <option key={k} value={k}>
                  {SORT_LABELS[k]}
                </option>
              ))}
            </select>
          </label>
        </div>

        {allAreas.length > 0 && (
          <div className="chips">
            {allAreas.map((a) => (
              <button
                key={a}
                className={`chip chip-btn ${areas.includes(a) ? 'chip-active' : ''}`}
                onClick={() => toggleArea(a)}
                aria-pressed={areas.includes(a)}
              >
                {a}
              </button>
            ))}
          </div>
        )}

        <p className="muted small">
          Показано: {visible.length} из {feed.events.length}
          {hasFilters && (
            <>
              {' · '}
              <button className="link-btn" onClick={reset}>
                Сбросить фильтры
              </button>
            </>
          )}
        </p>
      </section>

      {visible.length === 0 && <p className="muted">По выбранным фильтрам событий нет.</p>}

      {visible.map((ev) => (
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