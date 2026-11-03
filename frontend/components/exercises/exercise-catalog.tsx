'use client';

import {
  ChevronLeft,
  ChevronRight,
  Dumbbell,
  SearchX,
  Search,
  X,
} from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';

import {
  ExerciseCard,
  ExerciseCardSkeleton,
} from '@/components/exercises/exercise-card';
import { ExerciseDetailDialog } from '@/components/exercises/exercise-detail-dialog';
import { Input } from '@/components/ui/input';
import { ApiError, apiFetch } from '@/lib/api';
import {
  equipmentLabel,
  muscleLabel,
  type ExerciseCatalogResponse,
  type ExerciseDetail,
  type ExerciseFilters,
  type ExerciseLocale,
} from '@/lib/exercises';
import { cn } from '@/lib/utils';

interface RequestState<T> {
  key: string;
  data?: T;
  error?: string;
}

const PAGE_SIZE = 24;
const SKELETON_COUNT = 8;

const LOCALES: { value: ExerciseLocale; label: string }[] = [
  { value: 'pt-BR', label: 'PT' },
  { value: 'en', label: 'EN' },
];

function errorMessage(error: unknown) {
  return error instanceof ApiError
    ? error.message
    : 'Não foi possível carregar os dados. Tente novamente.';
}

export function ExerciseCatalog() {
  const [locale, setLocale] = useState<ExerciseLocale>('pt-BR');
  const [searchInput, setSearchInput] = useState('');
  const [query, setQuery] = useState('');
  const [muscleGroup, setMuscleGroup] = useState('');
  const [equipment, setEquipment] = useState('');
  const [page, setPage] = useState(1);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [listRetry, setListRetry] = useState(0);
  const [detailRetry, setDetailRetry] = useState(0);
  const [listState, setListState] =
    useState<RequestState<ExerciseCatalogResponse> | null>(null);
  const [detailState, setDetailState] =
    useState<RequestState<ExerciseDetail> | null>(null);
  // Os filtros ficam guardados para não sumirem enquanto uma nova página carrega.
  const [filters, setFilters] = useState<ExerciseFilters | null>(null);
  const resultsTop = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      setQuery(searchInput.trim());
      setPage(1);
    }, 300);
    return () => window.clearTimeout(timeout);
  }, [searchInput]);

  const listUrl = useMemo(() => {
    const params = new URLSearchParams({
      locale,
      page: String(page),
      page_size: String(PAGE_SIZE),
    });
    if (query) params.set('q', query);
    if (muscleGroup) params.set('muscle_group', muscleGroup);
    if (equipment) params.set('equipment', equipment);
    return `/exercises?${params.toString()}`;
  }, [equipment, locale, muscleGroup, page, query]);
  const listRequestKey = `${listUrl}:${listRetry}`;

  useEffect(() => {
    const controller = new AbortController();
    apiFetch<ExerciseCatalogResponse>(listUrl, {
      cache: 'no-store',
      signal: controller.signal,
    })
      .then((data) => {
        if (controller.signal.aborted) return;
        setListState({ key: listRequestKey, data });
        setFilters(data.filters);
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setListState({ key: listRequestKey, error: errorMessage(error) });
      });

    return () => controller.abort();
  }, [listRequestKey, listUrl]);

  const detailUrl = selectedId
    ? `/exercises/${encodeURIComponent(selectedId)}?locale=${locale}`
    : '';
  const detailRequestKey = `${detailUrl}:${detailRetry}`;

  useEffect(() => {
    if (!detailUrl) return;

    const controller = new AbortController();
    apiFetch<ExerciseDetail>(detailUrl, {
      cache: 'no-store',
      signal: controller.signal,
    })
      .then((data) => {
        if (controller.signal.aborted) return;
        setDetailState({ key: detailRequestKey, data });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setDetailState({ key: detailRequestKey, error: errorMessage(error) });
      });

    return () => controller.abort();
  }, [detailRequestKey, detailUrl]);

  const listCurrent = listState?.key === listRequestKey;
  const listLoading = !listCurrent;
  const listError = listCurrent ? listState.error : undefined;
  // Mantém o resultado anterior visível (esmaecido) durante a troca de página/filtro.
  const listData = listError ? undefined : listState?.data;
  const items = listData?.items ?? [];
  const firstLoad = listState === null;

  const detailCurrent = detailState?.key === detailRequestKey;
  const detailData = detailCurrent ? detailState.data : undefined;
  const detailError = detailCurrent ? detailState.error : undefined;
  const detailLoading = Boolean(selectedId) && !detailCurrent;

  const selectedIndex = items.findIndex((item) => item.id === selectedId);
  const selectedSummary = selectedIndex >= 0 ? items[selectedIndex] : undefined;
  const hasActiveFilters = Boolean(searchInput || muscleGroup || equipment);

  function changeMuscleGroup(value: string) {
    setMuscleGroup(value);
    setPage(1);
  }

  function changeEquipment(value: string) {
    setEquipment(value);
    setPage(1);
  }

  function clearFilters() {
    setSearchInput('');
    setQuery('');
    setMuscleGroup('');
    setEquipment('');
    setPage(1);
  }

  function goToPage(next: number) {
    setPage(next);
    resultsTop.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  const totalLabel = listData
    ? `${listData.total.toLocaleString('pt-BR')} ${
        listData.total === 1 ? 'exercício' : 'exercícios'
      }`
    : 'Carregando exercícios…';

  return (
    <div className="pb-12">
      <section className="from-primary/10 via-background to-background border-b bg-gradient-to-b">
        <div className="container mx-auto max-w-7xl px-4 py-8 md:px-6 md:py-10">
          <div className="flex items-center gap-4">
            <span className="bg-primary text-primary-foreground flex size-12 shrink-0 items-center justify-center rounded-2xl shadow-sm">
              <Dumbbell className="size-6" />
            </span>
            <div>
              <h1 className="text-2xl font-bold tracking-tight md:text-3xl">
                Catálogo de exercícios
              </h1>
              <p className="text-muted-foreground mt-1 text-sm md:text-base">
                Encontre o exercício certo e veja como executá-lo, passo a
                passo.
              </p>
            </div>
          </div>
        </div>
      </section>

      <div className="bg-background/90 sticky top-16 z-30 border-b backdrop-blur">
        <div className="container mx-auto max-w-7xl space-y-3 px-4 py-3 md:px-6">
          <div className="flex flex-col gap-3 md:flex-row md:items-center">
            <div className="relative flex-1">
              <Search className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2" />
              <Input
                value={searchInput}
                onChange={(event) => setSearchInput(event.target.value)}
                placeholder="Buscar por nome, ex.: agachamento, rosca, remada…"
                aria-label="Buscar exercício"
                className="h-11 rounded-xl pr-10 pl-10 text-base"
              />
              {searchInput && (
                <button
                  type="button"
                  onClick={() => setSearchInput('')}
                  aria-label="Limpar busca"
                  className="text-muted-foreground hover:text-foreground absolute top-1/2 right-3 -translate-y-1/2"
                >
                  <X className="size-4" />
                </button>
              )}
            </div>

            <div className="flex items-center gap-3">
              <select
                value={equipment}
                onChange={(event) => changeEquipment(event.target.value)}
                aria-label="Equipamento"
                className="border-input bg-background focus-visible:border-ring focus-visible:ring-ring/50 h-11 min-w-0 flex-1 rounded-xl border px-3 text-sm outline-none focus-visible:ring-[3px] md:w-52 md:flex-none"
              >
                <option value="">Todos os equipamentos</option>
                {(filters?.equipment ?? []).map((value) => (
                  <option key={value} value={value}>
                    {equipmentLabel(value)}
                  </option>
                ))}
              </select>

              <div
                role="group"
                aria-label="Idioma do conteúdo"
                className="bg-muted flex shrink-0 rounded-xl p-1"
              >
                {LOCALES.map((option) => (
                  <button
                    type="button"
                    key={option.value}
                    aria-pressed={locale === option.value}
                    onClick={() => {
                      setLocale(option.value);
                      setPage(1);
                    }}
                    className={cn(
                      'h-9 rounded-lg px-3 text-sm font-medium transition-colors',
                      locale === option.value
                        ? 'bg-background text-foreground shadow-sm'
                        : 'text-muted-foreground hover:text-foreground'
                    )}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div
            role="group"
            aria-label="Grupo muscular"
            className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 md:mx-0 md:flex-wrap md:px-0 [&::-webkit-scrollbar]:hidden"
          >
            {[
              { value: '', label: 'Todos' },
              ...(filters?.muscle_groups ?? []).map((value) => ({
                value,
                label: muscleLabel(value),
              })),
            ].map((chip) => (
              <button
                type="button"
                key={chip.value || 'all'}
                aria-pressed={muscleGroup === chip.value}
                onClick={() => changeMuscleGroup(chip.value)}
                className={cn(
                  'shrink-0 rounded-full border px-3.5 py-1.5 text-sm font-medium whitespace-nowrap transition-colors',
                  muscleGroup === chip.value
                    ? 'bg-primary text-primary-foreground border-primary'
                    : 'bg-card text-muted-foreground hover:text-foreground hover:border-foreground/30'
                )}
              >
                {chip.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div
        ref={resultsTop}
        className="container mx-auto max-w-7xl scroll-mt-52 px-4 pt-6 md:px-6"
      >
        <div className="mb-4 flex min-h-8 items-center justify-between gap-3">
          <p className="text-muted-foreground text-sm" aria-live="polite">
            <span className="text-foreground font-semibold">{totalLabel}</span>
            {query && listData ? ` para “${query}”` : ''}
          </p>
          {hasActiveFilters && (
            <button
              type="button"
              onClick={clearFilters}
              className="text-primary inline-flex items-center gap-1 text-sm font-medium hover:underline"
            >
              <X className="size-3.5" /> Limpar filtros
            </button>
          )}
        </div>

        {listError ? (
          <div
            role="alert"
            className="bg-card flex flex-col items-center gap-3 rounded-xl border px-6 py-12 text-center"
          >
            <p className="text-destructive text-sm">{listError}</p>
            <button
              type="button"
              onClick={() => setListRetry((value) => value + 1)}
              className="bg-primary text-primary-foreground hover:bg-primary/90 h-9 rounded-md px-4 text-sm font-medium"
            >
              Tentar novamente
            </button>
          </div>
        ) : firstLoad ? (
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {Array.from({ length: SKELETON_COUNT }, (_, index) => (
              <ExerciseCardSkeleton key={index} />
            ))}
          </div>
        ) : items.length === 0 && !listLoading ? (
          <div className="bg-card flex flex-col items-center gap-3 rounded-xl border px-6 py-16 text-center">
            <SearchX className="text-muted-foreground size-10" />
            <p className="font-semibold">Nenhum exercício encontrado</p>
            <p className="text-muted-foreground max-w-sm text-sm">
              Tente outro nome, mude o grupo muscular ou remova algum filtro.
            </p>
            {hasActiveFilters && (
              <button
                type="button"
                onClick={clearFilters}
                className="text-primary text-sm font-medium hover:underline"
              >
                Limpar filtros
              </button>
            )}
          </div>
        ) : (
          <div
            aria-busy={listLoading}
            className={cn(
              'grid gap-5 transition-opacity sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4',
              listLoading && 'pointer-events-none opacity-50'
            )}
          >
            {items.map((exercise) => (
              <ExerciseCard
                key={exercise.id}
                exercise={exercise}
                onSelect={setSelectedId}
              />
            ))}
          </div>
        )}

        {listData && listData.total_pages > 1 && !listError && (
          <nav
            aria-label="Paginação do catálogo"
            className="mt-8 flex items-center justify-between gap-3"
          >
            <button
              type="button"
              disabled={listData.page <= 1 || listLoading}
              onClick={() => goToPage(listData.page - 1)}
              className="hover:bg-accent inline-flex h-10 items-center gap-1 rounded-lg border px-4 text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-40"
            >
              <ChevronLeft className="size-4" /> Anterior
            </button>
            <span className="text-muted-foreground text-sm">
              Página{' '}
              <span className="text-foreground font-semibold">
                {listData.page}
              </span>{' '}
              de {listData.total_pages}
            </span>
            <button
              type="button"
              disabled={listData.page >= listData.total_pages || listLoading}
              onClick={() => goToPage(listData.page + 1)}
              className="hover:bg-accent inline-flex h-10 items-center gap-1 rounded-lg border px-4 text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-40"
            >
              Próxima <ChevronRight className="size-4" />
            </button>
          </nav>
        )}
      </div>

      <ExerciseDetailDialog
        summary={selectedSummary}
        detail={detailData}
        loading={detailLoading}
        error={detailError}
        locale={locale}
        onRetry={() => setDetailRetry((value) => value + 1)}
        onClose={() => setSelectedId(null)}
        onPrevious={
          selectedIndex > 0
            ? () => setSelectedId(items[selectedIndex - 1].id)
            : undefined
        }
        onNext={
          selectedIndex >= 0 && selectedIndex < items.length - 1
            ? () => setSelectedId(items[selectedIndex + 1].id)
            : undefined
        }
      />
    </div>
  );
}
