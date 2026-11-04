'use client';

import { Check, Plus, Search, SearchX } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

import { ExerciseImage } from '@/components/exercises/exercise-image';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { ApiError, apiFetch } from '@/lib/api';
import {
  equipmentLabel,
  muscleLabel,
  type ExerciseCatalogResponse,
  type ExerciseSummary,
} from '@/lib/exercises';
import { cn } from '@/lib/utils';

interface ExercisePickerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onAdd: (exercise: ExerciseSummary) => void;
}

interface State {
  key: string;
  data?: ExerciseCatalogResponse;
  error?: string;
}

const PAGE_SIZE = 12;

export function ExercisePicker({
  open,
  onOpenChange,
  onAdd,
}: ExercisePickerProps) {
  const [searchInput, setSearchInput] = useState('');
  const [query, setQuery] = useState('');
  const [muscleGroup, setMuscleGroup] = useState('');
  const [page, setPage] = useState(1);
  const [state, setState] = useState<State | null>(null);
  const [muscles, setMuscles] = useState<string[]>([]);
  const [added, setAdded] = useState<Record<string, number>>({});

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      setQuery(searchInput.trim());
      setPage(1);
    }, 300);
    return () => window.clearTimeout(timeout);
  }, [searchInput]);

  const url = useMemo(() => {
    const params = new URLSearchParams({
      locale: 'pt-BR',
      page: String(page),
      page_size: String(PAGE_SIZE),
    });
    if (query) params.set('q', query);
    if (muscleGroup) params.set('muscle_group', muscleGroup);
    return `/exercises?${params.toString()}`;
  }, [muscleGroup, page, query]);

  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    apiFetch<ExerciseCatalogResponse>(url, {
      cache: 'no-store',
      signal: controller.signal,
    })
      .then((data) => {
        if (controller.signal.aborted) return;
        setState({ key: url, data });
        setMuscles(data.filters.muscle_groups);
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setState({
          key: url,
          error:
            error instanceof ApiError
              ? error.message
              : 'Não foi possível carregar os exercícios.',
        });
      });
    return () => controller.abort();
  }, [open, url]);

  const loading = state?.key !== url;
  const data = state?.error ? undefined : state?.data;
  const items = data?.items ?? [];
  const addedTotal = Object.values(added).reduce(
    (sum, value) => sum + value,
    0
  );
  const chips = [
    { value: '', label: 'Todos' },
    ...muscles.map((value) => ({ value, label: muscleLabel(value) })),
  ];

  function handleAdd(exercise: ExerciseSummary) {
    onAdd(exercise);
    setAdded((current) => ({
      ...current,
      [exercise.id]: (current[exercise.id] ?? 0) + 1,
    }));
  }

  function handleOpenChange(next: boolean) {
    if (!next) setAdded({});
    onOpenChange(next);
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="flex h-[88dvh] max-w-3xl flex-col overflow-hidden">
        <div className="shrink-0 space-y-3 border-b p-4 sm:p-5">
          <div className="pr-10">
            <DialogTitle>Adicionar exercícios</DialogTitle>
            <DialogDescription className="mt-1">
              Busque no catálogo e toque para adicionar. Você pode escolher
              vários.
            </DialogDescription>
          </div>
          <div className="relative">
            <Search className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2" />
            <Input
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder="Buscar exercício…"
              aria-label="Buscar exercício"
              className="h-10 rounded-lg pl-9"
            />
          </div>
          <div
            role="group"
            aria-label="Grupo muscular"
            className="flex gap-2 overflow-x-auto pb-1"
          >
            {chips.map((chip) => (
              <button
                type="button"
                key={chip.value || 'all'}
                aria-pressed={muscleGroup === chip.value}
                onClick={() => {
                  setMuscleGroup(chip.value);
                  setPage(1);
                }}
                className={cn(
                  'shrink-0 rounded-full border px-3 py-1 text-sm whitespace-nowrap transition-colors',
                  muscleGroup === chip.value
                    ? 'bg-primary text-primary-foreground border-primary'
                    : 'text-muted-foreground hover:text-foreground'
                )}
              >
                {chip.label}
              </button>
            ))}
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain p-3">
          {state?.error ? (
            <p
              role="alert"
              className="text-destructive p-6 text-center text-sm"
            >
              {state.error}
            </p>
          ) : !loading && items.length === 0 ? (
            <div className="text-muted-foreground flex flex-col items-center gap-2 p-10 text-sm">
              <SearchX className="size-8" />
              Nenhum exercício encontrado.
            </div>
          ) : (
            <ul
              aria-busy={loading}
              className={cn(
                'space-y-1 transition-opacity',
                loading && 'pointer-events-none opacity-50'
              )}
            >
              {items.map((exercise) => {
                const count = added[exercise.id] ?? 0;
                return (
                  <li key={exercise.id}>
                    <button
                      type="button"
                      onClick={() => handleAdd(exercise)}
                      className="hover:bg-accent focus-visible:ring-ring/60 flex w-full items-center gap-3 rounded-lg p-2 text-left transition-colors outline-none focus-visible:ring-[3px]"
                    >
                      <span className="bg-muted relative h-14 w-20 shrink-0 overflow-hidden rounded-md">
                        <ExerciseImage
                          key={exercise.images[0] ?? 'empty'}
                          path={exercise.images[0]}
                          alt=""
                          sizes="80px"
                        />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block text-sm font-medium sm:text-base">
                          {exercise.name}
                        </span>
                        <span className="text-muted-foreground block truncate text-sm">
                          {muscleLabel(exercise.muscle_group)}
                          {exercise.equipment
                            ? ` · ${equipmentLabel(exercise.equipment)}`
                            : ''}
                        </span>
                      </span>
                      <span
                        className={cn(
                          'flex size-8 shrink-0 items-center justify-center rounded-full',
                          count > 0
                            ? 'bg-primary text-primary-foreground'
                            : 'bg-muted text-muted-foreground'
                        )}
                        role="img"
                        aria-label={
                          count > 0
                            ? `Adicionado ${count} ${count === 1 ? 'vez' : 'vezes'}`
                            : 'Adicionar'
                        }
                      >
                        {count > 0 ? (
                          <Check className="size-4" />
                        ) : (
                          <Plus className="size-4" />
                        )}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        <div className="flex items-center justify-between gap-3 border-t p-3">
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={!data || data.page <= 1 || loading}
              onClick={() => setPage((value) => value - 1)}
              className="hover:bg-accent h-9 rounded-md border px-3 text-sm disabled:pointer-events-none disabled:opacity-40"
            >
              Anterior
            </button>
            <span className="text-muted-foreground text-sm">
              {data ? `${data.page}/${data.total_pages || 1}` : '…'}
            </span>
            <button
              type="button"
              disabled={!data || data.page >= data.total_pages || loading}
              onClick={() => setPage((value) => value + 1)}
              className="hover:bg-accent h-9 rounded-md border px-3 text-sm disabled:pointer-events-none disabled:opacity-40"
            >
              Próxima
            </button>
          </div>
          <button
            type="button"
            onClick={() => handleOpenChange(false)}
            className="bg-primary text-primary-foreground hover:bg-primary/90 h-9 rounded-md px-4 text-sm font-medium"
          >
            {addedTotal > 0 ? `Concluir (${addedTotal})` : 'Fechar'}
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
