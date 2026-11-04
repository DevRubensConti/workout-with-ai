'use client';

import { useEffect, useState } from 'react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ApiError, apiFetch } from '@/lib/api';
import type { TrainingProfile } from '@/lib/training-profile';

export function TrainingProfileForm() {
  const [profile, setProfile] = useState<TrainingProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    apiFetch<TrainingProfile | null>('/auth/training-profile', {
      signal: controller.signal,
    })
      .then((data) => {
        setProfile(data);
        setError(null);
      })
      .catch((caught: unknown) => {
        if (!controller.signal.aborted) {
          setError(
            caught instanceof ApiError
              ? caught.message
              : 'Falha ao carregar o perfil.'
          );
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [attempt]);

  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setSaving(true);
    try {
      const saved = await apiFetch<TrainingProfile>('/auth/training-profile', {
        method: 'PUT',
        body: {
          age: Number(form.get('age')),
          weight_kg: Number(form.get('weight')),
          height_cm: Number(form.get('height')),
        },
      });
      setProfile(saved);
      toast.success('Perfil de treino atualizado.');
    } catch (caught) {
      toast.error(
        caught instanceof ApiError
          ? caught.message
          : 'Falha ao salvar o perfil.'
      );
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    setSaving(true);
    try {
      await apiFetch('/auth/training-profile', { method: 'DELETE' });
      setProfile(null);
      toast.success('Dados físicos removidos do perfil.');
    } catch (caught) {
      toast.error(
        caught instanceof ApiError
          ? caught.message
          : 'Falha ao remover os dados.'
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Perfil de treino</CardTitle>
        <CardDescription>
          Dados privados, reutilizados na geração por IA apenas com seu
          consentimento. Disponível para adultos de 18 a 100 anos. Mantenha
          idade e medidas atualizadas.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {loading ? (
          <p role="status">Carregando perfil...</p>
        ) : error ? (
          <div className="space-y-3">
            <p role="alert">{error}</p>
            <Button onClick={() => setAttempt((value) => value + 1)}>
              Tentar novamente
            </Button>
          </div>
        ) : (
          <form
            key={profile?.updated_at ?? 'empty'}
            onSubmit={save}
            className="space-y-4"
          >
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="space-y-2">
                <Label htmlFor="training-age">Idade (anos)</Label>
                <Input
                  id="training-age"
                  name="age"
                  type="number"
                  inputMode="numeric"
                  min={18}
                  max={100}
                  step={1}
                  required
                  defaultValue={profile?.age ?? ''}
                  disabled={saving}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="training-weight">Peso (kg)</Label>
                <Input
                  id="training-weight"
                  name="weight"
                  type="number"
                  inputMode="decimal"
                  min={20}
                  max={400}
                  step="0.01"
                  required
                  defaultValue={profile?.weight_kg ?? ''}
                  disabled={saving}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="training-height">Altura (cm)</Label>
                <Input
                  id="training-height"
                  name="height"
                  type="number"
                  inputMode="numeric"
                  min={100}
                  max={250}
                  step={1}
                  required
                  defaultValue={profile?.height_cm ?? ''}
                  disabled={saving}
                />
              </div>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
              <Button type="submit" disabled={saving}>
                {saving ? 'Salvando...' : 'Salvar perfil de treino'}
              </Button>
              {profile && (
                <Button
                  type="button"
                  variant="outline"
                  onClick={remove}
                  disabled={saving}
                >
                  Remover dados físicos
                </Button>
              )}
            </div>
            <p className="text-muted-foreground text-xs">
              Remover o perfil impede novas gerações por IA até preenchê-lo
              novamente. Treinos já salvos e seus textos não são apagados por
              esta ação.
            </p>
          </form>
        )}
      </CardContent>
    </Card>
  );
}
