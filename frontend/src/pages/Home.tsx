import { useNavigate } from 'react-router-dom';
import { Button } from '@alfalab/core-components/button';

export default function Home() {
  const navigate = useNavigate();
  return (
    <>
      <section className="entry">
        <h1>Новостная аналитика</h1>
        <p>Как события на рынке влияют именно на ваш бизнес</p>
        <Button view="accent" onClick={() => navigate('/news')}>
          Открыть
        </Button>
      </section>
      <section className="cards">
        <div className="card">
          <div className="demo-head">
            <h3>Счета</h3>
            <span className="badge demo">Демо-макет</span>
          </div>
          <div className="skeleton-line" />
          <div className="skeleton-line short" />
          <p className="muted small">Подключение к счетам интернет-банка в прототипе не реализовано.</p>
    </div>
        <div className="card">
          <div className="demo-head">
            <h3>Платежи</h3>
            <span className="badge demo">Демо-макет</span>
          </div>
          <div className="skeleton-line" />
          <div className="skeleton-line short" />
          <p className="muted small">Платёжные операции в прототипе не реализованы.</p>
        </div>
      </section>
    </>
  );
}