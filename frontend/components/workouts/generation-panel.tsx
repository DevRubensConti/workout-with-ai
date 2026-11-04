import { AlertTriangle, BookOpen, Info, Sparkles } from 'lucide-react';

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import type { AiInfo } from '@/lib/generator';
import { cn } from '@/lib/utils';

interface GenerationPanelProps {
  info: AiInfo;
  mode: 'draft' | 'saved';
}

// Explica de onde vêm as escolhas do treino: metas, fundamentos e fontes.
export function GenerationPanel({ info, mode }: GenerationPanelProps) {
  const draft = mode === 'draft';
  const origin =
    info.generator === 'gemini'
      ? `Personalizado pelo Google Gemini${info.model ? ` (${info.model})` : ''}, usando as referências do gerador.`
      : 'Gerado por regras baseadas em evidências.';

  return (
    <Card className="border-primary/30">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Sparkles className="text-primary size-5" />
          {draft
            ? 'Treino sugerido: revise antes de salvar'
            : 'Como este treino foi montado'}
        </CardTitle>
        <CardDescription>
          {origin}
          {draft &&
            ' Você pode trocar, remover ou ajustar qualquer exercício abaixo.'}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        {info.warnings.length > 0 && (
          <ul
            aria-label="Avisos"
            className="border-warning/40 bg-warning-surface space-y-2 rounded-lg border p-3 text-sm"
          >
            {info.warnings.map((warning) => (
              <li key={warning} className="flex gap-2">
                <AlertTriangle className="text-warning mt-0.5 size-4 shrink-0" />
                <span>{warning}</span>
              </li>
            ))}
          </ul>
        )}

        {info.weekly_volume.length > 0 && (
          <section aria-labelledby="weekly-volume-heading">
            <h3
              id="weekly-volume-heading"
              className="mb-3 text-sm font-semibold tracking-wide uppercase"
            >
              Séries por semana (meta)
            </h3>
            <ul className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
              {info.weekly_volume.map((entry) => {
                const reached = entry.sets >= entry.target;
                return (
                  <li key={entry.muscle} className="space-y-1">
                    <div className="flex justify-between text-sm">
                      <span>{entry.label}</span>
                      <span className="text-data tabular-nums">
                        {entry.target > 0
                          ? `${entry.sets}/${entry.target}`
                          : `${entry.sets} · sem meta definida`}
                      </span>
                    </div>
                    {entry.target > 0 && (
                      <div
                        role="progressbar"
                        aria-label={`${entry.label}: ${entry.sets} de ${entry.target} séries`}
                        aria-valuemin={0}
                        aria-valuemax={entry.target}
                        aria-valuenow={entry.sets}
                        className="bg-muted h-1.5 overflow-hidden rounded-full"
                      >
                        <div
                          className={cn(
                            'h-full',
                            reached ? 'bg-data' : 'bg-data-secondary'
                          )}
                          style={{
                            width: `${Math.min(100, (entry.sets / entry.target) * 100)}%`,
                          }}
                        />
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          </section>
        )}

        <details className="group rounded-lg border">
          <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-3 text-sm font-medium">
            <Info className="text-primary size-4" /> Por que este treino?
          </summary>
          <ul className="text-muted-foreground list-disc space-y-2 border-t px-8 py-3 text-sm leading-relaxed">
            {info.rationale.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </details>

        {info.references.length > 0 && (
          <details className="group rounded-lg border">
            <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-3 text-sm font-medium">
              <BookOpen className="text-primary size-4" /> Fontes científicas
            </summary>
            <ol className="text-muted-foreground space-y-2 border-t px-4 py-3 text-xs leading-relaxed">
              {info.references.map((reference) => (
                <li key={reference.id}>
                  <span className="text-foreground font-semibold">
                    [{reference.id}]
                  </span>{' '}
                  {reference.text}
                </li>
              ))}
            </ol>
          </details>
        )}

        <p className="text-muted-foreground text-xs">
          Regras versão {info.rules_version || '—'}
          {info.review_status === 'pendente_revisao_profissional' &&
            ' · base de regras ainda sem revisão profissional'}
          . Este treino não substitui avaliação médica ou profissional.
        </p>
      </CardContent>
    </Card>
  );
}
