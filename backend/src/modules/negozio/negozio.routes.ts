import { Router } from "express";
import { requireAuth } from "../../middleware/auth.middleware";
import { requireRole } from "../../middleware/role.middleware";
import { validateBody } from "../../middleware/validate.middleware";
import { createNegozioSchema, updateNegozioSchema } from "./negozio.schemas";
import { createNegozioHandler, getOwnNegozioHandler, updateOwnNegozioHandler } from "./negozio.controller";

export const negozioRouter = Router();

negozioRouter.use(requireAuth, requireRole("VENDITORE"));

negozioRouter.post("/", validateBody(createNegozioSchema), createNegozioHandler);
negozioRouter.get("/me", getOwnNegozioHandler);
negozioRouter.patch("/me", validateBody(updateNegozioSchema), updateOwnNegozioHandler);
