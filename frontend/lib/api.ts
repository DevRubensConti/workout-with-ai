// Mesmo dominio do site: o cookie HttpOnly tambem fica disponivel ao Next.js.

export const API_URL = '/api';

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

// FastAPI devolve `detail` como string (erros de negócio) ou lista (422).
function extractErrorMessage(data: unknown, fallback: string): string {
  if (data && typeof data === 'object' && 'detail' in data) {
    const detail = (data as { detail: unknown }).detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as { msg?: string };
      if (first?.msg) return first.msg;
    }
  }
  return fallback;
}

export async function apiFetch<T = unknown>(
  path: string,
  options: Omit<RequestInit, 'body'> & { body?: unknown } = {}
): Promise<T> {
  const { body, headers, ...rest } = options;

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...rest,
      credentials: 'include',
      headers: {
        ...(body !== undefined && { 'Content-Type': 'application/json' }),
        ...headers,
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError('Não foi possível conectar ao servidor.', 0);
  }

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new ApiError(
      extractErrorMessage(data, 'Ocorreu um erro inesperado.'),
      response.status
    );
  }

  return data as T;
}
