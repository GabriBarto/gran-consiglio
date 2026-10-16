import { prisma } from "../../lib/prisma";
import { HttpError } from "../../utils/httpError";

export async function listNegoziByStato(stato: "PENDING" | "APPROVED" | "REJECTED") {
  return prisma.negozio.findMany({
    where: { statoVerifica: stato },
    include: { utente: { select: { id: true, username: true, email: true } } },
    orderBy: { createdAt: "asc" },
  });
}

async function findNegozioOrThrow(negozioId: number) {
  const negozio = await prisma.negozio.findUnique({ where: { id: negozioId } });
  if (!negozio) throw HttpError.notFound("Negozio non trovato");
  return negozio;
}

export async function approveNegozio(negozioId: number) {
  await findNegozioOrThrow(negozioId);
  return prisma.negozio.update({
    where: { id: negozioId },
    data: { statoVerifica: "APPROVED", motivoRifiuto: null },
  });
}

export async function rejectNegozio(negozioId: number, motivo: string) {
  await findNegozioOrThrow(negozioId);
  return prisma.negozio.update({
    where: { id: negozioId },
    data: { statoVerifica: "REJECTED", motivoRifiuto: motivo },
  });
}
