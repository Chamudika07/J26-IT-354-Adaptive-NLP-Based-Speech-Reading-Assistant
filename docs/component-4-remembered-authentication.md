# Component 4 remembered authentication

Approved expo-secure-store ~57.0.4 is installed (57.0.4). Native persistent
sign-in still requires physical-device verification.
The SDK 57 bundledNativeModules.json specifies that exact compatible range.
Expo documents SecureStore as included in Expo Go. No biometric
requireAuthentication option is used (it has Expo Go limitations).

## Data separation

URL, login handle, Remember Me and auto-sign-in flag use a separate versioned
feature-owned settings file. No passwords, tokens, learner IDs, roles or analytics
are written to it. Settings use strict HTTPS URL validation and bounded reads.

Only the rotating refresh credential is persisted, with its HTTPS server and handle
binding, inside SecureStore under a namespaced key. Access JWTs stay in memory.
iOS keychain accessibility is WHEN_UNLOCKED_THIS_DEVICE_ONLY. Credentials are not
stored in preview/demo files, PDFs, logs or environment variables.

Restart consumes and deletes the old saved refresh credential BEFORE making the
existing refresh request. The validated replacement is saved before authentication
is exposed. Then /auth/me and the authorized learner list are fetched afresh.
No identity/role/learner claims are trusted from local settings. No automatic POST
reading-session request is made during restoration.

Refresh failure, token expiration or unavailable secure storage returns to sign-in
with URL/handle retained and password empty. Tokens are never replayed after an
uncertain refresh. Secure storage failures have no plaintext token fallback.

Explicit Sign Out clears visible authenticated data immediately, persists a
no-auto-sign-in marker, deletes the secure credential and calls existing logout.
If local cleanup fails, the user gets an explicit failure notice. Both storage and
network can fail: no implementation can promise confirmed erasure/revocation in
that situation; do not suppress the error. Returning to Demo also signs out.
Navigation/unmount does not delete remembered credentials; explicit logout does.
The app requires device unlock for secure restore. Expo Go clearing/reinstallation,
backend refresh-session expiry and server revocation can require a new login.

## Device verification on iPhone

1. Keep trusted HTTPS backend running; sign in with Remember Me enabled.
2. Close/reopen Expo Go; check that session restores without entering a password.
3. Open PP1 journey and Refresh Saved Progress; verify saved synthetic evidence.
4. Sign Out; reopen app and verify no automatic sign-in, retained URL/handle and
   empty password. Verify Remember Me off keeps only nonsecret form settings.
5. Expire/revoke the refresh session through an approved test workflow; reopen and
   confirm sign-in is required. No consent or role permission should change.
6. Test with secure storage unavailable/locked device. No tokens should be written
   to plaintext storage and no previous-account analytics should remain visible.
7. Verify guardian/educator role boundaries, explicit offline fallback, saved AI
   reports and native PDFs. Automated tests do not constitute device verification.
