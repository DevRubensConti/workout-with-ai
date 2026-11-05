'use client';

import { ArrowLeftRight, Loader2 } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

import { ExerciseImageViewer } from '@/components/exercises/exercise-image-viewer';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog';
import { ApiError, apiFetch } from '@/lib/api';
import { equipmentLabel, levelLabel } from '@/lib/exercises';
import type {
  AppliedReplacement,
  ReplacementContext,
  ReplacementOption,
  ReplacementSuggestions,
} from '@/lib/replacements';

interface ExerciseReplacementProps {
  mode: ReplacementContext['mode'];
  name: string;
  disabled?: boolean;
  getContext: () => ReplacementContext | Promise<ReplacementContext>;
  onApplied: (
    option: ReplacementOption,
    result: AppliedReplacement | null
  ) => void;
  onOpenChange?: (open: boolean) => void;
}

export function ExerciseReplacement({
  mode,
  name,
  disabled,
  getContext,
  onApplied,
  onOpenChange,
}: ExerciseReplacementProps) {
  const [open, setOpen] = useState(false);
  const [context, setContext] = useState<ReplacementContext | null>(null);
  const [suggestions, setSuggestions] = useState<ReplacementSuggestions | null>(
    null
  );
  const [loading, setLoading] = useState(false);
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState('');
  const request = useRef<AbortController | null>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  useEffect(() => () => request.current?.abort(), []);

  function changeOpen(value: boolean) {
    if (applying) return;
    if (!value) request.current?.abort();
    setOpen(value);
    onOpenChange?.(value);
  }

  async function load() {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setLoading(true);
    setError('');
    setSuggestions(null);
    try {
      const currentContext = await getContext();
      if (controller.signal.aborted) return;
      setContext(currentContext);
      const result = await apiFetch<ReplacementSuggestions>(
        '/workouts/replacements/suggest',
        {
          method: 'POST',
          body: { context: currentContext, ai_consent: true },
          signal: controller.signal,
        }
      );
      if (!controller.signal.aborted) setSuggestions(result);
    } catch (failure) {
      if (!controller.signal.aborted) {
        setError(
          failure instanceof Error
            ? failure.message
            : 'Não foi possível buscar alternativas.'
        );
      }
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }

  async function choose(option: ReplacementOption) {
    if (!context || !suggestions) return;
    setApplying(true);
    setError('');
    try {
      const result =
        context.mode === 'draft'
          ? null
          : await apiFetch<AppliedReplacement>('/workouts/replacements/apply', {
              method: 'POST',
              body: {
                context,
                replacement_id: option.exercise.id,
                revision: suggestions.revision,
              },
            });
      if (context.mode === 'session' && !result?.session) {
        throw new Error(
          'Resposta da troca sem a sessão atualizada. Recarregue o treino.'
        );
      }
      if (context.mode === 'plan' && !result?.plan) {
        throw new Error(
          'Resposta da troca sem o plano atualizado. Recarregue o treino.'
        );
      }
      onApplied(option, result);
      setOpen(false);
      onOpenChange?.(false);
    } catch (failure) {
      setError(
        failure instanceof Error
          ? failure.message
          : 'Não foi possível salvar a troca.'
      );
      if (failure instanceof ApiError && failure.status === 409)
        setSuggestions(null);
    } finally {
      setApplying(false);
    }
  }

  return (
    <>
      <Button
        ref={trigger}
        type="button"
        variant="outline"
        size="sm"
        className="h-auto min-h-11 whitespace-normal"
        disabled={disabled}
        aria-label={`Trocar exercício: ${name}`}
        onClick={() => {
          setContext(null);
          setSuggestions(null);
          setError('');
          setLoading(false);
          changeOpen(true);
        }}
      >
        <ArrowLeftRight /> Trocar exercício
      </Button>
      <Dialog open={open} onOpenChange={changeOpen}>
        <DialogContent
          className="p-4 sm:p-6"
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            trigger.current?.focus();
          }}
          onEscapeKeyDown={(event) => applying && event.preventDefault()}
          onInteractOutside={(event) => applying && event.preventDefault()}
        >
          <header className="space-y-2 pr-12">
            <DialogTitle>Trocar {name}</DialogTitle>
            <DialogDescription>
              Compare até 3 alternativas com os mesmos músculos primários,
              equipamento e nível. A IA pode errar; confirme a adequação com um
              profissional.
            </DialogDescription>
          </header>
          <p className="text-muted-foreground my-4 text-sm">
            Ao buscar, você autoriza o envio do catálogo e da prescrição do
            treino atual ao Google Gemini. Seu perfil pessoal, cargas e notas
            não são enviados.
          </p>
          <p className="bg-muted mb-4 rounded-lg p-3 text-sm">
            {mode === 'draft'
              ? 'A troca será feita no rascunho e só será gravada ao salvar o treino.'
              : 'No treino salvo, a troca atualiza este dia para os próximos treinos. Durante a sessão, séries concluídas permanecem no exercício original e somente as restantes mudam.'}{' '}
            Séries, repetições e descanso são mantidos. Carga, ritmo e notas
            específicos do exercício são limpos para revisão.
          </p>
          {error && (
            <p role="alert" className="text-destructive mb-3 text-sm">
              {error}
            </p>
          )}
          <Button
            type="button"
            disabled={loading || applying}
            onClick={() => void load()}
          >
            {loading && <Loader2 className="animate-spin" />}
            {loading
              ? 'Comparando alternativas…'
              : suggestions
                ? 'Buscar novamente'
                : 'Autorizar e buscar alternativas'}
          </Button>
          {suggestions && (
            <div className="mt-4 space-y-3">
              {suggestions.message && (
                <p role="status" className="text-muted-foreground text-sm">
                  {suggestions.message}
                </p>
              )}
              <ul className="space-y-3">
                {suggestions.options.map((option) => (
                  <li
                    key={option.exercise.id}
                    className="space-y-3 rounded-xl border p-3"
                  >
                    <div className="flex items-start gap-3">
                      <div className="bg-muted relative h-16 w-20 shrink-0 overflow-hidden rounded-lg">
                        <ExerciseImageViewer
                          images={option.exercise.images}
                          alt={option.exercise.name}
                          sizes="80px"
                        />
                      </div>
                      <div className="min-w-0">
                        <h3 className="font-semibold">
                          {option.exercise.name}
                        </h3>
                        <p className="text-muted-foreground text-sm">
                          {option.exercise.equipment &&
                            equipmentLabel(option.exercise.equipment)}
                          {option.exercise.level &&
                            ` · ${levelLabel(option.exercise.level)}`}
                        </p>
                      </div>
                    </div>
                    <p className="text-sm">
                      <strong>Pró da troca:</strong> {option.pro}
                    </p>
                    <p className="text-sm">
                      <strong>Contra da troca:</strong> {option.con}
                    </p>
                    <Button
                      type="button"
                      disabled={applying || loading}
                      onClick={() => void choose(option)}
                    >
                      {applying ? 'Salvando…' : 'Trocar por este exercício'}
                    </Button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
