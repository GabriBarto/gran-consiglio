import nodemailer from "nodemailer";
import { env } from "../config/env";

// In sviluppo, se SMTP non è configurato, l'email viene solo stampata in console
// così il flusso di verifica/reset è testabile senza un vero provider email.
const transporter = env.smtp.host
  ? nodemailer.createTransport({
      host: env.smtp.host,
      port: env.smtp.port,
      secure: env.smtp.port === 465,
      auth: env.smtp.user ? { user: env.smtp.user, pass: env.smtp.password } : undefined,
    })
  : null;

interface SendEmailInput {
  to: string;
  subject: string;
  html: string;
}

export async function sendEmail({ to, subject, html }: SendEmailInput): Promise<void> {
  if (!transporter) {
    // eslint-disable-next-line no-console
    console.log(`\n[email:dev] A: ${to}\n[email:dev] Oggetto: ${subject}\n[email:dev] ${html}\n`);
    return;
  }
  await transporter.sendMail({ from: env.smtp.from, to, subject, html });
}

export function buildVerificationEmail(token: string): { subject: string; html: string } {
  const link = `${env.appBaseUrl}/verify-email?token=${token}`;
  return {
    subject: "Conferma la tua email",
    html: `<p>Benvenuto! Conferma la tua email cliccando <a href="${link}">questo link</a>.</p>
           <p>Il link scade tra ${env.emailVerificationTokenTtlHours} ore.</p>`,
  };
}

export function buildPasswordResetEmail(token: string): { subject: string; html: string } {
  const link = `${env.appBaseUrl}/reset-password?token=${token}`;
  return {
    subject: "Reimposta la tua password",
    html: `<p>Hai richiesto di reimpostare la password. Clicca <a href="${link}">qui</a> per procedere.</p>
           <p>Se non sei stato tu, ignora questa email. Il link scade tra ${env.passwordResetTokenTtlMinutes} minuti.</p>`,
  };
}
