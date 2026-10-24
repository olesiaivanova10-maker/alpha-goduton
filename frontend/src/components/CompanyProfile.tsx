import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { getCompanyContext } from '../api/company';
import type { CompanyContext, Counterparty } from '../types/company';

const PRODUCT_LABELS: Record<keyof CompanyContext['bank_products'], string> = {
  rko: 'РКО',
  credit: 'Кредиты',
  leasing: 'Лизинг',
  guarantees: 'Гарантии',
  deposits: 'Депозиты',
  salary_project: 'Зарплатный проект',
  factoring: 'Факторинг',
};

const rub = (n: number) =>
  new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(n);

function topCounterparties(list: Counterparty[], n = 5) {
  return [...list].sort((a, b) => b.payment_amount - a.payment_amount).slice(0, n);
}
const mln = (n: number) =>
  (n / 1_000_000).toLocaleString('ru-RU', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="kv">
      <span className="muted small">{label}</span>
      <span>{value ?? '—'}</span>
    </div>
  );
}

export default function CompanyProfile({ companyId }: { companyId: string }) {
  const [ctx, setCtx] = useState<CompanyContext | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setCtx(null);
    setError(null);
    getCompanyContext(companyId)
      .then((d) => {
        if (!cancelled) setCtx(d);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      });
    return () => {
      cancelled = true;
    };
  }, [companyId]);

  if (error) {
    return (
      <section className="card">
        <p className="risk">{error}</p>
      </section>
    );
  }
  if (!ctx) {
    return (
      <section className="card">
        <p className="muted">Загрузка профиля…</p>
      </section>
    );
  }

  const products = (Object.keys(PRODUCT_LABELS) as (keyof typeof PRODUCT_LABELS)[]).filter(
    (k) => ctx.bank_products[k] > 0,
  );
  const counterparties = ctx.counterparties.filter((c) => c.company_id !== ctx.company_id);

  return (
    <section className="card">
      <h3>Профиль компании {ctx.company_id}</h3>

      <div className="profile-grid">
        <Row label="Отрасль" value={ctx.industry.name} />
        <Row label="ОКВЭД" value={ctx.industry.okved_code} />
        <Row
          label="Регион"
          value={[ctx.location.city, ctx.location.region].filter(Boolean).join(', ')}
        />
        <Row label="Форма собственности" value={ctx.organization.ownership} />
        <Row label="Возраст компании, лет" value={ctx.organization.age} />
        <Row label="Стадия" value={ctx.organization.development_stage} />
        <Row label="Выручка" value={ctx.scale.revenue == null ? null : rub(ctx.scale.revenue)} />
        <Row label="Сотрудники (ФНС)" value={ctx.scale.employees_fns} />
        <Row
          label="Внешняя торговля"
          value={
            ctx.foreign_trade.has_fts_data > 0
              ? (ctx.foreign_trade.country ?? 'есть данные')
              : 'нет данных'
          }
        />
        <Row
          label="Группа компаний"
          value={ctx.group_id ? `${ctx.group_id} (${ctx.group_companies.length})` : 'нет'}
        />
      </div>

      <p className="muted small">Продукты Альфа-Банка</p>
      <div className="chips">
        {products.length === 0 && <span className="muted">Нет подключённых продуктов</span>}
        {products.map((k) => (
          <span key={k} className="chip">
            {PRODUCT_LABELS[k]}
          </span>
        ))}
      </div>

      {counterparties.length > 0 && (
        <>
          <p className="muted small">
            Контрагенты: {new Set(counterparties.map((c) => c.company_id)).size}, крупнейшие по
            сумме платежей
          </p>
          <table className="cp-table">
            <thead>
              <tr>
                <th>ID контрагента</th>
                <th>Направление потока</th>
                <th className="num">Сумма, млн ₽</th>
                <th className="num">Кол-во платежей</th>
              </tr>
            </thead>
            <tbody>
              {topCounterparties(counterparties).map((c) => (
                <tr key={c.company_id + c.direction}>
                  <td>{c.company_id}</td>
                  <td>{c.direction === 'incoming' ? 'Входящий' : 'Исходящий'}</td>
                  <td className="num">{mln(c.payment_amount)}</td>
                  <td className="num">{c.payment_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
      {ctx.related_persons.length > 0 && (
        <p className="muted small">Связанных лиц: {ctx.related_persons.length}</p>
      )}

      {ctx.warnings.length > 0 && (
        <div className="warn">
          <b>Данные неполные:</b>
          <ul>
            {ctx.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}