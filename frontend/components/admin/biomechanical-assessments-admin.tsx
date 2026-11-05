'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';

import { AssessmentCorrectionForm } from '@/components/admin/assessment-correction-form';
import { ExerciseImageViewer } from '@/components/exercises/exercise-image-viewer';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ApiError, apiFetch } from '@/lib/api';
import { categoryLabel, muscleLabel } from '@/lib/exercises';
import {
  REVIEW_LABELS,
  type AssessmentDetail,
  type AssessmentList,
} from '@/lib/biomechanical-assessments';

const endpoint = '/biomechanical-assessments';
const fieldClass =
  'border-input bg-background w-full rounded-md border px-3 py-2 text-base md:text-sm';
const methodLabels = { manual: 'Manual', ai: 'IA', rule: 'Regra' };

function errorMessage(error: unknown) {
  return error instanceof ApiError
    ? error.message
    : 'Não foi possível concluir a operação.';
}

function AssessmentViewer({
  id,
  onReviewed,
  onCorrected,
}: {
  id: string;
  onReviewed: () => void;
  onCorrected: (detail: AssessmentDetail) => void;
}) {
  const [viewedId, setViewedId] = useState(id);
  const [editing, setEditing] = useState(false);
  const [detail, setDetail] = useState<AssessmentDetail | null>(null);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const [notes, setNotes] = useState('');
  const [decision, setDecision] = useState<'reviewed' | 'rejected'>('reviewed');
  const [saving, setSaving] = useState(false);
  const [reviewError, setReviewError] = useState('');
  const [conflict, setConflict] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    apiFetch<AssessmentDetail>(`${endpoint}/${viewedId}`, {
      signal: controller.signal,
      cache: 'no-store',
    })
      .then((data) => {
        if (!controller.signal.aborted) {
          setDetail(data);
          setError('');
          setConflict(false);
          setReviewError('');
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setError(errorMessage(error));
      });
    return () => controller.abort();
  }, [viewedId, retry]);

  function reload() {
    setDetail(null);
    setError('');
    setEditing(false);
    setRetry((value) => value + 1);
  }

  async function review(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!detail) return;
    if (
      !window.confirm(
        `Registrar como ${REVIEW_LABELS[decision].toLowerCase()}? A decisão não poderá ser editada nesta tela.`
      )
    )
      return;
    setSaving(true);
    setReviewError('');
    try {
      const saved = await apiFetch<AssessmentDetail>(
        `${endpoint}/${viewedId}/review`,
        {
          method: 'POST',
          body: { decision, notes, content_hash: detail.content_hash },
        }
      );
      setDetail(saved);
      setNotes('');
      toast.success('Revisão registrada.');
      onReviewed();
    } catch (error) {
      setReviewError(errorMessage(error));
      setConflict(error instanceof ApiError && error.status === 409);
    } finally {
      setSaving(false);
    }
  }

  if (error)
    return (
      <div role="alert" className="space-y-3">
        <p className="text-destructive">{error}</p>
        <Button variant="outline" onClick={reload}>
          Tentar novamente
        </Button>
      </div>
    );
  if (!detail) return <p role="status">Carregando avaliação…</p>;

  const definition = detail.scale.definition;
  const canAccept = detail.validation_errors.length === 0;
  return (
    <Card>
      <CardHeader>
        <CardTitle>{detail.exercise_name}</CardTitle>
        <p className="text-muted-foreground text-sm">
          {REVIEW_LABELS[detail.review_status]} · Escala v{detail.scale_version}
          {!detail.uses_current_scale &&
            ' — versão anterior aos critérios atuais'}
        </p>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="bg-muted relative h-48 w-full overflow-hidden rounded-xl sm:h-64">
          <ExerciseImageViewer
            images={detail.images}
            alt={detail.exercise_name}
            sizes="(min-width: 768px) 800px, 90vw"
          />
        </div>
        <dl className="space-y-2 text-sm">
          <dt className="font-medium">Identificador da avaliação</dt>
          <dd className="break-all">{detail.id}</dd>
          <dt className="font-medium">Identificador do exercício</dt>
          <dd className="break-all">{detail.exercise_id}</dd>
          <dt className="font-medium">Origem</dt>
          <dd className="break-words">
            {methodLabels[detail.assessment_method]} ·{' '}
            {detail.assessment_source}
          </dd>
          <dt className="font-medium">Cadastro</dt>
          <dd className="break-all">
            {new Date(detail.created_at).toLocaleString('pt-BR')} ·{' '}
            {detail.created_by ?? 'Cadastro externo / autor não disponível'}
          </dd>
          <dt className="font-medium">Execução considerada</dt>
          <dd className="whitespace-pre-wrap">{detail.execution_context}</dd>
        </dl>
        {detail.supersedes_id && (
          <Button
            variant="outline"
            disabled={saving || editing}
            onClick={() => {
              if (detail.supersedes_id) {
                setDetail(null);
                setError('');
                setNotes('');
                setViewedId(detail.supersedes_id);
              }
            }}
          >
            Consultar avaliação anterior
          </Button>
        )}
        {detail.validation_errors.length > 0 && (
          <div role="alert" className="text-destructive space-y-2">
            <p className="font-medium">
              Avaliação incompleta ou inválida — não pode ser marcada como
              revisada.
            </p>
            <ul className="list-disc pl-5">
              {detail.validation_errors.map((error) => (
                <li key={error}>{error}</li>
              ))}
            </ul>
          </div>
        )}
        <fieldset disabled={saving || conflict} className="min-w-0">
          <AssessmentCorrectionForm
            key={detail.id}
            detail={detail}
            onCancel={reload}
            onEditingChange={setEditing}
            onSaved={(saved) => {
              toast.success(
                'Nova avaliação pendente criada. A original foi preservada.'
              );
              onCorrected(saved);
            }}
          />
        </fieldset>
        <details className="space-y-4 rounded-md border p-4">
          <summary className="cursor-pointer font-medium">
            Critérios utilizados — versão {detail.scale_version}
          </summary>
          <p className="text-sm whitespace-pre-wrap">{definition.disclaimer}</p>
          {(
            [
              ['Condições de referência', definition.reference_conditions],
              ['Critérios de avaliação', definition.evaluation_criteria],
              ['Consistência e revisão', definition.consistency_rules],
              ['Não avaliado', definition.unassessed_guidance],
            ] as const
          ).map(([label, text]) => (
            <div key={label}>
              <h4 className="text-sm font-semibold">{label}</h4>
              <p className="text-sm whitespace-pre-wrap">{text}</p>
            </div>
          ))}
          {definition.scores.map((score) => (
            <p key={score.score} className="text-sm">
              <strong>
                {score.score} — {score.label}:{' '}
              </strong>
              {score.description}
            </p>
          ))}
          {[...definition.regions, ...definition.roles].map((item) => (
            <p key={item.code} className="text-sm">
              <strong>{item.label}: </strong>
              {item.description}
            </p>
          ))}
        </details>
        {detail.review ? (
          <section
            aria-label="Revisão registrada"
            className="space-y-2 border-t pt-4"
          >
            <h3 className="font-semibold">
              Revisão registrada: {REVIEW_LABELS[detail.review.decision]}
            </h3>
            <p className="text-muted-foreground text-sm break-all">
              {new Date(detail.review.reviewed_at).toLocaleString('pt-BR')} ·{' '}
              {detail.review.reviewed_by ?? 'Administrador removido'}
            </p>
            <p className="whitespace-pre-wrap">
              {detail.review.notes || 'Sem justificativa informada.'}
            </p>
            <p className="text-muted-foreground text-sm">
              Somente leitura. Correções devem ser cadastradas como uma nova
              avaliação.
            </p>
          </section>
        ) : (
          <form onSubmit={review} className="space-y-4 border-t pt-4">
            <h3 className="font-semibold">Registrar revisão administrativa</h3>
            {editing && (
              <p role="status" className="text-muted-foreground text-sm">
                Salve ou descarte as alterações antes de registrar a revisão.
              </p>
            )}
            <p className="text-muted-foreground text-sm">
              Revisada significa que os dados foram conferidos, não que o
              exercício seja seguro para qualquer pessoa. Regiões não avaliadas
              continuam sem nota. A revisão deve ser realizada por profissional
              qualificado.
            </p>
            <fieldset
              disabled={saving || conflict || editing}
              className="space-y-4"
            >
              <label className="block space-y-2">
                <span>Decisão</span>
                <select
                  className={fieldClass}
                  value={decision}
                  onChange={(event) =>
                    setDecision(
                      event.target.value === 'rejected'
                        ? 'rejected'
                        : 'reviewed'
                    )
                  }
                >
                  <option value="reviewed" disabled={!canAccept}>
                    Marcar como revisada
                  </option>
                  <option value="rejected">Rejeitar avaliação</option>
                </select>
              </label>
              <label className="block space-y-2">
                <span>Justificativa da revisão (opcional)</span>
                <textarea
                  className={fieldClass}
                  rows={4}
                  maxLength={4000}
                  value={notes}
                  onChange={(event) => setNotes(event.target.value)}
                />
              </label>
              <Button
                type="submit"
                disabled={decision === 'reviewed' && !canAccept}
              >
                {saving ? 'Registrando…' : 'Registrar revisão'}
              </Button>
            </fieldset>
            {reviewError && (
              <p role="alert" className="text-destructive">
                {reviewError}
              </p>
            )}
            {conflict && (
              <Button variant="outline" type="button" onClick={reload}>
                Recarregar avaliação
              </Button>
            )}
          </form>
        )}
      </CardContent>
    </Card>
  );
}

export function BiomechanicalAssessmentsAdmin({
  exerciseId,
}: {
  exerciseId?: string;
}) {
  const [query, setQuery] = useState('');
  const [input, setInput] = useState('');
  const [status, setStatus] = useState('pending');
  const [category, setCategory] = useState('');
  const [muscleGroup, setMuscleGroup] = useState('');
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  const [state, setState] = useState<{
    key: string;
    data?: AssessmentList;
    error?: string;
  } | null>(null);
  const params = new URLSearchParams({ page: String(page), page_size: '20' });
  if (query) params.set('q', query);
  if (status) params.set('review_status', status);
  if (category) params.set('category', category);
  if (muscleGroup) params.set('muscle_group', muscleGroup);
  if (exerciseId) params.set('exercise_id', exerciseId);
  const key = params.toString();

  useEffect(() => {
    const controller = new AbortController();
    apiFetch<AssessmentList>(`${endpoint}?${key}`, {
      signal: controller.signal,
      cache: 'no-store',
    })
      .then((data) => {
        if (!controller.signal.aborted) setState({ key, data });
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted)
          setState((current) => ({
            key,
            data: current?.key === key ? current.data : undefined,
            error: errorMessage(error),
          }));
      });
    return () => controller.abort();
  }, [key, retry]);

  const active = state?.key === key ? state : null;
  return (
    <div className="container mx-auto max-w-4xl space-y-6 px-4 py-8 md:px-6">
      <section
        aria-label="Totais de validação do catálogo global"
        className="space-y-2"
      >
        <dl aria-busy={!active} className="grid gap-3 sm:grid-cols-3">
          {(
            [
              ['Total de exercícios', active?.data?.counts.total_exercises],
              [
                'Exercícios validados',
                active?.data?.counts.validated_exercises,
              ],
              [
                'Exercícios não validados',
                active?.data?.counts.unvalidated_exercises,
              ],
            ] as const
          ).map(([label, count]) => (
            <div key={label} className="bg-card rounded-xl border p-4">
              <dt className="text-muted-foreground text-sm">{label}</dt>
              <dd className="mt-1 text-2xl font-semibold tabular-nums">
                {count === undefined ? '—' : count.toLocaleString('pt-BR')}
              </dd>
            </div>
          ))}
        </dl>
        <p className="text-muted-foreground text-xs">
          Totais do catálogo global, sem aplicar os filtros abaixo. Validado: a
          avaliação mais recente está revisada. Não validado: avaliação
          pendente, rejeitada ou exercício sem avaliação.
        </p>
      </section>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Avaliações biomecânicas</h1>
        <Link
          href="/admin/biomechanical-scale"
          className="text-primary underline"
        >
          Editar critérios
        </Link>
      </div>
      <p className="text-muted-foreground">
        Consulta e revisão das avaliações do catálogo global, cadastradas
        externamente. Correções criam novas avaliações pendentes, preservando as
        originais. Esta tela não altera a geração de treinos.
      </p>
      {exerciseId && (
        <div className="space-y-2 text-sm">
          <p className="break-all">Filtrando exercício: {exerciseId}</p>
          <Link
            className="text-primary underline"
            href="/admin/biomechanical-assessments"
          >
            Ver todos os exercícios
          </Link>
        </div>
      )}
      <form
        className="flex flex-wrap items-end gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          setQuery(input.trim());
          setPage(1);
          setSelected(null);
        }}
      >
        <label className="space-y-2">
          <span className="text-sm">Categoria</span>
          <select
            className={fieldClass}
            value={category}
            onChange={(event) => {
              setCategory(event.target.value);
              setPage(1);
              setSelected(null);
            }}
          >
            <option value="">Todas as categorias</option>
            {state?.data?.filters.categories.map((value) => (
              <option key={value} value={value}>
                {categoryLabel(value)}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-2">
          <span className="text-sm">Grupo muscular</span>
          <select
            className={fieldClass}
            value={muscleGroup}
            onChange={(event) => {
              setMuscleGroup(event.target.value);
              setPage(1);
              setSelected(null);
            }}
          >
            <option value="">Todos os grupos musculares</option>
            {state?.data?.filters.muscle_groups.map((value) => (
              <option key={value} value={value}>
                {muscleLabel(value)}
              </option>
            ))}
          </select>
        </label>
        <label className="min-w-0 flex-1 space-y-2">
          <span className="text-sm">
            Buscar exercício por nome ou código de origem
          </span>
          <input
            className={fieldClass}
            maxLength={160}
            value={input}
            onChange={(event) => setInput(event.target.value)}
          />
        </label>
        <label className="space-y-2">
          <span className="text-sm">Status da revisão</span>
          <select
            className={fieldClass}
            value={status}
            onChange={(event) => {
              setStatus(event.target.value);
              setPage(1);
              setSelected(null);
            }}
          >
            <option value="">Todos</option>
            {Object.entries(REVIEW_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <Button type="submit">Buscar</Button>
      </form>
      {active?.error ? (
        <div role="alert" className="space-y-2">
          <p className="text-destructive">{active.error}</p>
          <Button
            variant="outline"
            onClick={() => setRetry((value) => value + 1)}
          >
            Tentar novamente
          </Button>
        </div>
      ) : null}
      {!active?.data && !active?.error ? (
        <p role="status">Carregando avaliações…</p>
      ) : active?.data ? (
        <>
          <p className="text-muted-foreground text-sm">
            {active.data.total} avaliação(ões) encontrada(s).
          </p>
          {active.data.items.length === 0 ? (
            <p>
              Nenhuma avaliação encontrada. O cadastro inicial é feito
              externamente.
            </p>
          ) : (
            <ul className="divide-y rounded-md border px-4">
              {active.data.items.map((item) => (
                <li
                  key={item.id}
                  className="flex flex-wrap items-center justify-between gap-3 py-4"
                >
                  <div className="bg-muted relative h-16 w-20 shrink-0 overflow-hidden rounded-lg">
                    <ExerciseImageViewer
                      images={item.images}
                      alt={item.exercise_name}
                      sizes="80px"
                    />
                  </div>
                  <div className="min-w-0 flex-1 basis-48 space-y-2">
                    <p className="font-medium break-words">
                      {item.exercise_name}
                    </p>
                    <p className="text-muted-foreground text-sm">
                      {REVIEW_LABELS[item.review_status]} · Escala v
                      {item.scale_version}
                      {!item.uses_current_scale && ' (anterior)'}
                    </p>
                    <p className="text-muted-foreground text-xs">
                      {new Date(item.created_at).toLocaleString('pt-BR')}
                    </p>
                    <dl
                      aria-label={`Prévia das notas de ${item.exercise_name}`}
                      className="flex flex-wrap gap-2"
                    >
                      {item.region_scores.map((region) => (
                        <div
                          key={region.region_code}
                          className="bg-muted rounded-lg px-2.5 py-2 text-xs"
                        >
                          <dt className="text-muted-foreground">
                            {region.label}
                          </dt>
                          <dd className="mt-1 font-medium">
                            {region.assessment_status === null
                              ? 'Registro ausente'
                              : region.assessment_status === 'unassessed'
                                ? 'Não avaliada'
                                : region.demand_score === null
                                  ? 'Nota ausente'
                                  : `${region.demand_score}/5`}
                          </dd>
                        </div>
                      ))}
                    </dl>
                  </div>
                  <Button
                    variant="outline"
                    aria-expanded={selected === item.id}
                    aria-controls={`assessment-panel-${item.id}`}
                    onClick={() =>
                      setSelected(selected === item.id ? null : item.id)
                    }
                  >
                    {selected === item.id
                      ? 'Fechar consulta'
                      : 'Consultar avaliação'}
                  </Button>
                  {selected === item.id && (
                    <section
                      id={`assessment-panel-${item.id}`}
                      aria-label={`Detalhe da avaliação de ${item.exercise_name}`}
                      className="w-full min-w-0 space-y-3"
                    >
                      <AssessmentViewer
                        key={item.id}
                        id={item.id}
                        onReviewed={() => setRetry((value) => value + 1)}
                        onCorrected={(saved) => {
                          setSelected(saved.id);
                          setState((current) => {
                            if (current?.key !== key || !current.data)
                              return current;
                            return {
                              ...current,
                              data: {
                                ...current.data,
                                items: current.data.items.map((entry) =>
                                  entry.id === item.id
                                    ? {
                                        ...saved,
                                        region_scores:
                                          saved.scale.definition.regions.map(
                                            (region) => {
                                              const result = saved.regions.find(
                                                (entry) =>
                                                  entry.region_code ===
                                                  region.code
                                              );
                                              return {
                                                region_code: region.code,
                                                label: region.label,
                                                assessment_status:
                                                  result?.assessment_status ??
                                                  null,
                                                demand_score:
                                                  result?.demand_score ?? null,
                                              };
                                            }
                                          ),
                                      }
                                    : entry
                                ),
                              },
                            };
                          });
                          setRetry((value) => value + 1);
                        }}
                      />
                    </section>
                  )}
                </li>
              ))}
            </ul>
          )}
          {active.data.total_pages > 1 && (
            <div className="flex flex-wrap items-center gap-3">
              <Button
                variant="outline"
                disabled={page === 1}
                onClick={() => {
                  setPage(page - 1);
                  setSelected(null);
                }}
              >
                Anterior
              </Button>
              <span className="text-sm">
                Página {page} de {active.data.total_pages}
              </span>
              <Button
                variant="outline"
                disabled={page >= active.data.total_pages}
                onClick={() => {
                  setPage(page + 1);
                  setSelected(null);
                }}
              >
                Próxima
              </Button>
            </div>
          )}
        </>
      ) : null}
    </div>
  );
}
