import type { Request, Response } from "express";
import { asyncHandler } from "../../utils/asyncHandler";
import { HttpError } from "../../utils/httpError";
import * as negozioService from "./negozio.service";

function requireUserId(req: Request): number {
  if (!req.user) throw HttpError.unauthorized();
  return req.user.sub;
}

export const createNegozioHandler = asyncHandler(async (req: Request, res: Response) => {
  const negozio = await negozioService.createNegozio(requireUserId(req), req.body);
  res.status(201).json(negozio);
});

export const getOwnNegozioHandler = asyncHandler(async (req: Request, res: Response) => {
  const negozio = await negozioService.getOwnNegozio(requireUserId(req));
  res.json(negozio);
});

export const updateOwnNegozioHandler = asyncHandler(async (req: Request, res: Response) => {
  const negozio = await negozioService.updateOwnNegozio(requireUserId(req), req.body);
  res.json(negozio);
});
