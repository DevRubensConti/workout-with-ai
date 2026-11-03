'use client';

import { ArrowLeft, Sparkles } from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';
import { toast } from 'sonner';

import { WorkoutBuilder } from '@/components/workouts/workout-builder';
import { Button } from '@/components/ui/button';
import { ApiError, apiFetch } from '@/lib/api';
import { muscleLabel } from '@/lib/exercises';
import {
  AUTO_STYLE_BY_DAYS,
  AVOID_MUSCLES,
  DAYS_OPTIONS,
  DEFAULT_INPUT,
  FOCUS_MUSCLES,
  GOAL_OPTIONS,
  LEVEL_CHOICES,
  MAX_AVOID,
  MAX_FOCUS,
  MINUTES_OPTIONS,
  SPLIT_STYLES,
  draftFromGenerated,
  type GenerateInput,
  type GeneratedPlan,
} from '@/lib/generator';
import type { Draft } from '@/lib/workouts';
import { cn } from '@/lib/utils';

interface Generated {
  draft: Draft;
  plan: GeneratedPlan;
  input: GenerateInput;
}

function Section({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3">
      <div>
        <h2 className="font-semibold">{title}</h2>
        {hint && <p className="text-muted-foreground text-sm">{hint}</p>}
      </div>
      {children}
    </section>
  );
}

function OptionCard({
  selected,
  title,
  description,
  onSelect,
}: {
  selected: boolean;
  title: string;
  description: string;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      onClick={onSelect}
      className={cn(
        'focus-visible:ring-ring/60 rounded-xl border p-4 text-left transition-colors outline-none focus-visible:ring-[3px]',
        selected
          ? 'border-primary bg-primary/10'
          : 'bg-card hover:border-primary/50'
      )}
    >
      <span className="block font-semibold">{title}</span>
      <span className="text-muted-foreground mt-1 block text-sm">
        {description}
      </span>
    </button>
  );
}

function Chip({
  selected,
  disabled,
  onToggle,
  children,
}: {
  selected: boolean;
  disabled?: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      disabled={disabled && !selected}
      onClick={onToggle}
      className={cn(
        'rounded-full border px-3.5 py-1.5 text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-40',
        selected
          ? 'bg-primary text-primary-foreground border-primary'
          : 'text-muted-foreground hover:text-foreground'
      )}
    >
      {children}
    </button>
  );
}

function toggle(list: string[], value: string) {
  return list.includes(value)
    ? list.filter((item) => item !== value)
    : [...list, value];
}

export function GenerateFlow() {
  const [input, setInput] = useState<GenerateInput>(DEFAULT_INPUT);
  const [generated, setGenerated] = useState<Generated | null>(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function patch(change: Partial<GenerateInput>) {
    setInput((current) => ({ ...current, ...change }));
  }

  // O estilo escolhido pode não existir para o novo número de dias: volta ao automático.
  function changeDays(days: number) {
    setInput((current) => {
      const style = SPLIT_STYLES.find(
        (item) => item.value === current.split_style
      );
      const stillValid = !style || style.days.includes(days);
      return {
        ...current,
        days_per_week: days,
        split_style: stillValid ? current.split_style : 'auto',
      };
    });
  }

  async function generate() {
    setGenerating(true);
    setError(null);
    try {
      const plan = await apiFetch<GeneratedPlan>('/workouts/generate', {
        method: 'POST',
        body: input,
      });
      setGenerated({ draft: draftFromGenerated(plan), plan, input });
      window.scrollTo({ top: 0 });
    } catch (caught) {
      const message =
        caught instanceof ApiError
          ? caught.message
          : 'Não foi possível gerar o treino.';
      setError(message);
      toast.error(message);
    } finally {
      setGenerating(false);
    }
  }

  if (generated) {
    const { plan, input: usedInput } = generated;
    return (
      <WorkoutBuilder
        initialDraft={generated.draft}
        generation={{
          info: {
            rules_version: plan.rules_version,
            review_status: plan.review_status,
            split: plan.split,
            rationale: plan.rationale,
            warnings: plan.warnings,
            references: plan.references,
            weekly_volume: plan.weekly_volume,
          },
          input: usedInput,
        }}
        onRestart={() => setGenerated(null)}
      />
    );
  }

  return (
    <div className="container mx-auto max-w-3xl space-y-8 px-4 py-8 md:px-6">
      <div>
        <Link
          href="/workouts"
          className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-sm"
        >
          <ArrowLeft className="size-4" /> Meus treinos
        </Link>
        <h1 className="mt-1 flex items-center gap-2 text-2xl font-bold tracking-tight md:text-3xl">
          <Sparkles className="text-primary size-6" /> Gerar treino
        </h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Responda algumas perguntas e montamos um treino com base em evidências
          científicas. Você revisa e ajusta antes de salvar.
        </p>
      </div>

      <Section title="Qual é o seu objetivo?">
        <div
          role="radiogroup"
          aria-label="Objetivo"
          className="grid gap-3 sm:grid-cols-2"
        >
          {GOAL_OPTIONS.map((option) => (
            <OptionCard
              key={option.value}
              selected={input.goal === option.value}
              title={option.title}
              description={option.description}
              onSelect={() => patch({ goal: option.value })}
            />
          ))}
        </div>
      </Section>

      <Section title="Qual é o seu nível?">
        <div
          role="radiogroup"
          aria-label="Nível"
          className="grid gap-3 sm:grid-cols-3"
        >
          {LEVEL_CHOICES.map((option) => (
            <OptionCard
              key={option.value}
              selected={input.level === option.value}
              title={option.title}
              description={option.description}
              onSelect={() => patch({ level: option.value })}
            />
          ))}
        </div>
      </Section>

      <Section title="Quantos dias por semana você consegue treinar?">
        <div
          role="radiogroup"
          aria-label="Dias por semana"
          className="flex gap-2"
        >
          {DAYS_OPTIONS.map((days) => (
            <button
              type="button"
              role="radio"
              key={days}
              aria-checked={input.days_per_week === days}
              onClick={() => changeDays(days)}
              className={cn(
                'size-12 rounded-xl border text-lg font-semibold transition-colors',
                input.days_per_week === days
                  ? 'bg-primary text-primary-foreground border-primary'
                  : 'bg-card text-muted-foreground hover:text-foreground'
              )}
            >
              {days}
            </button>
          ))}
        </div>
      </Section>

      <Section
        title="Como quer dividir os treinos?"
        hint="Com o mesmo volume semanal, a ciência não aponta uma divisão melhor que as outras: escolha a que combina com a sua rotina."
      >
        <div
          role="radiogroup"
          aria-label="Estilo de divisão"
          className="grid gap-3 sm:grid-cols-2"
        >
          <OptionCard
            selected={input.split_style === 'auto'}
            title="Automático (recomendado)"
            description={`Para ${input.days_per_week} dias, usamos: ${AUTO_STYLE_BY_DAYS[input.days_per_week]}. Mantém cada músculo principal 2x por semana quando possível.`}
            onSelect={() => patch({ split_style: 'auto' })}
          />
          {SPLIT_STYLES.filter((style) =>
            style.days.includes(input.days_per_week)
          ).map((style) => (
            <OptionCard
              key={style.value}
              selected={input.split_style === style.value}
              title={style.title}
              description={style.description}
              onSelect={() => patch({ split_style: style.value })}
            />
          ))}
        </div>
      </Section>

      <Section
        title="Quanto tempo tem por sessão?"
        hint="Inclui cerca de 8 minutos de aquecimento. Com pouco tempo, o volume é reduzido."
      >
        <div
          role="radiogroup"
          aria-label="Minutos por sessão"
          className="flex flex-wrap gap-2"
        >
          {MINUTES_OPTIONS.map((minutes) => (
            <button
              type="button"
              role="radio"
              key={minutes}
              aria-checked={input.session_minutes === minutes}
              onClick={() => patch({ session_minutes: minutes })}
              className={cn(
                'rounded-xl border px-4 py-2.5 text-sm font-medium transition-colors',
                input.session_minutes === minutes
                  ? 'bg-primary text-primary-foreground border-primary'
                  : 'bg-card text-muted-foreground hover:text-foreground'
              )}
            >
              {minutes} min
            </button>
          ))}
        </div>
      </Section>

      <Section
        title="Quer dar mais atenção a algum músculo? (opcional)"
        hint={`Escolha até ${MAX_FOCUS}. Eles recebem cerca de 25% mais séries.`}
      >
        <div
          role="group"
          aria-label="Músculos em foco"
          className="flex flex-wrap gap-2"
        >
          {FOCUS_MUSCLES.map((muscle) => (
            <Chip
              key={muscle}
              selected={input.focus_muscles.includes(muscle)}
              disabled={input.focus_muscles.length >= MAX_FOCUS}
              onToggle={() =>
                patch({ focus_muscles: toggle(input.focus_muscles, muscle) })
              }
            >
              {muscleLabel(muscle)}
            </Chip>
          ))}
        </div>
      </Section>

      <Section
        title="Alguma dor ou área a proteger? (opcional)"
        hint={`Escolha até ${MAX_AVOID}. As queixas ficam registradas para futura avaliação por IA. O gerador atual não adapta nem exclui exercícios por elas; revise o treino com um profissional.`}
      >
        <div
          role="group"
          aria-label="Áreas a proteger"
          className="flex flex-wrap gap-2"
        >
          {AVOID_MUSCLES.map((muscle) => (
            <Chip
              key={muscle}
              selected={input.avoid_muscles.includes(muscle)}
              disabled={input.avoid_muscles.length >= MAX_AVOID}
              onToggle={() =>
                patch({ avoid_muscles: toggle(input.avoid_muscles, muscle) })
              }
            >
              {muscleLabel(muscle)}
            </Chip>
          ))}
        </div>
      </Section>

      {error && (
        <p
          role="alert"
          className="bg-destructive/10 text-destructive border-destructive/30 rounded-lg border px-4 py-3 text-sm"
        >
          {error}
        </p>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-6">
        <p className="text-muted-foreground max-w-md text-xs">
          Sugestão geral para adultos saudáveis. Em caso de lesão, doença ou
          dúvida, procure um médico ou profissional de educação física.
        </p>
        <Button size="lg" onClick={generate} disabled={generating}>
          <Sparkles /> {generating ? 'Gerando…' : 'Gerar meu treino'}
        </Button>
      </div>
    </div>
  );
}
