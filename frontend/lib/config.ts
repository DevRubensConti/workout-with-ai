export const APP_NAME = 'Workout AI';
export const APP_DESCRIPTION =
  'Seu assistente de treinos com inteligência artificial.';

// Bucket público do Supabase Storage com as imagens do catálogo.
export const EXERCISE_IMAGES_URL = (
  process.env.NEXT_PUBLIC_EXERCISE_IMAGES_URL ||
  'https://hzvnfbmlzhuctanycyfz.supabase.co/storage/v1/object/public/exercise-images'
).replace(/\/+$/, '');

// `path` é o caminho relativo guardado em `exercises.images` (ex.: "Air_Bike/0.jpg").
export function exerciseImageUrl(path: string) {
  const encoded = path.split('/').map(encodeURIComponent).join('/');
  return `${EXERCISE_IMAGES_URL}/${encoded}`;
}
