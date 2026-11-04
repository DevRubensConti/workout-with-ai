'use client';

import { useEffect, useState } from 'react';
import { Trophy, TrendingUp } from 'lucide-react';
import { ApiError, apiFetch } from '@/lib/api';
import { Button } from '@/components/ui/button';
import {
  formatProgressDate,
  formatSetLog,
  type ExerciseProgress as Progress,
} from '@/lib/sessions';
import { formatWeight } from '@/lib/workouts';

export function ExerciseProgress({
  collapsible = false,
  ...props
}: {
  exerciseId: string;
  currentWeightKg?: number | null;
  collapsible?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  if (!collapsible) return <ExerciseProgressContent {...props} />;
  return (
    <div className="space-y-3">
      <Button
        variant="outline"
        className="w-full"
        aria-expanded={expanded}
        onClick={() => setExpanded((value) => !value)}
      >
        <TrendingUp />{' '}
        {expanded ? 'Ocultar evolução' : 'Ver evolução e recordes'}
      </Button>
      {expanded && <ExerciseProgressContent {...props} />}
    </div>
  );
}

function ExerciseProgressContent({
  exerciseId,
  currentWeightKg,
}: {
  exerciseId: string;
  currentWeightKg?: number | null;
}) {
  const [page, setPage] = useState(1);
  const [retry, setRetry] = useState(0);
  const [state, setState] = useState<{
    key: string;
    data?: Progress;
    error?: string;
  } | null>(null);
  const key = `${exerciseId}:${page}:${retry}`;
  useEffect(() => {
    const controller = new AbortController();
    apiFetch<Progress>(
      `/sessions/progress/exercises/${exerciseId}?page=${page}&page_size=20`,
      { signal: controller.signal, cache: 'no-store' }
    )
      .then((data) => {
        if (!controller.signal.aborted) setState({ key, data });
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted)
          setState({
            key,
            error:
              error instanceof ApiError
                ? error.message
                : 'Não foi possível carregar a evolução.',
          });
      });
    return () => controller.abort();
  }, [exerciseId, page, key]);
  const current = state?.key === key;
  const data = current ? state.data : undefined;
  const points =
    data?.points
      .slice()
      .reverse()
      .filter((point) => point.max_weight_kg !== null) ?? [];
  const max = Math.max(1, ...points.map((point) => point.max_weight_kg ?? 0));
  const coords = points.map(
    (point, index) =>
      `${points.length === 1 ? 150 : 10 + (index * 280) / (points.length - 1)},${90 - ((point.max_weight_kg ?? 0) * 75) / max}`
  );
  return (
    <section
      aria-label="Evolução pessoal do exercício"
      className="bg-data-surface rounded-2xl border p-4"
    >
      <h3 className="flex items-center gap-2 text-sm font-semibold">
        <TrendingUp className="text-data size-4" /> Sua evolução neste exercício
      </h3>
      {!current ? (
        <p role="status" className="text-muted-foreground mt-3 text-sm">
          Carregando histórico…
        </p>
      ) : state.error ? (
        <div role="alert" className="mt-3">
          <p className="text-destructive text-sm">{state.error}</p>
          <Button
            variant="outline"
            className="mt-2"
            onClick={() => setRetry((value) => value + 1)}
          >
            Tentar novamente
          </Button>
        </div>
      ) : (
        data && (
          <>
            <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm">
                <Trophy className="text-primary mr-1 inline size-4" /> Recorde:{' '}
                <strong className="text-data">
                  {data.personal_record_kg === null
                    ? 'Sem carga registrada'
                    : formatWeight(data.personal_record_kg)}
                </strong>
              </p>
              <span className="text-muted-foreground text-xs">
                {data.completed_sessions} sessões com séries realizadas
              </span>
            </div>
            {data.personal_record_at && (
              <p className="text-muted-foreground mt-1 text-xs">
                Alcançado em {formatProgressDate(data.personal_record_at)}
              </p>
            )}
            {currentWeightKg !== null &&
              currentWeightKg !== undefined &&
              (data.personal_record_kg === null ||
                currentWeightKg > data.personal_record_kg) && (
                <p
                  role="status"
                  className="bg-accent text-accent-foreground mt-3 rounded-xl p-3 text-sm"
                >
                  Maior carga informada neste treino:{' '}
                  <strong>{formatWeight(currentWeightKg)}</strong>.
                  {data.personal_record_kg !== null
                    ? ' Supera seu recorde anterior.'
                    : ' Será seu primeiro registro de carga.'}{' '}
                  O recorde será confirmado ao finalizar o treino.
                </p>
              )}
            {points.length > 0 && (
              <figure className="bg-card mt-4 rounded-xl p-3">
                <svg
                  viewBox="0 0 300 105"
                  className="h-28 w-full"
                  role="img"
                  aria-label="Evolução da maior carga por sessão, da mais antiga para a mais recente nesta página"
                >
                  <line
                    x1="10"
                    y1="90"
                    x2="290"
                    y2="90"
                    stroke="currentColor"
                    opacity=".15"
                  />
                  <polyline
                    points={coords.join(' ')}
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    className="text-data"
                  />
                  {coords.map((coord, index) => {
                    const [x, y] = coord.split(',');
                    return (
                      <circle
                        key={points[index].session_id}
                        cx={x}
                        cy={y}
                        r="3"
                        fill="currentColor"
                        className="text-data"
                      >
                        <title>
                          {formatProgressDate(points[index].performed_at)}:{' '}
                          {formatWeight(points[index].max_weight_kg ?? 0)}
                        </title>
                      </circle>
                    );
                  })}
                </svg>
                <figcaption className="text-muted-foreground text-xs">
                  Maior carga por sessão · os valores completos estão abaixo.
                </figcaption>
              </figure>
            )}
            <p className="text-muted-foreground mt-3 text-xs">
              Compare apenas o mesmo equipamento e execução. Recordes não são
              uma recomendação para aumentar a carga.
            </p>
            {data.points.length === 0 ? (
              <p className="text-muted-foreground mt-3 text-sm">
                Finalize um treino com séries realizadas para iniciar seu
                histórico.
              </p>
            ) : (
              <details className="mt-3">
                <summary className="cursor-pointer text-sm font-medium">
                  Cargas e datas das sessões
                </summary>
                <ul className="mt-2 max-h-56 space-y-3 overflow-y-auto">
                  {data.points.map((point) => (
                    <li
                      key={point.session_id}
                      className="border-t pt-2 text-xs"
                    >
                      <p className="font-medium">
                        {formatProgressDate(point.performed_at)} ·{' '}
                        {point.max_weight_kg === null
                          ? 'Sem carga externa registrada'
                          : formatWeight(point.max_weight_kg)}
                      </p>
                      <p className="text-muted-foreground mt-1">
                        {point.sets
                          .map(
                            (set) => `${set.set_number}: ${formatSetLog(set)}`
                          )
                          .join(' · ')}
                      </p>
                    </li>
                  ))}
                </ul>
              </details>
            )}
            {data.total_pages > 1 && (
              <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  disabled={page <= 1}
                  onClick={() => setPage(page - 1)}
                >
                  Mais recentes
                </Button>
                <span className="text-muted-foreground text-xs">
                  {page}/{data.total_pages}
                </span>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={page >= data.total_pages}
                  onClick={() => setPage(page + 1)}
                >
                  Mais antigas
                </Button>
              </div>
            )}
          </>
        )
      )}
    </section>
  );
}
