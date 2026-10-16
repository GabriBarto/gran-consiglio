import type { NextFunction, Request, Response } from "express";
import type { ZodTypeAny } from "zod";
import { HttpError } from "../utils/httpError";

// Valida body/query/params con uno schema zod e sostituisce req.body con i dati parsati (già tipizzati).
export function validateBody(schema: ZodTypeAny) {
  return (req: Request, _res: Response, next: NextFunction) => {
    const result = schema.safeParse(req.body);
    if (!result.success) {
      throw HttpError.badRequest("Dati non validi", result.error.flatten());
    }
    req.body = result.data;
    next();
  };
}
