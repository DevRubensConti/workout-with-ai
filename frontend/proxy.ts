import { jwtVerify } from 'jose';
import type { NextRequest } from 'next/server';
import { NextResponse } from 'next/server';

// Rotas acessíveis sem login
const publicRoutes = [
  '/login',
  '/register',
  '/forgot-password',
  '/reset-password',
];

function getSecret() {
  const key = process.env.JWT_SECRET_KEY;
  if (!key) {
    console.error(
      'JWT_SECRET_KEY não configurada: nenhuma sessão será aceita.'
    );
    return null;
  }
  return new TextEncoder().encode(key);
}

async function hasValidSession(token: string | undefined) {
  const secret = getSecret();
  if (!token || !secret) return false;
  try {
    await jwtVerify(token, secret, { algorithms: ['HS256'] });
    return true;
  } catch {
    return false;
  }
}

// Primeira barreira (assinatura + expiração do JWT). A autorização fina e a
// checagem de usuário ativo acontecem na API e no layout autenticado.
export async function proxy(request: NextRequest) {
  const { pathname, searchParams } = request.nextUrl;
  const token = request.cookies.get('access_token')?.value;
  const isPublicRoute = publicRoutes.includes(pathname);
  const validSession = await hasValidSession(token);

  if (validSession) {
    // `session=expired`: o layout detectou sessão inválida no servidor (ex.:
    // usuário desativado). Deixa abrir o /login para limpar o cookie.
    if (isPublicRoute && searchParams.get('session') !== 'expired') {
      return NextResponse.redirect(new URL('/home', request.url));
    }
    return NextResponse.next();
  }

  if (isPublicRoute) return NextResponse.next();

  const response = NextResponse.redirect(new URL('/login', request.url));
  if (token) response.cookies.delete('access_token');
  return response;
}

export const config = {
  matcher: [
    '/((?!api|_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
};
