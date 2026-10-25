import { useEffect, useRef, useState } from 'react';
import { askQuestion } from '../api/chat';
import type { ChatMessage } from '../types/chat';
import type { EventCard } from '../types/feed';
import OriginBadge from './OriginBadge';

export default function ChatPanel({ card }: { card: EventCard }) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  const q = card.six_questions;
  
  const suggestions = [
    `Как это сделать: ${q.q5_recommended_actions.title}?`,
    ...q.q4_consequences.risks.slice(0, 1).map((r) => `Подробнее о риске: ${r}`),
  ];
  const cuts = ['Покажи по срокам', 'Покажи по рискам для ликвидности', 'Сравни с прошлым кварталом'];

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  async function send(text: string) {
    const question = text.trim();
    if (!question || loading) return;
    setInput('');
    setMessages((m) => [...m, { id: crypto.randomUUID(), role: 'user', text: question }]);
    setLoading(true);
    try {
      const res = await askQuestion({ card_id: card.card_id, question }, card);
      setMessages((m) => [
        ...m,
        { id: crypto.randomUUID(), role: 'assistant', text: res.answer, origin: res.origin, sources: res.sources },
      ]);
    } catch {
      setMessages((m) => [
        ...m,
        { id: crypto.randomUUID(), role: 'assistant', text: 'Не удалось получить ответ. Попробуйте еще раз.' },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <button className="chat-fab" onClick={() => setOpen(true)}>
        Задать вопрос
      </button>

      {open && <div className="chat-backdrop" onClick={() => setOpen(false)} />}

      <aside className={`chat-panel ${open ? 'open' : ''}`} aria-hidden={!open}>
        <div className="chat-head">
          <b>Уточнить по событию</b>
          <button className="chat-close" onClick={() => setOpen(false)} aria-label="Закрыть">
            ×
          </button>
        </div>

        <div className="chat-body">
          {messages.length === 0 && (
            <>
              <p className="muted">Спросите про последствия, действия или попросите другой разрез данных.</p>
              <div className="chips">
                {suggestions.map((s) => (
                  <button key={s} className="chip chip-btn" onClick={() => send(s)}>
                    {s}
                  </button>
                ))}
              </div>
              <p className="muted small">Другой разрез:</p>
              <div className="chips">
                {cuts.map((s) => (
                  <button key={s} className="chip chip-btn" onClick={() => send(s)}>
                    {s}
                  </button>
                ))}
              </div>
            </>
          )}

          {messages.map((m) => (
            <div key={m.id} className={`msg ${m.role}`}>
              {m.origin && <OriginBadge origin={m.origin} />}
              <p>{m.text}</p>
              {m.sources && m.sources.length > 0 && (
                <div className="msg-sources">
                  <span className="muted small">Первоисточники:</span>
                  {m.sources.map((s) =>
                    s.url_or_file?.startsWith('http') ? (
                      <a key={s.name} href={s.url_or_file} target="_blank" rel="noreferrer">
                        {s.name}
                      </a>
                    ) : (
                      <span key={s.name} className="muted small">
                        {s.name}
                        {s.page ? `, стр. ${s.page}` : ''}
                      </span>
                    ),
                  )}
                </div>
              )}
            </div>
          ))}

          {loading && <p className="muted">Агент думает…</p>}
          <div ref={endRef} />
        </div>

        <form
          className="chat-form"
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ваш вопрос…"
            disabled={loading}
          />
          <button type="submit" disabled={loading || !input.trim()}>
            Отправить
          </button>
        </form>
      </aside>
    </>
  );
}