import { z } from "zod";

export const createNegozioSchema = z.object({
  nome: z.string().min(2).max(100),
  indirizzo: z.string().min(3).max(200),
  lat: z.number().min(-90).max(90),
  lng: z.number().min(-180).max(180),
  telefono: z.string().min(5).max(30).optional(),
  // URL del documento di licenza già caricato su uno storage (es. S3/Cloudinary).
  // L'upload diretto del file è un passo successivo del piano.
  licenzaUrl: z.string().url(),
  orarioApertura: z.string().max(100).optional(),
  fasciaRitiro: z.string().max(100).optional(),
});
export type CreateNegozioInput = z.infer<typeof createNegozioSchema>;

export const updateNegozioSchema = createNegozioSchema.partial().omit({ licenzaUrl: true });
export type UpdateNegozioInput = z.infer<typeof updateNegozioSchema>;
