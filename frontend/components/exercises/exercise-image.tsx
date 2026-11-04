'use client';

import { Dumbbell } from 'lucide-react';
import Image from 'next/image';
import { useState, useSyncExternalStore } from 'react';

import { exerciseImageUrl } from '@/lib/config';
import { cn } from '@/lib/utils';

interface ExerciseImageProps {
  path: string | undefined;
  alt: string;
  sizes: string;
  className?: string;
  priority?: boolean;
}

const HOVER_QUERY = '(hover: hover) and (pointer: fine)';

function subscribeToHover(onChange: () => void) {
  const media = window.matchMedia(HOVER_QUERY);
  media.addEventListener('change', onChange);
  return () => media.removeEventListener('change', onChange);
}

export function ExerciseHoverImage(props: ExerciseImageProps) {
  const canHover = useSyncExternalStore(
    subscribeToHover,
    () => window.matchMedia(HOVER_QUERY).matches,
    () => false
  );
  return canHover ? <ExerciseImage {...props} /> : null;
}

// O pai precisa ter `position: relative` e um tamanho definido.
export function ExerciseImage({
  path,
  alt,
  sizes,
  className,
  priority,
}: ExerciseImageProps) {
  const [failed, setFailed] = useState(false);

  if (!path || failed) {
    return (
      <div
        role="img"
        aria-label={alt}
        className="text-muted-foreground/50 absolute inset-0 flex items-center justify-center"
      >
        <Dumbbell className="size-10" />
      </div>
    );
  }

  return (
    <Image
      src={exerciseImageUrl(path)}
      alt={alt}
      fill
      sizes={sizes}
      priority={priority}
      // As imagens já são JPGs leves no Storage; evita configurar o otimizador do Next.
      unoptimized
      onError={() => setFailed(true)}
      className={cn('object-cover', className)}
    />
  );
}
