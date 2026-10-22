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
        <div className="card"><h3>Счета</h3><p>Заглушка</p></div>
        <div className="card"><h3>Платежи</h3><p>Заглушка</p></div>
      </section>
    </>
  );
}