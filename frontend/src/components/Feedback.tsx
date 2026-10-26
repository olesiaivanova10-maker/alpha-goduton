import { useState } from 'react';
export default function Feedback({cardId}: {cardId: string}) {
  const [rating,setRating]=useState(4);
  const [comment,setComment]=useState('');
  const [state,setState]=useState('');
  const [busy,setBusy]=useState(false);
  async function send() {
    setBusy(true);
    try {
      const res=await fetch('/feedback',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({insight_id:cardId,company_id:cardId.match(/^card-(U_[^-]+)-/)?.[1],rating,comment})});
      if (!res.ok) throw new Error();
      setState('Оценка сохранена. Она поступит команде для проверки качества, автоматического обучения на ней нет.');
    } catch {setState('Не удалось сохранить оценку. Попробуйте снова.');}
    finally {setBusy(false);}
  }
  return <section className="card"><h3>Насколько полезен разбор?</h3>
    <label>Оценка <select value={rating} onChange={e=>setRating(Number(e.target.value))}>{[1,2,3,4,5].map(n=><option key={n} value={n}>{n}</option>)}</select></label>
    <p><textarea aria-label="Комментарий к оценке" placeholder="Что неточно или чего не хватает?" maxLength={2000} value={comment} onChange={e=>setComment(e.target.value)}/></p>
    <button disabled={busy} onClick={send}>Сохранить оценку</button><p role="status">{state}</p>
  </section>;
}
