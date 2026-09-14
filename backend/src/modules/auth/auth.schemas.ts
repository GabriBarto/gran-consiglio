import { z } from "zod";

// Password: almeno 8 caratteri, una maiuscola, una minuscola, un numero.
const passwordSchema = z
  .string()
  .min(8, "La password deve avere almeno 8 caratteri")
  .regex(/[a-z]/, "La password deve contenere almeno una lettera minuscola")
  .regex(/[A-Z]/, "La password deve contenere almeno una lettera maiuscola")
  .regex(/[0-9]/, "La password deve contenere almeno un numero");

export const registerSchema = z.object({
  username: z.string().min(3).max(32),
  email: z.string().email(),
  password: passwordSchema,
  // Un utente può registrarsi come cliente o venditore; ADMIN si assegna solo manualmente/da un admin esistente.
  role: z.enum(["CLIENTE", "VENDITORE"]).default("CLIENTE"),
});
export type RegisterInput = z.infer<typeof registerSchema>;

export const loginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
});
export type LoginInput = z.infer<typeof loginSchema>;

export const verifyEmailSchema = z.object({
  token: z.string().min(1),
});

export const refreshSchema = z.object({
  refreshToken: z.string().min(1),
});

export const forgotPasswordSchema = z.object({
  email: z.string().email(),
});

export const resetPasswordSchema = z.object({
  token: z.string().min(1),
  password: passwordSchema,
});
