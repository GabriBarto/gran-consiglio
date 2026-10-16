import { prisma } from "../../lib/prisma";
import { HttpError } from "../../utils/httpError";
import type { CreateNegozioInput, UpdateNegozioInput } from "./negozio.schemas";

export async function createNegozio(userId: number, input: CreateNegozioInput) {
  const existing = await prisma.negozio.findUnique({ where: { userId } });
  if (existing) {
    throw HttpError.conflict("Hai già un negozio registrato");
  }

  // Lo stato parte sempre da PENDING: l'approvazione è un'azione esclusiva dell'admin.
  return prisma.negozio.create({
    data: { userId, ...input, statoVerifica: "PENDING" },
  });
}

export async function getOwnNegozio(userId: number) {
  const negozio = await prisma.negozio.findUnique({ where: { userId } });
  if (!negozio) {
    throw HttpError.notFound("Nessun negozio associato a questo account");
  }
  return negozio;
}

export async function updateOwnNegozio(userId: number, input: UpdateNegozioInput) {
  const negozio = await getOwnNegozio(userId);
  return prisma.negozio.update({ where: { id: negozio.id }, data: input });
}
