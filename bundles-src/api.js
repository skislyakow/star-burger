/** Тонкий клиент API витрины: fetch, CSRF и человеческие тексты ошибок. */

const NETWORK_ERROR =
  'Не удалось связаться с сервером. Проверьте соединение и попробуйте ещё раз.';

export class ApiError extends Error {
  constructor(message, status = 0) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

function getCsrfToken() {
  const input = document.querySelector('[name=csrfmiddlewaretoken]');
  if (input && input.value) {
    return input.value;
  }

  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : '';
}

async function readErrorMessage(response) {
  if (response.status === 429) {
    return 'Слишком много заказов подряд. Подождите немного и попробуйте снова.';
  }

  try {
    const data = await response.json();
    if (data && typeof data === 'object') {
      if (typeof data.detail === 'string') {
        return data.detail;
      }
      for (const value of Object.values(data)) {
        if (Array.isArray(value) && value.length) {
          return String(value[0]);
        }
        if (typeof value === 'string') {
          return value;
        }
      }
    }
  } catch (error) {
    // Тело ответа не JSON — ниже отдадим общий текст.
  }

  return `Ошибка сервера (${response.status}). Попробуйте ещё раз.`;
}

async function request(url, options = {}) {
  let response;

  try {
    response = await fetch(url, options);
  } catch (error) {
    throw new ApiError(NETWORK_ERROR);
  }

  if (!response.ok) {
    throw new ApiError(await readErrorMessage(response), response.status);
  }

  return response.json();
}

export function getProducts() {
  return request('/api/products/');
}

export function getBanners() {
  return request('/api/banners/');
}

export function submitOrder(order) {
  return request('/api/order/', {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrfToken(),
    },
    body: JSON.stringify(order),
  });
}
