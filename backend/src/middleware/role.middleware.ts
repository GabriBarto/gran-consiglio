import type { NextFunction, Request, Response } from "express";
import type { Ruolo } from "@prisma/client";
import { HttpError } from "../utils/httpError";

// Da usare dopo requireAuth. Es: router.post("/", requireAuth, requireRole("ADMIN"), handler)
export function requireRole(...allowed: Ruolo[]) {
  return (req: Request, _res: Response, next: NextFunction) => {
    if (!req.user) {
      throw HttpError.unauthorized();
    }
    if (!allowed.includes(req.user.role)) {
      throw HttpError.forbidden("Il tuo ruolo non può accedere a questa risorsa");
    }
    next();
  };
}
