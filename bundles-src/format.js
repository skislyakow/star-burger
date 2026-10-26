/** Форматирование денег для витрины: цены с API приходят строками. */

const priceFormatter = new Intl.NumberFormat('ru-RU', {
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});

export function formatPrice(value) {
  const price = Number(value);
  return Number.isFinite(price) ? priceFormatter.format(price) : '—';
}
