import { useState } from 'react';
import { Button } from '@alfalab/core-components/button';
import type { EventCard } from '../types/feed';
import OriginBadge from './OriginBadge';

type Status = 'idle' | 'confirm' | 'sending' | 'done' | 'error';

export default function ActionBlock({ card }: { card: EventCard }) {
  const a = card.six_questions.q5_recommended_actions;
  const [status, setStatus] = useState<Status>('idle');

  async function confirm() {
    setStatus('sending');
    try {
      await navigator.clipboard.writeText(`${card.title}\n${a.title}\n${a.description}\nКарточка: ${card.card_id}`);
      setStatus('done');
    } catch {
      setStatus('error');
    }
  }

  return (
    <section className="card">
      <h3>{a.question}</h3>
      <OriginBadge origin={a.origin} />
      <h4>{a.title}</h4>
      <p>{a.description}</p>
      {a.bank_product_tag && <span className="chip">{a.bank_product_tag}</span>}

      <div className="action-row">
        {status === 'done' ? (
          <p className="opp">Текст для обсуждения скопирован. Передайте его своему менеджеру.</p>
        ) : (
          <Button view="accent" onClick={() => setStatus('confirm')}>
            Подготовить вопрос менеджеру
          </Button>
        )}
        {status === 'error' && (
          <p className="risk">Не удалось скопировать текст. Выделите и скопируйте описание выше.</p>
        )}
      </div>

      {(status === 'confirm' || status === 'sending') && (
        <>
          <div className="modal-backdrop" onClick={() => status === 'confirm' && setStatus('idle')} />
          <div className="modal" role="dialog" aria-modal="true">
            <h3>{a.title}</h3>
            <p className="muted">{a.description}</p>
            <p className="muted small">
              Это прототип: автоматической отправки в банк нет. Скопируйте текст и передайте менеджеру самостоятельно.
            </p>
            <div className="modal-actions">
              <button
                className="btn-cancel"
                onClick={() => setStatus('idle')}
                disabled={status === 'sending'}
              >
                Отмена
              </button>
              <Button view="accent" onClick={confirm} loading={status === 'sending'}>
                Скопировать текст
              </Button>
            </div>
          </div>
        </>
      )}
    </section>
  );
}