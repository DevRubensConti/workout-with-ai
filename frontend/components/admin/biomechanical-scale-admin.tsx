'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ApiError, apiFetch } from '@/lib/api';
import type {
  ScaleDefinition,
  ScaleHistory,
  ScaleVersion,
} from '@/lib/biomechanical-scales';

const endpoint = '/biomechanical-scales';
const fieldClass =
  'border-input bg-background w-full rounded-md border px-3 py-2 text-base disabled:opacity-70 md:text-sm';
const textFields = [
  ['title', 'Nome da escala'],
  ['disclaimer', 'Limitações e aviso de segurança'],
  ['reference_conditions', 'Condições de referência'],
  ['evaluation_criteria', 'Critérios de avaliação'],
  ['consistency_rules', 'Regras de consistência e revisão'],
  ['unassessed_guidance', 'Como registrar regiões não avaliadas'],
] as const;

function message(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : 'Não foi possível concluir a operação.';
}

function DefinitionFields({
  value,
  onChange,
}: {
  value: ScaleDefinition;
  onChange?: (value: ScaleDefinition) => void;
}) {
  return (
    <div className="space-y-6">
      {textFields.map(([key, label]) => (
        <label key={key} className="block space-y-2">
          <span className="font-medium">{label}</span>
          <textarea
            className={fieldClass}
            rows={key === 'title' ? 2 : 4}
            required
            maxLength={key === 'title' ? 160 : 4000}
            readOnly={!onChange}
            value={value[key]}
            onChange={(event) =>
              onChange?.({ ...value, [key]: event.target.value })
            }
          />
        </label>
      ))}
      {(['scores', 'regions', 'roles'] as const).map((collection) => (
        <section key={collection} className="space-y-4">
          <h3 className="text-lg font-semibold">
            {collection === 'scores'
              ? 'Escala de 0 a 5'
              : collection === 'regions'
                ? 'Regiões avaliadas'
                : 'Tipos de participação'}
          </h3>
          {value[collection].map((item, index) => {
            const identifier =
              'score' in item ? `Nota ${item.score}` : item.code;
            function update(key: 'label' | 'description', text: string) {
              onChange?.({
                ...value,
                [collection]: value[collection].map((entry, entryIndex) =>
                  entryIndex === index ? { ...entry, [key]: text } : entry
                ),
              });
            }
            return (
              <div key={identifier} className="space-y-3 border-l pl-4">
                <p className="text-muted-foreground text-sm">{identifier}</p>
                <label className="block space-y-1">
                  <span className="text-sm">Nome — {identifier}</span>
                  <input
                    className={fieldClass}
                    required
                    maxLength={160}
                    readOnly={!onChange}
                    value={item.label}
                    onChange={(event) => update('label', event.target.value)}
                  />
                </label>
                <label className="block space-y-1">
                  <span className="text-sm">Definição — {identifier}</span>
                  <textarea
                    className={fieldClass}
                    rows={3}
                    required
                    maxLength={4000}
                    readOnly={!onChange}
                    value={item.description}
                    onChange={(event) =>
                      update('description', event.target.value)
                    }
                  />
                </label>
              </div>
            );
          })}
        </section>
      ))}
    </div>
  );
}

function ScaleEditor({
  current,
  onSaved,
  onReload,
}: {
  current: ScaleVersion;
  onSaved: (version: ScaleVersion) => void;
  onReload: () => void;
}) {
  const [definition, setDefinition] = useState(current.definition);
  const [reason, setReason] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [conflict, setConflict] = useState(false);
  const dirty =
    JSON.stringify(definition) !== JSON.stringify(current.definition);

  useEffect(() => {
    if (!dirty) return;
    function warn(event: BeforeUnloadEvent) {
      event.preventDefault();
    }
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [dirty]);

  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError('');
    try {
      const saved = await apiFetch<ScaleVersion>(endpoint, {
        method: 'POST',
        body: {
          base_version: current.version,
          change_reason: reason,
          definition,
        },
      });
      toast.success(`Versão ${saved.version} salva. Histórico preservado.`);
      onSaved(saved);
    } catch (error) {
      setError(message(error));
      setConflict(error instanceof ApiError && error.status === 409);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={save} className="space-y-6">
      <p className="text-muted-foreground text-sm">
        Editando a versão {current.version}. Salvar cria uma nova versão
        completa. Os códigos das regiões, os tipos de participação e o intervalo
        0–5 são fixos; seus nomes e critérios são editáveis.
      </p>
      <fieldset disabled={saving} className="min-w-0 space-y-6">
        <DefinitionFields value={definition} onChange={setDefinition} />
        <label className="block space-y-2">
          <span className="font-medium">Motivo da alteração</span>
          <textarea
            className={fieldClass}
            required
            maxLength={1000}
            rows={3}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
        </label>
      </fieldset>
      {error && (
        <p role="alert" className="text-destructive">
          {error}
        </p>
      )}
      <div className="flex flex-wrap gap-3">
        <Button
          type="submit"
          disabled={!dirty || !reason.trim() || saving || conflict}
        >
          {saving ? 'Salvando…' : 'Salvar nova versão'}
        </Button>
        <Button
          type="button"
          variant="outline"
          disabled={saving}
          onClick={() => {
            if (
              !dirty ||
              window.confirm(
                'Descartar alterações locais e recarregar os critérios?'
              )
            ) {
              onReload();
            }
          }}
        >
          Recarregar versão atual
        </Button>
      </div>
    </form>
  );
}

function VersionHistory({ currentVersion }: { currentVersion: number }) {
  const [page, setPage] = useState(1);
  const [history, setHistory] = useState<ScaleHistory | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [snapshot, setSnapshot] = useState<ScaleVersion | null>(null);
  const [error, setError] = useState('');
  const [snapshotError, setSnapshotError] = useState('');
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    apiFetch<ScaleHistory>(`${endpoint}?page=${page}`, {
      signal: controller.signal,
      cache: 'no-store',
    })
      .then((data) => {
        if (!controller.signal.aborted) {
          setHistory(data);
          setError('');
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setError(message(error));
      });
    return () => controller.abort();
  }, [page, currentVersion, retry]);

  useEffect(() => {
    if (selected === null) return;
    const controller = new AbortController();
    apiFetch<ScaleVersion>(`${endpoint}/${selected}`, {
      signal: controller.signal,
      cache: 'no-store',
    })
      .then((data) => {
        if (!controller.signal.aborted) setSnapshot(data);
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setSnapshotError(message(error));
      });
    return () => controller.abort();
  }, [selected, retry]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Histórico de versões</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {error ? (
          <p role="alert" className="text-destructive">
            {error}
          </p>
        ) : !history || history.page !== page ? (
          <p role="status">Carregando histórico…</p>
        ) : (
          <>
            <ul className="divide-y">
              {history.items.map((item) => (
                <li key={item.version} className="space-y-2 py-4">
                  <p className="font-medium">
                    Versão {item.version} ·{' '}
                    {new Date(item.created_at).toLocaleString('pt-BR')}
                  </p>
                  <p className="text-sm break-words">{item.change_reason}</p>
                  <p className="text-muted-foreground text-xs break-all">
                    Autor:{' '}
                    {item.created_by ??
                      (item.version === 1
                        ? 'Inicialização do sistema'
                        : 'Administrador removido')}
                  </p>
                  <Button
                    variant="outline"
                    onClick={() => {
                      setSnapshot(null);
                      setSnapshotError('');
                      setSelected(item.version);
                      setRetry((value) => value + 1);
                    }}
                  >
                    Consultar versão {item.version}
                  </Button>
                </li>
              ))}
            </ul>
            <div className="flex flex-wrap items-center gap-3">
              <Button
                variant="outline"
                disabled={page === 1}
                onClick={() => setPage(page - 1)}
              >
                Anterior
              </Button>
              <span className="text-sm">Página {page}</span>
              <Button
                variant="outline"
                disabled={page * 20 >= history.total}
                onClick={() => setPage(page + 1)}
              >
                Próxima
              </Button>
            </div>
          </>
        )}
        {(error || snapshotError) && (
          <Button
            variant="outline"
            onClick={() => {
              setSnapshotError('');
              setRetry((value) => value + 1);
            }}
          >
            Tentar novamente
          </Button>
        )}
        {snapshotError && (
          <p role="alert" className="text-destructive">
            {snapshotError}
          </p>
        )}
        {selected !== null && (
          <section
            aria-label={`Consulta da versão ${selected}`}
            className="space-y-4 border-t pt-6"
          >
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h3 className="font-semibold">
                Versão {selected} — somente leitura
              </h3>
              <Button variant="outline" onClick={() => setSelected(null)}>
                Fechar consulta
              </Button>
            </div>
            {snapshot?.version === selected ? (
              <DefinitionFields value={snapshot.definition} />
            ) : !snapshotError ? (
              <p role="status">Carregando versão…</p>
            ) : null}
          </section>
        )}
      </CardContent>
    </Card>
  );
}

export function BiomechanicalScaleAdmin() {
  const [current, setCurrent] = useState<ScaleVersion | null>(null);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    apiFetch<ScaleVersion>(`${endpoint}/current`, {
      signal: controller.signal,
      cache: 'no-store',
    })
      .then((data) => {
        if (!controller.signal.aborted) {
          setCurrent(data);
          setError('');
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setError(message(error));
      });
    return () => controller.abort();
  }, [retry]);

  function reload() {
    setCurrent(null);
    setError('');
    setRetry((value) => value + 1);
  }

  return (
    <div className="container mx-auto max-w-3xl space-y-6 px-4 py-8 md:px-6">
      <h1 className="text-2xl font-bold">Critérios biomecânicos</h1>
      <Link
        href="/admin/biomechanical-assessments"
        className="text-primary inline-block underline"
      >
        Consultar e revisar avaliações por exercício
      </Link>
      <p className="text-muted-foreground">
        Formalização da demanda por região, não do risco de lesão. Esta etapa
        não classifica exercícios nem altera a geração de treinos.
      </p>
      {error ? (
        <div role="alert" className="space-y-3">
          <p className="text-destructive">{error}</p>
          <Button variant="outline" onClick={reload}>
            Tentar novamente
          </Button>
        </div>
      ) : current ? (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Versão atual: {current.version}</CardTitle>
            </CardHeader>
            <CardContent>
              <ScaleEditor
                key={current.version}
                current={current}
                onSaved={setCurrent}
                onReload={reload}
              />
            </CardContent>
          </Card>
          <VersionHistory
            key={current.version}
            currentVersion={current.version}
          />
        </>
      ) : (
        <p role="status">Carregando critérios…</p>
      )}
    </div>
  );
}
