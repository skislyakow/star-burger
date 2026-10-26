import { describe, expect, it } from 'vitest';

import {
  addToCart,
  cartCount,
  cartTotal,
  normalizeQuantity,
  removeFromCart,
  toOrderLines,
} from './cart';
import { formatPrice } from './format';

const burger = { id: 1, name: 'Бургер', price: '199.00' };
const cola = { id: 2, name: 'Кола', price: '99.50' };

describe('normalizeQuantity', () => {
  it('округляет вниз до целого', () => {
    expect(normalizeQuantity(2.7)).toBe(2);
  });

  it('заменяет ноль, отрицательное и мусор на единицу', () => {
    expect(normalizeQuantity(0)).toBe(1);
    expect(normalizeQuantity(-3)).toBe(1);
    expect(normalizeQuantity('abc')).toBe(1);
  });
});

describe('addToCart', () => {
  it('добавляет новый товар с количеством', () => {
    expect(addToCart([], { ...burger, quantity: 2 })).toEqual([
      { ...burger, quantity: 2 },
    ]);
  });

  it('складывает количество повторного товара, не дублируя строку', () => {
    const cart = addToCart([], { ...burger, quantity: 1 });

    const next = addToCart(cart, { ...burger, quantity: 2 });

    expect(next).toHaveLength(1);
    expect(next[0].quantity).toBe(3);
  });

  it('не мутирует исходную корзину', () => {
    const cart = [{ ...burger, quantity: 1 }];

    addToCart(cart, { ...burger, quantity: 1 });
    addToCart(cart, { ...cola, quantity: 1 });

    expect(cart).toEqual([{ ...burger, quantity: 1 }]);
  });
});

describe('removeFromCart', () => {
  it('удаляет только выбранный товар', () => {
    const cart = [
      { ...burger, quantity: 1 },
      { ...cola, quantity: 1 },
    ];

    expect(removeFromCart(cart, burger.id)).toEqual([
      { ...cola, quantity: 1 },
    ]);
  });

  it('оставляет корзину нетронутой, если товара в ней нет', () => {
    // Регрессия: раньше splice(-1) в этом случае удалял последний товар.
    const cart = [
      { ...burger, quantity: 1 },
      { ...cola, quantity: 1 },
    ];

    expect(removeFromCart(cart, 999)).toEqual(cart);
  });
});

describe('cartCount', () => {
  it('считает штуки, а не строки', () => {
    const cart = [
      { ...burger, quantity: 2 },
      { ...cola, quantity: 3 },
    ];

    expect(cartCount(cart)).toBe(5);
  });
});

describe('cartTotal', () => {
  it('считает сумму с копейками без хвостов float', () => {
    const cart = [
      { ...burger, quantity: 2 },
      { ...cola, quantity: 1 },
    ];

    expect(cartTotal(cart)).toBe(497.5);
    expect(cartTotal([])).toBe(0);
  });
});

describe('toOrderLines', () => {
  it('отдаёт серверу только id и количество', () => {
    const cart = [
      { ...burger, quantity: 2 },
      { ...cola, quantity: 1 },
    ];

    expect(toOrderLines(cart)).toEqual([
      { product: burger.id, quantity: 2 },
      { product: cola.id, quantity: 1 },
    ]);
  });
});

describe('formatPrice', () => {
  it('показывает рубли по-русски', () => {
    expect(formatPrice('199.00')).toBe('199');
    expect(formatPrice(497.5)).toBe('497,5');
    expect(formatPrice(0)).toBe('0');
  });

  it('не падает на мусоре', () => {
    expect(formatPrice('abc')).toBe('—');
  });
});
