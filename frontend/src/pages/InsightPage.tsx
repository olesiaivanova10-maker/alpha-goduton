import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import ChatPanel from '../components/ChatPanel';
import type { EventCard } from '../types/feed';
import ActionBlock from '../components/ActionBlock';
import OriginBadge from '../components/OriginBadge';
import Feedback from '../components/Feedback';

export default function InsightPage() {
  const { id } = useParams();
  const [card, setCard] = useState<EventCard | null | undefined>(undefined);
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [flash, setFlash] = useState<string | null>(null);

  useEffect(() => {
    fetch(`/api/cards/${encodeURIComponent(id || '')}`).then(r => {if (!r.ok) throw new Error(); return r.json();}).then(setCard).catch(() => setCard(null));
  }, [id]);

  if (card === undefined) return <p className="muted">Загрузка…</p>;
  if (card === null) return <p className="muted">Событие не найдено. <Link to="/news">К ленте</Link></p>;

  const q = card.six_questions;
  const sources = q.q6_basis_of_conclusion.sources;

  const sourceIndex = (filename?: string, title?: string | null) => {
    let i = sources.findIndex((s) => !!filename && s.url_or_file === filename);
    if (i < 0 && title) i = sources.findIndex((s) => s.name === title);
    return i;
  };

  const jumpToSource = (i: number) => {
    if (i < 0) return;
    setSourcesOpen(true);
    setFlash(`src-${i}`);
    setTimeout(() => {
      document.getElementById(`src-${i}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 80);
    setTimeout(() => setFlash(null), 2500);
  };

  return (
    <>
      <Link to="/news" className="muted">← К ленте</Link>
      <h1>{card.title}</h1>
      <p className="muted small">Сохранённый разбор: после обновления данных или моделей его выводы могут отличаться от новой ленты.</p>
      {card.analysis_status === 'degraded' && <p className="warn">Сводка PDF моделью недоступна. Разбор прошёл аудит с исходными фрагментами документов; сверяйте цифры с PDF.</p>}

      <section className="card">
        <h3>{q.q1_what_happened.question}</h3>
        <OriginBadge origin={q.q1_what_happened.origin} />
        <p>{q.q1_what_happened.text}</p>
      </section>

      <section className="card">
        <h3>{q.q2_why_matters.question}</h3>
        <OriginBadge origin={q.q2_why_matters.origin} />
        <p>{q.q2_why_matters.text}</p>
        <div className="chips">
          {card.client_features.influencing_signals.map((s) => (
            <span key={s} className="chip">{s}</span>
          ))}
        </div>
      </section>

      <section className="card">
        <h3>{q.q4_consequences.question}</h3>
        <OriginBadge origin={q.q4_consequences.origin} />
        <h4>Риски</h4>
        <ul>{q.q4_consequences.risks.map((r) => <li key={r}>{r}</li>)}</ul>
        <h4>Возможности</h4>
        <ul>{q.q4_consequences.opportunities.map((r) => <li key={r}>{r}</li>)}</ul>
      </section>
      <ActionBlock card={card} />

      <section className="card bank">
        <h3>{q.q3_bank_evaluation.question}</h3>
        <OriginBadge origin={q.q3_bank_evaluation.origin} />
        {q.q3_bank_evaluation.has_report ? (
          <>
            {q.q3_bank_evaluation.report_title && (
              <h4>
                <a
                  href="#sources"
                  className="src-link"
                  onClick={(ev) => {
                    ev.preventDefault();
                    jumpToSource(
                      sourceIndex(
                        q.q3_bank_evaluation.bank_excerpts?.[0]?.filename,
                        q.q3_bank_evaluation.report_title,
                      ),
                    );
                  }}
                >
                  {q.q3_bank_evaluation.report_title}
                </a>
              </h4>
            )}
            {(q.q3_bank_evaluation.bank_excerpts ?? []).map((e, i) => (
              <div key={i}>
                <b>
                  <a
                    href="#sources"
                    className="src-link"
                    onClick={(ev) => {
                      ev.preventDefault();
                      jumpToSource(sourceIndex(e.filename));
                    }}
                  >
                    Материал Альфа-Банка · {e.filename}, стр. {e.page}
                  </a>
                </b>
                <p className="muted small">Дата отчёта: {e.report_date || 'не установлена'}. {e.extraction_method === 'ocr' ? 'Текст распознан: цифры следует сверять с PDF.' : 'Текст извлечён из PDF.'} Исторический материал не является новой рекомендацией.</p>
                <blockquote>{e.text}</blockquote>
                <a href={`/api/reports/files/${encodeURIComponent(e.filename)}#page=${e.page}`} target="_blank" rel="noreferrer">Открыть страницу первоисточника</a>
              </div>
            ))}
            <h4>Интерпретация материала моделью</h4>
            <p>{q.q3_bank_evaluation.text}</p>
          </>
        ) : (
          <p className="muted">Позиция банка по этой теме не найдена.</p>
        )}
      </section>

      <section className="card">
        <details
          open={sourcesOpen}
          onToggle={(ev) => setSourcesOpen((ev.currentTarget as HTMLDetailsElement).open)}
        >
          <summary><b>{q.q6_basis_of_conclusion.question}</b></summary>
          <h4>Источники</h4>
          <ul>
            {sources.map((s, i) => (
              <li
                key={s.name + s.url_or_file}
                id={`src-${i}`}
                className={flash === `src-${i}` ? 'src-flash' : undefined}
              >
                {s.url_or_file?.startsWith('http') ? (
                  <a href={s.url_or_file} target="_blank" rel="noreferrer">{s.name}</a>
                ) : (
                  s.url_or_file?.endsWith('.pdf') ? <a href={`/api/reports/files/${encodeURIComponent(s.url_or_file)}#page=${s.page || 1}`} target="_blank" rel="noreferrer">{s.name}</a> : s.name
                )}
                {s.page ? `, стр. ${s.page}` : ''}
              </li>
            ))}
          </ul>
          <h4>Признаки компании, повлиявшие на вывод</h4>
          <div className="chips">
            {q.q6_basis_of_conclusion.client_signals_used.map((s) => (
              <span key={s} className="chip">{s}</span>
            ))}
          </div>
        </details>
      </section>

      <p className="muted small">{card.disclaimer}</p>
      <Feedback cardId={card.card_id} />
      <ChatPanel card={card} />
    </>
  );
}