import type { ContentOrigin, SourceItem } from './feed';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  origin?: ContentOrigin;
  sources?: SourceItem[];
}

// надо согласовать с бэкендом, что будет в ответе на вопрос, пока что просто пример
export interface ChatRequest {
  card_id: string;
  question: string;
}

export interface ChatResponse {
  answer: string;
  origin: ContentOrigin;
  sources: SourceItem[];
}