'use client';

import * as React from 'react';
import { ThemeProvider as NextThemesProvider } from 'next-themes';

function BrowserThemeColor() {
  React.useEffect(() => {
    const meta = document.createElement('meta');
    meta.name = 'theme-color';
    const updateColor = () => {
      meta.content = getComputedStyle(document.documentElement)
        .getPropertyValue('--background')
        .trim();
    };
    updateColor();
    document.head.appendChild(meta);
    const observer = new MutationObserver(updateColor);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['class'],
    });
    return () => {
      observer.disconnect();
      meta.remove();
    };
  }, []);
  return null;
}

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
    >
      <BrowserThemeColor />
      {children}
    </NextThemesProvider>
  );
}
