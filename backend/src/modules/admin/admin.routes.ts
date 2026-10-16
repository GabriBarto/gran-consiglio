import { Router } from "express";
import { requireAuth } from "../../middleware/auth.middleware";
import { requireRole } from "../../middleware/role.middleware";
import { validateBody } from "../../middleware/validate.middleware";
import { rejectNegozioSchema } from "./admin.schemas";
import { approveNegozioHandler, listNegoziHandler, rejectNegozioHandler } from "./admin.controller";

export const adminRouter = Router();

adminRouter.use(requireAuth, requireRole("ADMIN"));

adminRouter.get("/negozi", listNegoziHandler);
adminRouter.post("/negozi/:id/approve", approveNegozioHandler);
adminRouter.post("/negozi/:id/reject", validateBody(rejectNegozioSchema), rejectNegozioHandler);
