import type { Request, Response } from "express";
import { asyncHandler } from "../../utils/asyncHandler";
import { HttpError } from "../../utils/httpError";
import * as adminService from "./admin.service";

function parseNegozioId(req: Request): number {
  const id = Number(req.params.id);
  if (!Number.isInteger(id)) throw HttpError.badRequest("id negozio non valido");
  return id;
}

export const listNegoziHandler = asyncHandler(async (req: Request, res: Response) => {
  const stato = (req.query.stato as string | undefined)?.toUpperCase() ?? "PENDING";
  if (!["PENDING", "APPROVED", "REJECTED"].includes(stato)) {
    throw HttpError.badRequest("Parametro 'stato' non valido");
  }
  const negozi = await adminService.listNegoziByStato(stato as "PENDING" | "APPROVED" | "REJECTED");
  res.json(negozi);
});

export const approveNegozioHandler = asyncHandler(async (req: Request, res: Response) => {
  const negozio = await adminService.approveNegozio(parseNegozioId(req));
  res.json(negozio);
});

export const rejectNegozioHandler = asyncHandler(async (req: Request, res: Response) => {
  const negozio = await adminService.rejectNegozio(parseNegozioId(req), req.body.motivo);
  res.json(negozio);
});
