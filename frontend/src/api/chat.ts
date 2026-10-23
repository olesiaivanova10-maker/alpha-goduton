import type { ChatRequest, ChatResponse } from '../types/chat';
import type { EventCard } from '../types/feed';

const USE_MOCK = true;

export async function askQuestion(req: ChatRequest, card: EventCard): Promise<ChatResponse> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 800));
    return {
      answer:
        'Это демонстрационный ответ-заглушка. Здесь будет ответ агента на вопрос: «' +
        req.question +
        '». Он будет опираться на данные компании, новости и аналитику банка.',
      origin: 'ВЫВОД ИИ',
      sources: card.six_questions.q6_basis_of_conclusion.sources,
    };
  }
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(`Chat request failed: ${res.status}`);
  return res.json();
}