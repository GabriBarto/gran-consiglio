import { z } from "zod";

export const rejectNegozioSchema = z.object({
  motivo: z.string().min(3).max(500),
});
