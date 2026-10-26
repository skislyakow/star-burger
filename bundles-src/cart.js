/** Корзина как чистые функции: без React, без мутаций, всё тестируется. */

export function normalizeQuantity(value) {
  const quantity = Math.floor(Number(value));
  return Number.isFinite(quantity) && quantity > 0 ? quantity : 1;
}

export function addToCart(cart, product) {
  const quantity = normalizeQuantity(product.quantity);
  const index = cart.findIndex((item) => item.id === product.id);

  if (index === -1) {
    return [...cart, { ...product, quantity }];
  }

  return cart.map((item, itemIndex) =>
    itemIndex === index
      ? {
          ...item,
          quantity: normalizeQuantity(item.quantity) + quantity,
        }
      : item,
  );
}

export function removeFromCart(cart, productId) {
  return cart.filter((item) => item.id !== productId);
}

export function cartCount(cart) {
  return cart.reduce((count, item) => count + item.quantity, 0);
}

export function cartTotal(cart) {
  const total = cart.reduce(
    (sum, item) => sum + Number(item.price) * item.quantity,
    0,
  );
  return Math.round(total * 100) / 100;
}

export function toOrderLines(cart) {
  return cart.map((item) => ({
    product: item.id,
    quantity: item.quantity,
  }));
}
