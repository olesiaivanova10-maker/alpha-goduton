import type { ContentOrigin } from '../types/feed';
import { ORIGIN_STYLE } from '../types/origin';

export default function OriginBadge({ origin }: { origin: ContentOrigin }) {
  const s = ORIGIN_STYLE[origin];
  return (
    <span className="badge" style={{ borderColor: s.color, color: s.color }}>
      {s.label}
    </span>
  );
}