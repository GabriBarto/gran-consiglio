import crypto from "node:crypto";
import jwt, { type SignOptions } from "jsonwebtoken";
import { env } from "../config/env";
import type { Ruolo } from "@prisma/client";

export interface AccessTokenPayload {
  sub: number; // userId
  role: Ruolo;
}

export function signAccessToken(payload: AccessTokenPayload): string {
  const options: SignOptions = { expiresIn: env.jwt.accessExpiresIn as SignOptions["expiresIn"] };
  return jwt.sign(payload, env.jwt.accessSecret, options);
}

export function verifyAccessToken(token: string): AccessTokenPayload {
  // I claim custom (sub numerico, role) non coincidono esattamente col JwtPayload standard
  // (che prevede sub: string) — cast esplicito passando per unknown, come suggerito da TS.
  return jwt.verify(token, env.jwt.accessSecret) as unknown as AccessTokenPayload;
}

export interface RefreshTokenPayload {
  sub: number;
  exp: number;
}

export function signRefreshToken(payload: { sub: number }): string {
  const options: SignOptions = { expiresIn: env.jwt.refreshExpiresIn as SignOptions["expiresIn"] };
  return jwt.sign(payload, env.jwt.refreshSecret, options);
}

export function verifyRefreshToken(token: string): RefreshTokenPayload {
  return jwt.verify(token, env.jwt.refreshSecret) as unknown as RefreshTokenPayload;
}

// Token opachi (verifica email, reset password): random, non JWT — così l'unico modo
// per usarli è averli ricevuti via email, e possiamo invalidarli lato DB in ogni momento.
export function generateOpaqueToken(): string {
  return crypto.randomBytes(32).toString("hex");
}

export function addHours(date: Date, hours: number): Date {
  return new Date(date.getTime() + hours * 60 * 60 * 1000);
}

export function addMinutes(date: Date, minutes: number): Date {
  return new Date(date.getTime() + minutes * 60 * 1000);
}
