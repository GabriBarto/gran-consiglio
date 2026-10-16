import type { NextFunction, Request, Response } from "express";
import { HttpError } from "../utils/httpError";
import { verifyAccessToken, type AccessTokenPayload } from "../utils/tokens";

declare global {
  namespace Express {
    interface Request {
      user?: AccessTokenPayload;
    }
  }
}

export function requireAuth(req: Request, _res: Response, next: NextFunction) {
  const header = req.headers.authorization;
  if (!header?.startsWith("Bearer ")) {
    throw HttpError.unauthorized("Token di accesso mancante");
  }

  const token = header.slice("Bearer ".length);
  try {
    req.user = verifyAccessToken(token);
  } catch {
    throw HttpError.unauthorized("Token di accesso non valido o scaduto");
  }
  next();
}
