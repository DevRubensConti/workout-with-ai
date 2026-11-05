'use client';

import { useEffect, useState } from 'react';

import { Button } from '@/components/ui/button';
import { ApiError, apiFetch } from '@/lib/api';
import type { AssessmentDetail } from '@/lib/biomechanical-assessments';

const fieldClass =
  'border-input bg-background w-full rounded-md border px-3 py-2 text-base md:text-sm';
type Region = AssessmentDetail['regions'][number];

export function AssessmentCorrectionForm({
  detail,
  onSaved,
  onCancel,
  onEditingChange,
}: {
  detail: AssessmentDetail;
  onSaved: (detail: AssessmentDetail) => void;
  onCancel: () => void;
  onEditingChange: (active: boolean) => void;
}) {
  const [initialRegions] = useState<Region[]>(() =>
    detail.scale.definition.regions.map((definition) => {
      const current = detail.regions.find(
        (entry) => entry.region_code === definition.code
      );
      return current
        ? { ...current }
        : {
            region_code: definition.code,
            assessment_status: 'unassessed',
            demand_score: null,
            demand_role: null,
            justification: '',
          };
    })
  );
  const [regions, setRegions] = useState(initialRegions);
  const [reason, setReason] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [conflict, setConflict] = useState(false);
  const changed =
    detail.regions.length !== initialRegions.length ||
    JSON.stringify(regions) !== JSON.stringify(initialRegions);

  useEffect(() => {
    onEditingChange(changed || Boolean(reason.trim()) || saving || conflict);
  }, [changed, reason, saving, conflict, onEditingChange]);

  function patch(code: string, changes: Partial<Region>) {
    setRegions((current) =>
      current.map((region) =>
        region.region_code === code ? { ...region, ...changes } : region
      )
    );
  }

  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError('');
    try {
      const saved = await apiFetch<AssessmentDetail>(
        `/biomechanical-assessments/${detail.id}/corrections`,
        {
          method: 'POST',
          body: { content_hash: detail.content_hash, reason, regions },
        }
      );
      onSaved(saved);
    } catch (failure) {
      setError(
        failure instanceof ApiError
          ? failure.message
          : 'Não foi possível salvar a nova avaliação.'
      );
      setConflict(failure instanceof ApiError && failure.status === 409);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form
      onSubmit={save}
      aria-label="Alterar notas da avaliação"
      className="space-y-4 rounded-lg border p-4"
    >
      <h3 className="font-semibold">Alterar notas</h3>
      <p className="text-muted-foreground text-sm">
        A original será preservada. As alterações criam uma nova avaliação
        manual, pendente de revisão, usando a mesma escala v
        {detail.scale_version}. O exercício deixará de contar como validado até
        a revisão da nova avaliação. Se a anterior estiver pendente, será
        rejeitada automaticamente. Decisões já registradas serão preservadas.
      </p>
      <fieldset disabled={saving || conflict} className="space-y-4">
        {regions.map((region) => {
          const label = detail.scale.definition.regions.find(
            (entry) => entry.code === region.region_code
          )?.label;
          return (
            <fieldset
              key={region.region_code}
              className="space-y-3 rounded-lg border p-3"
            >
              <legend className="px-1 font-medium">{label}</legend>
              <label className="block space-y-1">
                <span className="text-sm">Nota — {label}</span>
                <select
                  className={fieldClass}
                  value={
                    region.assessment_status === 'unassessed'
                      ? ''
                      : String(region.demand_score ?? '')
                  }
                  onChange={(event) => {
                    if (event.target.value === '') {
                      patch(region.region_code, {
                        assessment_status: 'unassessed',
                        demand_score: null,
                        demand_role: null,
                      });
                    } else {
                      patch(region.region_code, {
                        assessment_status: 'assessed',
                        demand_score: Number(event.target.value),
                      });
                    }
                  }}
                >
                  <option value="">Não avaliada — sem nota</option>
                  {detail.scale.definition.scores.map((score) => (
                    <option key={score.score} value={score.score}>
                      {score.score} — {score.label}
                    </option>
                  ))}
                </select>
              </label>
              {region.assessment_status === 'assessed' && (
                <label className="block space-y-1">
                  <span className="text-sm">Participação — {label}</span>
                  <select
                    className={fieldClass}
                    required
                    value={region.demand_role ?? ''}
                    onChange={(event) =>
                      patch(region.region_code, {
                        demand_role: event.target.value || null,
                      })
                    }
                  >
                    <option value="">Selecione a participação</option>
                    {detail.scale.definition.roles.map((role) => (
                      <option key={role.code} value={role.code}>
                        {role.label}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              <label className="block space-y-1">
                <span className="text-sm">
                  Justificativa — {label} (opcional)
                </span>
                <textarea
                  className={fieldClass}
                  rows={3}
                  maxLength={4000}
                  value={region.justification}
                  onChange={(event) =>
                    patch(region.region_code, {
                      justification: event.target.value,
                    })
                  }
                />
              </label>
            </fieldset>
          );
        })}
        <label className="block space-y-1">
          <span className="text-sm">Motivo da alteração (opcional)</span>
          <textarea
            className={fieldClass}
            rows={2}
            maxLength={400}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
        </label>
        <Button
          type="submit"
          className="h-auto min-h-11 max-w-full whitespace-normal"
          disabled={
            !changed ||
            regions.some(
              (region) =>
                region.assessment_status === 'assessed' &&
                (region.demand_score === null || !region.demand_role)
            )
          }
        >
          {saving ? 'Salvando…' : 'Salvar como nova avaliação pendente'}
        </Button>
      </fieldset>
      {error && (
        <p role="alert" className="text-destructive text-sm">
          {error}
        </p>
      )}
      {conflict && (
        <p className="text-muted-foreground text-sm">
          Cancele a edição e consulte a avaliação mais recente antes de tentar
          novamente.
        </p>
      )}
      <Button
        type="button"
        variant="outline"
        disabled={saving}
        onClick={onCancel}
      >
        Descartar alterações e recarregar
      </Button>
    </form>
  );
}
