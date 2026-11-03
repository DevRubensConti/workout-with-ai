'use client';

import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Timer } from 'lucide-react';
import { ApiError, apiFetch } from '@/lib/api';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';

export function WorkoutPreferencesForm() {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    apiFetch<{ rest_timer_enabled: boolean }>('/auth/workout-preferences', {
      signal: controller.signal,
      cache: 'no-store',
    })
      .then((data) => {
        if (!controller.signal.aborted) {
          setEnabled(data.rest_timer_enabled);
          setError('');
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted)
          setError(
            error instanceof ApiError
              ? error.message
              : 'Não foi possível carregar a preferência.'
          );
      });
    return () => controller.abort();
  }, [retry]);

  async function save(value: boolean) {
    setSaving(true);
    try {
      const data = await apiFetch<{ rest_timer_enabled: boolean }>(
        '/auth/workout-preferences',
        { method: 'PUT', body: { rest_timer_enabled: value } }
      );
      setEnabled(data.rest_timer_enabled);
      toast.success('Preferência de timer salva.');
    } catch (error) {
      toast.error(
        error instanceof ApiError
          ? error.message
          : 'Não foi possível salvar a preferência.'
      );
    } finally {
      setSaving(false);
    }
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Timer className="size-5" /> Durante o treino
        </CardTitle>
        <CardDescription>
          Personalize o temporizador do modo de execução.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {error ? (
          <div role="alert" className="space-y-2">
            <p className="text-destructive text-sm">{error}</p>
            <Button
              variant="outline"
              onClick={() => setRetry((value) => value + 1)}
            >
              Tentar novamente
            </Button>
          </div>
        ) : (
          <label className="flex cursor-pointer items-start gap-3">
            <input
              type="checkbox"
              className="accent-primary mt-1 size-5"
              checked={enabled ?? false}
              disabled={enabled === null || saving}
              onChange={(event) => void save(event.target.checked)}
            />
            <span>
              <span className="block font-medium">
                Ativar tempo de descanso
              </span>
              <span className="text-muted-foreground text-sm">
                Ao concluir uma série, inicia a contagem regressiva do descanso
                prescrito. Desativado, o timer mostra somente o tempo de treino.
              </span>
            </span>
          </label>
        )}
        <p role="status" className="text-muted-foreground mt-2 text-xs">
          {saving
            ? 'Salvando…'
            : enabled === null && !error
              ? 'Carregando…'
              : 'Aplicado ao abrir ou recarregar o treino.'}
        </p>
      </CardContent>
    </Card>
  );
}
