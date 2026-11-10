import { ApiError } from "@j26/api-client";

export type ErrorContext =
  | "reading"
  | "login"
  | "admin"
  | "preferences"
  | "assessment"
  | "pdf";

export function errorMessage(
  error: unknown,
  context: ErrorContext = "reading",
): string {
  if (context === "login") {
    if (error instanceof ApiError) {
      if (error.status === 401)
        return "The login handle or password was rejected. Check both and try again.";
      if (error.status === 422)
        return "Enter a login handle and password, each no longer than 128 characters.";
      if (error.status === 429)
        return "Too many sign-in attempts. Wait a moment before trying again.";
      if (error.status >= 500)
        return "The sign-in service is temporarily unavailable. Try again shortly.";
    }
    return "Sign-in could not complete. Check the API connection and try again. If you changed the API URL, reload the app.";
  }
  if (error instanceof ApiError) {
    if (error.status === 409 && context === "admin")
      return "The handle or an open assignment already exists. Use another handle, or revoke the existing grant before assigning again.";
    if (error.status === 409)
      return "This record changed or an operation is already running. Reload to review the current state before submitting again.";
    if (error.status === 422 && context !== "reading")
      return "Check the entered values and required fields. Nothing was accepted; correct the form and try again.";
    if (error.status === 404 && context === "preferences")
      return "Preferences are available only to the learner or an authorized guardian. Educator access does not include preferences.";
    if (error.status === 404 && context === "assessment")
      return "This assessment is unavailable or you lack permission. Only its administering instructor can complete or abandon it.";
    if (error.status === 503 && context === "pdf")
      return "PDF processing is unavailable. The server requires private PDF storage. Reload sources before retrying this upload.";
    if (error.status === 413 && context === "pdf")
      return "This PDF exceeds the server's file or page limit. Choose a PDF up to 10 MB and 25 pages.";
    if (error.status === 415 && context === "pdf")
      return "The server could not accept this file as a PDF. Choose a valid PDF file.";
    if (error.status === 401)
      return "Your session expired or the sign-in details were rejected. Please sign in again.";
    if (error.status === 403)
      return "Your account does not have permission for this action.";
    if (error.status === 404)
      return "This item is unavailable or your learner access has changed. Instructor access is required to create or process text.";
    if (error.status === 422)
      return "Check your input. Use English text, a title up to 200 characters and text up to 50,000 characters.";
    if (error.status === 413)
      return "This text is too large. Use a shorter passage.";
    if (error.status === 429)
      return "Too many requests. Wait a moment before trying again.";
    if (error.status === 503)
      return "The service is temporarily unavailable. Refresh the material list before repeating a create request.";
  }
  return "Could not complete the request. Check your connection and API URL. A write may have completed; reload before submitting again.";
}
