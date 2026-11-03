import { APP_NAME } from '@/lib/config';

export function Footer() {
  return (
    <footer className="border-t py-4">
      <div className="text-muted-foreground container mx-auto px-4 text-center text-xs md:px-6">
        © {new Date().getFullYear()} {APP_NAME}
      </div>
    </footer>
  );
}
