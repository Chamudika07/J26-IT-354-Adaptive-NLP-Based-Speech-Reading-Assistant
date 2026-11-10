import assert from "node:assert/strict";
import test from "node:test";
import { ApiError } from "@j26/api-client";
import { errorMessage } from "../src/api/errors";

test("login failure guidance distinguishes rejected credentials from connectivity", () => {
  const rejected = errorMessage(
    new ApiError(401, "invalid_credentials"),
    "login",
  );
  const offline = errorMessage(new TypeError("fetch failed"), "login");
  assert.match(rejected, /handle or password was rejected/);
  assert.match(offline, /API connection/);
  assert.doesNotMatch(
    offline,
    /password was rejected|write may have completed/i,
  );
});

test("login validation and server failures do not show reading-material guidance", () => {
  assert.match(
    errorMessage(new ApiError(422, "validation_error"), "login"),
    /login handle and password/,
  );
  assert.match(
    errorMessage(new ApiError(503, "service_unavailable"), "login"),
    /sign-in service/,
  );
  assert.match(
    errorMessage(new ApiError(429, "rate_limited"), "login"),
    /Too many sign-in attempts/,
  );
  assert.match(
    errorMessage(new ApiError(422, "validation_error")),
    /English text/,
  );
});

test("login errors never echo arbitrary error payloads", () => {
  const privateValue = "synthetic-private-value-never-display";
  assert.equal(
    errorMessage(new Error(privateValue), "login").includes(privateValue),
    false,
  );
  assert.equal(
    errorMessage(new ApiError(503, privateValue), "login").includes(
      privateValue,
    ),
    false,
  );
});

test("PDF failures explain file limits and unsupported files", () => {
  assert.match(
    errorMessage(new ApiError(413, "too_large"), "pdf"),
    /10 MB and 25 pages/,
  );
  assert.match(
    errorMessage(new ApiError(415, "unsupported_media"), "pdf"),
    /valid PDF/,
  );
});
