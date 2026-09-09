export class HttpError extends Error {
  status: number;
  details?: unknown;

  constructor(status: number, message: string, details?: unknown) {
    super(message);
    this.name = "HttpError";
    this.status = status;
    this.details = details;
  }

  static badRequest(message: string, details?: unknown) {
    return new HttpError(400, message, details);
  }
  static unauthorized(message = "Non autenticato") {
    return new HttpError(401, message);
  }
  static forbidden(message = "Non autorizzato") {
    return new HttpError(403, message);
  }
  static notFound(message = "Risorsa non trovata") {
    return new HttpError(404, message);
  }
  static conflict(message: string) {
    return new HttpError(409, message);
  }
}
