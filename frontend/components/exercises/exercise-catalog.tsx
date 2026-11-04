'use client';

import {
  ChevronLeft,
  ChevronRight,
  CheckCheck,
  Dumbbell,
  Loader2,
  SlidersHorizontal,
  Sparkles,
  SearchX,
  Search,
  X,
  XCircle,
} from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';

import {
  ExerciseCard,
  ExerciseCardSkeleton,
} from '@/components/exercises/exercise-card';
import { ExerciseDetailDialog } from '@/components/exercises/exercise-detail-dialog';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog';
import { ApiError, apiFetch } from '@/lib/api';
import {
  equipmentLabel,
  categoryLabel,
  forceLabel,
  levelLabel,
  mechanicLabel,
  muscleLabel,
  type ExerciseCatalogResponse,
  type ExerciseDetail,
  type ExerciseFilters,
  type ExerciseLocale,
} from '@/lib/exercises';
import { cn } from '@/lib/utils';
import { useAuth } from '@/components/auth-provider';
import { toast } from 'sonner';

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
  const user = useAuth();
  const canChoose = user.permissions.includes('workouts:write');
  const [savingIds, setSavingIds] = useState<Set<string>>(new Set());
  const [availability, setAvailability] = useState('');
  const [locale, setLocale] = useState<ExerciseLocale>('pt-BR');
  const [searchInput, setSearchInput] = useState('');
  const [query, setQuery] = useState('');
  const [muscleGroup, setMuscleGroup] = useState('');
  const [equipment, setEquipment] = useState('');
  const [level, setLevel] = useState('');
  const [category, setCategory] = useState('');
  const [mechanic, setMechanic] = useState('');
  const [force, setForce] = useState('');
  const [bulkSaving, setBulkSaving] = useState(false);
  const [pendingBulk, setPendingBulk] = useState<{
    enabled: boolean;
    params: string;
    total: number;
    labels: string[];
  } | null>(null);
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
  const filterDetails = useRef<HTMLDetailsElement>(null);

  useEffect(() => {
    if (filterDetails.current) {
      filterDetails.current.open =
        window.matchMedia('(min-width: 768px)').matches;
    }
  }, []);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      setQuery(searchInput.trim());
      setPage(1);
    }, 300);
    return () => window.clearTimeout(timeout);
  }, [searchInput]);

  const filterParams = useMemo(() => {
    const params = new URLSearchParams({ locale });
    if (query) params.set('q', query);
    if (muscleGroup) params.set('muscle_group', muscleGroup);
    if (equipment) params.set('equipment', equipment);
    if (availability) params.set('enabled_for_ai', availability);
    if (level) params.set('level', level);
    if (category) params.set('category', category);
    if (mechanic) params.set('mechanic', mechanic);
    if (force) params.set('force', force);
    return params.toString();
  }, [
    availability,
    category,
    equipment,
    force,
    level,
    locale,
    mechanic,
    muscleGroup,
    query,
  ]);
  const listUrl = `/exercises?${filterParams}&page=${page}&page_size=${PAGE_SIZE}`;
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
        if (data.page > Math.max(1, data.total_pages)) {
          setPage(Math.max(1, data.total_pages));
        }
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
  const filterControls = [
    {
      key: 'equipment',
      label: 'Equipamento',
      value: equipment,
      set: setEquipment,
      options: filters?.equipment ?? [],
      format: equipmentLabel,
    },
    {
      key: 'level',
      label: 'Nível',
      value: level,
      set: setLevel,
      options: filters?.levels ?? [],
      format: levelLabel,
    },
    {
      key: 'category',
      label: 'Categoria',
      value: category,
      set: setCategory,
      options: filters?.categories ?? [],
      format: categoryLabel,
    },
    {
      key: 'mechanic',
      label: 'Mecânica',
      value: mechanic,
      set: setMechanic,
      options: filters?.mechanics ?? [],
      format: mechanicLabel,
    },
    {
      key: 'force',
      label: 'Tipo de força',
      value: force,
      set: setForce,
      options: filters?.forces ?? [],
      format: forceLabel,
    },
    {
      key: 'availability',
      label: 'Disponibilidade para IA',
      value: availability,
      set: setAvailability,
      options: ['true', 'false'],
      format: (value: string) =>
        value === 'true' ? 'Habilitados' : 'Desabilitados',
    },
  ];
  const activeFilters = [
    ...(query
      ? [
          {
            key: 'query',
            label: `Busca: ${query}`,
            clear: () => {
              setSearchInput('');
              setQuery('');
            },
          },
        ]
      : []),
    ...(muscleGroup
      ? [
          {
            key: 'muscle',
            label: muscleLabel(muscleGroup),
            clear: () => setMuscleGroup(''),
          },
        ]
      : []),
    ...filterControls
      .filter((filter) => filter.value)
      .map((filter) => ({
        key: filter.key,
        label: `${filter.label}: ${filter.format(filter.value)}`,
        clear: () => filter.set(''),
      })),
  ];
  const hasActiveFilters = Boolean(searchInput || activeFilters.length);
  const mutationBusy = bulkSaving || savingIds.size > 0;
  const bulkDisabled =
    mutationBusy ||
    listLoading ||
    !listData?.total ||
    searchInput.trim() !== query;

  async function changeAvailability(id: string, enabled: boolean) {
    setSavingIds((current) => new Set(current).add(id));
    try {
      await apiFetch(`/exercises/${id}/ai-availability`, {
        method: 'PUT',
        body: { enabled },
      });
      if (availability && items.length === 1 && page > 1) setPage(page - 1);
      setListRetry((value) => value + 1);
      setDetailRetry((value) => value + 1);
      toast.success(
        enabled
          ? 'Exercício habilitado para a IA.'
          : 'Exercício desabilitado para a IA.'
      );
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setSavingIds((current) => {
        const next = new Set(current);
        next.delete(id);
        return next;
      });
    }
  }

  function changeMuscleGroup(value: string) {
    setMuscleGroup(value);
    setPage(1);
  }

  function clearFilters() {
    setSearchInput('');
    setQuery('');
    setMuscleGroup('');
    setEquipment('');
    setAvailability('');
    setLevel('');
    setCategory('');
    setMechanic('');
    setForce('');
    setPage(1);
  }

  async function changeFilteredAvailability() {
    if (!pendingBulk || mutationBusy) return;
    setBulkSaving(true);
    try {
      const result = await apiFetch<{ matched: number; updated: number }>(
        `/exercises/ai-availability?${pendingBulk.params}`,
        { method: 'PUT', body: { enabled: pendingBulk.enabled } }
      );
      setPendingBulk(null);
      setPage(1);
      setListRetry((value) => value + 1);
      setDetailRetry((value) => value + 1);
      const action = pendingBulk.enabled ? 'habilitado' : 'desabilitado';
      const plural = result.updated !== 1;
      toast.success(
        result.updated === 0
          ? 'Nenhuma alteração necessária.'
          : `${result.updated.toLocaleString('pt-BR')} ${
              plural ? 'exercícios' : 'exercício'
            } ${action}${plural ? 's' : ''} para a IA.`,
        {
          description: `${result.matched.toLocaleString('pt-BR')} ${
            result.matched === 1
              ? 'resultado corresponde'
              : 'resultados correspondem'
          } aos filtros aplicados.`,
        }
      );
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setBulkSaving(false);
    }
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
    <div className="bg-muted/20 min-w-0 pb-8 md:pb-12">
      <section className="from-primary/10 via-background to-background border-b bg-gradient-to-br">
        <div className="container mx-auto max-w-7xl px-4 py-8 md:px-6 md:py-10">
          <div className="flex items-center gap-4">
            <span className="bg-primary text-primary-foreground flex size-12 shrink-0 items-center justify-center rounded-2xl shadow-sm">
              <Dumbbell className="size-6" />
            </span>
            <div className="max-w-3xl">
              <p className="text-primary mb-2 flex items-center gap-1.5 text-xs font-semibold tracking-widest uppercase">
                <Sparkles className="size-3.5" /> Seu repertório de treino
              </p>
              <h1 className="text-2xl font-bold tracking-tight md:text-3xl">
                Catálogo de exercícios
              </h1>
              <p className="text-muted-foreground mt-1 text-sm md:text-base">
                Explore os movimentos e escolha o que a IA pode usar nos seus
                treinos.
              </p>
              <p className="text-muted-foreground mt-2 text-sm">
                Suas escolhas são pessoais e salvas automaticamente. Todos
                começam habilitados; desativar não altera treinos salvos nem
                impede a inclusão manual.
              </p>
            </div>
          </div>
        </div>
      </section>

      <fieldset disabled={bulkSaving} className="bg-background border-b">
        <legend className="sr-only">Busca e grupo muscular</legend>
        <div className="container mx-auto max-w-7xl space-y-4 px-4 py-5 md:px-6">
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
                  className="text-muted-foreground hover:text-foreground absolute top-1/2 right-0 flex size-11 -translate-y-1/2 items-center justify-center"
                >
                  <X className="size-4" />
                </button>
              )}
            </div>

            <div className="flex items-center gap-3">
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
                  'min-h-11 shrink-0 rounded-full border px-3.5 py-1.5 text-sm font-medium whitespace-nowrap transition-colors md:min-h-0',
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
      </fieldset>

      <div
        ref={resultsTop}
        className="container mx-auto max-w-7xl scroll-mt-24 px-4 pt-6 md:px-6"
      >
        <details
          ref={filterDetails}
          className="bg-card mb-5 rounded-2xl border shadow-sm"
        >
          <summary className="focus-visible:ring-ring flex cursor-pointer list-none items-center gap-2 rounded-2xl p-4 text-sm font-semibold outline-none focus-visible:ring-2 [&::-webkit-details-marker]:hidden">
            <SlidersHorizontal className="text-primary size-4" />
            Refinar catálogo
            {activeFilters.length > 0 && (
              <span className="bg-accent text-accent-foreground rounded-full px-2 py-0.5 text-xs">
                {activeFilters.length} ativo(s)
              </span>
            )}
            <ChevronRight className="text-muted-foreground ml-auto size-4 in-open:rotate-90" />
          </summary>
          <fieldset
            disabled={bulkSaving}
            className="grid grid-cols-2 gap-3 border-t p-4 lg:grid-cols-3 xl:grid-cols-6"
          >
            <legend className="sr-only">Filtros do catálogo</legend>
            {filterControls.map((filter) => (
              <label key={filter.key} className="flex min-w-0 flex-col gap-2">
                <span className="text-muted-foreground text-xs font-medium">
                  {filter.label}
                </span>
                <select
                  value={filter.value}
                  onChange={(event) => {
                    filter.set(event.target.value);
                    setPage(1);
                  }}
                  className={cn(
                    'border-input bg-elevated focus-visible:border-ring focus-visible:ring-ring/50 h-10 w-full min-w-0 rounded-lg border px-2 text-sm outline-none focus-visible:ring-[3px]',
                    filter.value && 'border-primary/40 bg-accent'
                  )}
                >
                  <option value="">Todos</option>
                  {filter.options.map((value) => (
                    <option key={value} value={value}>
                      {filter.format(value)}
                    </option>
                  ))}
                </select>
              </label>
            ))}
          </fieldset>
        </details>

        {activeFilters.length > 0 && (
          <div
            className="mb-5 flex flex-wrap items-center gap-2"
            aria-label="Filtros ativos"
          >
            {activeFilters.map((filter) => (
              <button
                key={filter.key}
                type="button"
                disabled={bulkSaving}
                onClick={() => {
                  filter.clear();
                  setPage(1);
                }}
                aria-label={`Remover filtro ${filter.label}`}
                className="bg-background text-muted-foreground hover:border-primary/40 hover:text-foreground inline-flex max-w-full items-center gap-1.5 rounded-full border px-3 py-1 text-xs transition-colors disabled:opacity-50"
              >
                <span className="truncate">{filter.label}</span>
                <X className="size-3 shrink-0" />
              </button>
            ))}
          </div>
        )}

        <div className="mb-5 flex min-h-8 flex-wrap items-center justify-between gap-3">
          <p className="text-muted-foreground text-sm" aria-live="polite">
            <span className="text-foreground font-semibold">{totalLabel}</span>
            {query && listData ? ` para “${query}”` : ''}
          </p>
          {hasActiveFilters && (
            <button
              type="button"
              onClick={clearFilters}
              disabled={bulkSaving}
              className="text-primary inline-flex items-center gap-1 text-sm font-medium hover:underline"
            >
              <X className="size-3.5" /> Limpar filtros
            </button>
          )}
        </div>

        {canChoose && (
          <section
            aria-label="Seleção em lote para IA"
            className="bg-card mb-6 flex flex-col gap-4 rounded-2xl border p-4 shadow-sm md:flex-row md:items-center md:justify-between"
          >
            <div className="flex items-start gap-3">
              <span className="bg-primary/10 text-primary flex size-10 shrink-0 items-center justify-center rounded-xl">
                {bulkSaving ? (
                  <Loader2 className="size-5 animate-spin" />
                ) : (
                  <CheckCheck className="size-5" />
                )}
              </span>
              <div>
                <h2 className="text-sm font-semibold">Sua seleção para a IA</h2>
                <p className="text-muted-foreground mt-1 text-xs leading-relaxed">
                  Aplique aos {listData?.total.toLocaleString('pt-BR') ?? '…'}{' '}
                  resultados dos filtros, em todas as páginas.
                </p>
              </div>
            </div>
            <div className="grid shrink-0 gap-2 min-[400px]:grid-cols-2 md:grid-cols-2">
              <Button
                variant="outline"
                disabled={bulkDisabled}
                onClick={() =>
                  setPendingBulk({
                    enabled: true,
                    params: filterParams,
                    total: listData?.total ?? 0,
                    labels: activeFilters.map((filter) => filter.label),
                  })
                }
              >
                <CheckCheck className="size-4" /> Habilitar todos
              </Button>
              <Button
                variant="outline"
                disabled={bulkDisabled}
                onClick={() =>
                  setPendingBulk({
                    enabled: false,
                    params: filterParams,
                    total: listData?.total ?? 0,
                    labels: activeFilters.map((filter) => filter.label),
                  })
                }
              >
                <XCircle className="size-4" /> Desabilitar todos
              </Button>
            </div>
          </section>
        )}

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
              <div key={exercise.id} className="flex flex-col gap-2">
                <ExerciseCard exercise={exercise} onSelect={setSelectedId} />
                {canChoose && (
                  <label
                    className={cn(
                      'flex min-h-11 cursor-pointer items-center gap-2 rounded-xl border px-3 py-2.5 text-xs font-medium transition-colors',
                      exercise.enabled_for_ai
                        ? 'border-primary/20 bg-primary/5 text-primary'
                        : 'bg-card text-muted-foreground'
                    )}
                  >
                    <input
                      type="checkbox"
                      checked={exercise.enabled_for_ai}
                      disabled={
                        savingIds.has(exercise.id) || listLoading || bulkSaving
                      }
                      className="accent-primary size-4 shrink-0"
                      onChange={(event) =>
                        changeAvailability(exercise.id, event.target.checked)
                      }
                    />
                    {exercise.enabled_for_ai
                      ? 'Habilitado para IA'
                      : 'Desabilitado para IA'}
                    <span className="sr-only">: {exercise.name}</span>
                    {savingIds.has(exercise.id) && (
                      <Loader2
                        aria-label="Salvando"
                        role="status"
                        className="ml-auto size-3.5 animate-spin"
                      />
                    )}
                  </label>
                )}
              </div>
            ))}
          </div>
        )}

        {listData && listData.total_pages > 1 && !listError && (
          <nav
            aria-label="Paginação do catálogo"
            className="mt-8 grid grid-cols-[auto_1fr_auto] items-center gap-2"
          >
            <button
              type="button"
              disabled={listData.page <= 1 || listLoading || bulkSaving}
              onClick={() => goToPage(listData.page - 1)}
              className="hover:bg-accent inline-flex h-10 items-center gap-1 rounded-lg border px-4 text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-40"
            >
              <ChevronLeft className="size-4" />{' '}
              <span className="sr-only sm:not-sr-only">Anterior</span>
            </button>
            <span className="text-muted-foreground text-center text-sm">
              Página{' '}
              <span className="text-foreground font-semibold">
                {listData.page}
              </span>{' '}
              de {listData.total_pages}
            </span>
            <button
              type="button"
              disabled={
                listData.page >= listData.total_pages ||
                listLoading ||
                bulkSaving
              }
              onClick={() => goToPage(listData.page + 1)}
              className="hover:bg-accent inline-flex h-10 items-center gap-1 rounded-lg border px-4 text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-40"
            >
              <span className="sr-only sm:not-sr-only">Próxima</span>{' '}
              <ChevronRight className="size-4" />
            </button>
          </nav>
        )}
      </div>

      <Dialog
        open={pendingBulk !== null}
        onOpenChange={(open) => {
          if (!open && !bulkSaving) setPendingBulk(null);
        }}
      >
        <DialogContent className="max-w-lg p-6">
          <span className="bg-primary/10 text-primary mb-4 flex size-12 items-center justify-center rounded-2xl">
            <Sparkles className="size-6" />
          </span>
          <DialogTitle className="pr-6">
            {pendingBulk?.enabled ? 'Habilitar' : 'Desabilitar'} todos os
            resultados?
          </DialogTitle>
          <DialogDescription className="mt-3 leading-relaxed">
            A ação será aplicada a todos os exercícios que correspondem aos
            filtros no momento da confirmação, não apenas aos desta página. A
            consulta atual encontrou{' '}
            <strong>
              {pendingBulk?.total.toLocaleString('pt-BR')} exercícios
            </strong>
            .
          </DialogDescription>
          <div className="bg-muted/50 my-4 flex max-h-40 flex-wrap gap-2 overflow-y-auto rounded-xl p-3 text-xs">
            {pendingBulk?.labels.length ? (
              pendingBulk.labels.map((label) => (
                <span
                  key={label}
                  className="bg-elevated rounded-md border px-2 py-1"
                >
                  {label}
                </span>
              ))
            ) : (
              <span className="text-muted-foreground">
                Sem filtros: todo o seu catálogo acessível.
              </span>
            )}
          </div>
          <p className="text-muted-foreground text-xs leading-relaxed">
            A escolha afeta somente sua disponibilidade para próximos treinos
            com IA. Exercícios e treinos existentes serão preservados.
          </p>
          <div className="mt-6 flex justify-end gap-2">
            <Button
              variant="outline"
              disabled={bulkSaving}
              onClick={() => setPendingBulk(null)}
            >
              Cancelar
            </Button>
            <Button disabled={bulkSaving} onClick={changeFilteredAvailability}>
              {bulkSaving && <Loader2 className="size-4 animate-spin" />}
              {bulkSaving
                ? 'Salvando…'
                : pendingBulk?.enabled
                  ? 'Confirmar habilitação'
                  : 'Confirmar desabilitação'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

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
