import type { Ruolo } from "@prisma/client";
import { prisma } from "../../lib/prisma";
import { env } from "../../config/env";
import { HttpError } from "../../utils/httpError";
import { hashPassword, verifyPassword } from "../../utils/password";
import {
  addHours,
  addMinutes,
  generateOpaqueToken,
  signAccessToken,
  signRefreshToken,
  verifyRefreshToken,
} from "../../utils/tokens";
import { buildPasswordResetEmail, buildVerificationEmail, sendEmail } from "../../utils/email";
import type { RegisterInput, LoginInput } from "./auth.schemas";

async function issueTokenPair(userId: number, role: Ruolo) {
  const accessToken = signAccessToken({ sub: userId, role });
  const refreshToken = signRefreshToken({ sub: userId });

  // Il refresh token è salvato in DB (hash sarebbe ancora meglio, ma il valore stesso
  // è già un JWT firmato: qui lo teniamo per poterlo revocare/ruotare esplicitamente).
  const decoded = verifyRefreshToken(refreshToken);
  await prisma.refreshToken.create({
    data: {
      userId,
      token: refreshToken,
      expiresAt: new Date(decoded.exp * 1000),
    },
  });

  return { accessToken, refreshToken };
}

export async function register(input: RegisterInput) {
  const existing = await prisma.utente.findFirst({
    where: { OR: [{ email: input.email }, { username: input.username }] },
  });
  if (existing) {
    throw HttpError.conflict("Email o username già registrati");
  }

  const passwordHash = await hashPassword(input.password);
  const user = await prisma.utente.create({
    data: {
      username: input.username,
      email: input.email,
      passwordHash,
      role: input.role,
    },
  });

  const token = generateOpaqueToken();
  await prisma.emailVerificationToken.create({
    data: {
      userId: user.id,
      token,
      expiresAt: addHours(new Date(), env.emailVerificationTokenTtlHours),
    },
  });

  const { subject, html } = buildVerificationEmail(token);
  await sendEmail({ to: user.email, subject, html });

  return { id: user.id, username: user.username, email: user.email, role: user.role };
}

export async function verifyEmail(token: string) {
  const record = await prisma.emailVerificationToken.findUnique({ where: { token } });
  if (!record || record.usedAt || record.expiresAt < new Date()) {
    throw HttpError.badRequest("Token di verifica non valido o scaduto");
  }

  await prisma.$transaction([
    prisma.utente.update({ where: { id: record.userId }, data: { emailVerified: true } }),
    prisma.emailVerificationToken.update({ where: { id: record.id }, data: { usedAt: new Date() } }),
  ]);
}

export async function login(input: LoginInput) {
  const user = await prisma.utente.findUnique({ where: { email: input.email } });
  if (!user) {
    throw HttpError.unauthorized("Credenziali non valide");
  }

  const valid = await verifyPassword(input.password, user.passwordHash);
  if (!valid) {
    throw HttpError.unauthorized("Credenziali non valide");
  }

  if (!user.emailVerified) {
    throw HttpError.forbidden("Devi prima verificare la tua email");
  }

  const tokens = await issueTokenPair(user.id, user.role);
  return {
    ...tokens,
    user: { id: user.id, username: user.username, email: user.email, role: user.role },
  };
}

export async function refresh(refreshToken: string) {
  let payload: { sub: number };
  try {
    payload = verifyRefreshToken(refreshToken);
  } catch {
    throw HttpError.unauthorized("Refresh token non valido o scaduto");
  }

  const stored = await prisma.refreshToken.findUnique({ where: { token: refreshToken } });
  if (!stored || stored.revokedAt || stored.expiresAt < new Date()) {
    throw HttpError.unauthorized("Refresh token non valido o revocato");
  }

  const user = await prisma.utente.findUnique({ where: { id: payload.sub } });
  if (!user) {
    throw HttpError.unauthorized("Utente non trovato");
  }

  // Rotazione: revoca il token usato e ne emette una nuova coppia.
  await prisma.refreshToken.update({ where: { id: stored.id }, data: { revokedAt: new Date() } });
  return issueTokenPair(user.id, user.role);
}

export async function logout(refreshToken: string) {
  await prisma.refreshToken.updateMany({
    where: { token: refreshToken, revokedAt: null },
    data: { revokedAt: new Date() },
  });
}

export async function forgotPassword(email: string) {
  const user = await prisma.utente.findUnique({ where: { email } });
  // Non riveliamo se l'email esiste o meno, per non facilitare l'enumerazione utenti.
  if (!user) return;

  const token = generateOpaqueToken();
  await prisma.passwordResetToken.create({
    data: {
      userId: user.id,
      token,
      expiresAt: addMinutes(new Date(), env.passwordResetTokenTtlMinutes),
    },
  });

  const { subject, html } = buildPasswordResetEmail(token);
  await sendEmail({ to: user.email, subject, html });
}

export async function resetPassword(token: string, newPassword: string) {
  const record = await prisma.passwordResetToken.findUnique({ where: { token } });
  if (!record || record.usedAt || record.expiresAt < new Date()) {
    throw HttpError.badRequest("Token di reset non valido o scaduto");
  }

  const passwordHash = await hashPassword(newPassword);

  await prisma.$transaction([
    prisma.utente.update({ where: { id: record.userId }, data: { passwordHash } }),
    prisma.passwordResetToken.update({ where: { id: record.id }, data: { usedAt: new Date() } }),
    // Il cambio password invalida tutte le sessioni attive per sicurezza.
    prisma.refreshToken.updateMany({
      where: { userId: record.userId, revokedAt: null },
      data: { revokedAt: new Date() },
    }),
  ]);
}
