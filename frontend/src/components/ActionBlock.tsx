import { useState } from 'react';
import { Button } from '@alfalab/core-components/button';
import { submitAction } from '../api/action';
import type { EventCard } from '../types/feed';
import OriginBadge from './OriginBadge';

type Status = 'idle' | 'confirm' | 'sending' | 'done' | 'error';

export default function ActionBlock({ card }: { card: EventCard }) {
  const a = card.six_questions.q5_recommended_actions;
  const [status, setStatus] = useState<Status>('idle');

  async function confirm() {
    setStatus('sending');
    try {
      await submitAction({ card_id: card.card_id, action_type: a.action_type });
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
          <p className="opp">Заявка отправлена. Менеджер свяжется с вами.</p>
        ) : (
          <Button view="accent" onClick={() => setStatus('confirm')}>
            {a.button_text}
          </Button>
        )}
        {status === 'error' && (
          <p className="risk">Не удалось отправить заявку. Попробуйте еще раз.</p>
        )}
      </div>

      {(status === 'confirm' || status === 'sending') && (
        <>
          <div className="modal-backdrop" onClick={() => status === 'confirm' && setStatus('idle')} />
          <div className="modal" role="dialog" aria-modal="true">
            <h3>{a.title}</h3>
            <p className="muted">{a.description}</p>
            <p className="muted small">
              Заявка будет передана менеджеру Альфа-Банка. Вы не берете на себя обязательств.
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
                Отправить заявку
              </Button>
            </div>
          </div>
        </>
      )}
    </section>
  );
}