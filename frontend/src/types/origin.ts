import type { ContentOrigin } from './feed';

export const ORIGIN_STYLE: Record<ContentOrigin, { label: string; color: string }> = {
  'ФАКТ': { label: 'Факт', color: '#8e8e93' },
  'ПОЗИЦИЯ БАНКА': { label: 'Позиция Альфа-Банка', color: '#ef3124' },
  'ВЫВОД ИИ': { label: 'Вывод ИИ', color: '#7c5cff' },
  'РЕКОМЕНДАЦИЯ БАНКА': { label: 'Рекомендация банка', color: '#2fb344' },
  'ИСТОЧНИКИ': { label: 'Источники', color: '#4a90e2' },
};