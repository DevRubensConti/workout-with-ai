import type { Metadata, Viewport } from 'next';
import { Geist, Geist_Mono } from 'next/font/google';
import { Toaster } from 'sonner';

import { Providers } from '@/components/providers';
import { APP_DESCRIPTION, APP_NAME } from '@/lib/config';

import './globals.css';

const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin'],
});

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
  preload: false,
});

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  viewportFit: 'cover',
  interactiveWidget: 'resizes-content',
};

export const metadata: Metadata = {
  title: {
    default: APP_NAME,
    template: `%s | ${APP_NAME}`,
  },
  description: APP_DESCRIPTION,
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    // suppressHydrationWarning: necessário para o next-themes (classe "dark")
    <html lang="pt-BR" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} pr-[env(safe-area-inset-right)] pl-[env(safe-area-inset-left)] antialiased`}
      >
        <Providers>
          {children}
          <Toaster
            richColors
            closeButton
            position="top-right"
            offset={{
              top: 'calc(env(safe-area-inset-top, 0px) + 16px)',
              right: '16px',
            }}
            mobileOffset={{
              top: 'calc(env(safe-area-inset-top, 0px) + 16px)',
              left: '16px',
              right: '16px',
            }}
          />
        </Providers>
      </body>
    </html>
  );
}
