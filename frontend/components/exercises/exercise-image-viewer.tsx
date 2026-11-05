'use client';

import {
  ChevronLeft,
  ChevronRight,
  Expand,
  ZoomIn,
  ZoomOut,
} from 'lucide-react';
import { useRef, useState } from 'react';

import { ExerciseImage } from '@/components/exercises/exercise-image';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog';

interface ExerciseImageViewerProps {
  images: string[];
  alt: string;
  sizes: string;
}

export function ExerciseImageViewer({
  images,
  alt,
  sizes,
}: ExerciseImageViewerProps) {
  const [open, setOpen] = useState(false);
  const [activeImage, setActiveImage] = useState(0);
  const [zoom, setZoom] = useState(1);
  const trigger = useRef<HTMLButtonElement>(null);
  const viewport = useRef<HTMLDivElement>(null);

  function resetView(index: number) {
    setActiveImage(index);
    setZoom(1);
    viewport.current?.scrollTo(0, 0);
  }

  return (
    <>
      <button
        ref={trigger}
        type="button"
        aria-label={`Ampliar imagens de ${alt}`}
        aria-haspopup="dialog"
        disabled={images.length === 0}
        onClick={() => {
          resetView(0);
          setOpen(true);
        }}
        className="focus-visible:ring-ring relative block h-full w-full cursor-zoom-in rounded-[inherit] outline-none focus-visible:ring-2 focus-visible:ring-inset disabled:cursor-default"
      >
        <ExerciseImage
          key={images[0] ?? 'empty'}
          path={images[0]}
          alt={alt}
          sizes={sizes}
          className="object-contain"
        />
        {images.length > 0 && (
          <span className="bg-overlay/80 text-overlay-foreground pointer-events-none absolute right-1 bottom-1 flex size-6 items-center justify-center rounded">
            <Expand className="size-4" aria-hidden="true" />
          </span>
        )}
      </button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent
          className="flex h-dvh max-h-dvh! w-full max-w-none flex-col overflow-hidden rounded-none sm:h-[90dvh] sm:max-h-[90dvh]! sm:w-[calc(100%-2rem)] sm:max-w-5xl sm:rounded-2xl"
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            trigger.current?.focus();
          }}
        >
          <header className="shrink-0 space-y-1 px-4 pt-[max(1rem,env(safe-area-inset-top))] pr-16 pb-3">
            <DialogTitle>{alt}</DialogTitle>
            <DialogDescription>
              Use + e − para ampliar. Arraste a imagem ampliada para ver os
              detalhes.
            </DialogDescription>
          </header>

          <div
            ref={viewport}
            role="region"
            aria-label="Imagem ampliada do exercício"
            tabIndex={0}
            className="bg-muted focus-visible:ring-ring min-h-0 flex-1 touch-auto overflow-auto outline-none focus-visible:ring-2 focus-visible:ring-inset"
          >
            <div
              className="relative"
              style={{ width: `${zoom * 100}%`, height: `${zoom * 100}%` }}
            >
              <ExerciseImage
                key={images[activeImage] ?? 'empty'}
                path={images[activeImage]}
                alt={`${alt} — posição ${activeImage + 1}`}
                sizes="100vw"
                className="object-contain"
              />
            </div>
          </div>

          <footer className="shrink-0 space-y-2 p-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
            {images.length > 1 && (
              <div className="flex items-center justify-center gap-3">
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  className="size-11"
                  aria-label="Posição anterior"
                  disabled={activeImage === 0}
                  onClick={() => resetView(activeImage - 1)}
                >
                  <ChevronLeft />
                </Button>
                <p aria-live="polite" className="text-sm tabular-nums">
                  Posição {activeImage + 1} de {images.length}
                </p>
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  className="size-11"
                  aria-label="Próxima posição"
                  disabled={activeImage === images.length - 1}
                  onClick={() => resetView(activeImage + 1)}
                >
                  <ChevronRight />
                </Button>
              </div>
            )}
            <div className="flex items-center justify-center gap-3">
              <Button
                type="button"
                variant="outline"
                size="icon"
                className="size-11"
                aria-label="Diminuir zoom"
                disabled={zoom === 1}
                onClick={() => setZoom((value) => Math.max(1, value - 0.5))}
              >
                <ZoomOut />
              </Button>
              <Button
                type="button"
                variant="ghost"
                className="h-11 min-w-20 tabular-nums"
                aria-label="Redefinir zoom"
                onClick={() => resetView(activeImage)}
              >
                {Math.round(zoom * 100)}%
              </Button>
              <Button
                type="button"
                variant="outline"
                size="icon"
                className="size-11"
                aria-label="Aumentar zoom"
                disabled={zoom === 3}
                onClick={() => setZoom((value) => Math.min(3, value + 0.5))}
              >
                <ZoomIn />
              </Button>
            </div>
          </footer>
        </DialogContent>
      </Dialog>
    </>
  );
}
