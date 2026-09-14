import { Router } from "express";
import { validateBody } from "../../middleware/validate.middleware";
import {
  forgotPasswordSchema,
  loginSchema,
  refreshSchema,
  registerSchema,
  resetPasswordSchema,
  verifyEmailSchema,
} from "./auth.schemas";
import {
  forgotPasswordHandler,
  loginHandler,
  logoutHandler,
  refreshHandler,
  registerHandler,
  resetPasswordHandler,
  verifyEmailHandler,
} from "./auth.controller";

export const authRouter = Router();

authRouter.post("/register", validateBody(registerSchema), registerHandler);
authRouter.post("/verify-email", validateBody(verifyEmailSchema), verifyEmailHandler);
authRouter.post("/login", validateBody(loginSchema), loginHandler);
authRouter.post("/refresh", validateBody(refreshSchema), refreshHandler);
authRouter.post("/logout", validateBody(refreshSchema), logoutHandler);
authRouter.post("/forgot-password", validateBody(forgotPasswordSchema), forgotPasswordHandler);
authRouter.post("/reset-password", validateBody(resetPasswordSchema), resetPasswordHandler);
