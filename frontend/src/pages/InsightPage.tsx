import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { getFeed } from '../api/feed';
import ChatPanel from '../components/ChatPanel';
import type { EventCard } from '../types/feed';
import OriginBadge from '../components/OriginBadge';

export default function InsightPage() {
  const { id } = useParams();
  const [card, setCard] = useState<EventCard | null | undefined>(undefined);

  useEffect(() => {
    getFeed().then((f) => setCard(f.events.find((e) => e.card_id === id) ?? null));
  }, [id]);

  if (card === undefined) return <p className="muted">Загрузка…</p>;
  if (card === null) return <p className="muted">Событие не найдено. <Link to="/news">К ленте</Link></p>;

  const q = card.six_questions;

  return (
    <>
      <Link to="/news" className="muted">← К ленте</Link>
      <h1>{card.title}</h1>

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
        <div className="two-cols">
          <div>
            <h4 className="risk">Риски</h4>
            <ul>{q.q4_consequences.risks.map((r) => <li key={r}>{r}</li>)}</ul>
          </div>
          <div>
            <h4 className="opp">Возможности</h4>
            <ul>{q.q4_consequences.opportunities.map((o) => <li key={o}>{o}</li>)}</ul>
          </div>
        </div>
      </section>

      <section className="card">
        <h3>{q.q5_recommended_actions.question}</h3>
        <OriginBadge origin={q.q5_recommended_actions.origin} />
        <h4>{q.q5_recommended_actions.title}</h4>
        <p>{q.q5_recommended_actions.description}</p>
        {q.q5_recommended_actions.bank_product_tag && (
          <span className="chip">{q.q5_recommended_actions.bank_product_tag}</span>
        )}
      </section>

      <section className="card bank">
        <h3>{q.q3_bank_evaluation.question}</h3>
        <OriginBadge origin={q.q3_bank_evaluation.origin} />
        {q.q3_bank_evaluation.has_report ? (
          <>
            {q.q3_bank_evaluation.report_title && <h4>{q.q3_bank_evaluation.report_title}</h4>}
            <p>{q.q3_bank_evaluation.text}</p>
          </>
        ) : (
          <p className="muted">Позиция банка по этой теме не найдена.</p>
        )}
      </section>

      <section className="card">
        <details>
          <summary><b>{q.q6_basis_of_conclusion.question}</b></summary>
          <h4>Источники</h4>
          <ul>
            {q.q6_basis_of_conclusion.sources.map((s) => (
              <li key={s.name + s.url_or_file}>
                {s.url_or_file?.startsWith('http') ? (
                  <a href={s.url_or_file} target="_blank" rel="noreferrer">{s.name}</a>
                ) : (
                  s.name
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
      <ChatPanel card={card} />
    </>
  );
}