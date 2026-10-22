const blocks = [
  'Что произошло',
  'Почему это важно для вас',
  'Какие последствия возможны',
  'Какие действия могут быть релевантны',
  'Как это оценивает банк',
  'На чем основан вывод',
];

export default function InsightPage() {
  return (
    <>
      <h1>Название события</h1>
      {blocks.map((title) => (
        <section key={title} className="card">
          <h3>{title}</h3>
          <p className="muted">Заглушка</p>
        </section>
      ))}
    </>
  );
}