# Step 297: authenticated Component 4 host

This supersedes the Step 296 limitation that the default App cannot supply a live
connection. App.tsx now mounts the feature-owned Component4AccountBoundary around
the existing demonstration. It does not replace demo screens or shared navigation.

## Usage and API contracts

1. Launch normally: Demo Mode remains the default and makes no authentication calls.
2. Choose Sign In for Live Mode. Enter the trusted HTTPS server root ending in
   `/api/v1`, login handle and password. The address must not contain embedded
   credentials, query parameters or a fragment. No HTTP or TLS bypass is available.
3. POST `/auth/login` sends the documented `{login_handle, password}` body. Password
   state is cleared when submitted; it is never saved, logged or used as identity.
4. GET `/auth/me` resolves the authenticated account's active identity and global
   roles. JWT payloads are not decoded into trusted identity or permissions.
5. GET `/learners?limit=25` lists only authorized backend-returned names and UUIDs.
   More Learners uses `next_cursor`. No account/relationship creation is attempted.
6. Explicitly choose a returned learner. Existing LearnerProgressScreen,
   GuardianSummaryScreen or EducatorAnalyticsScreen receives a stable liveConnection
   and starts in Live Mode, using the existing client and projections.

The live report-role choices come from `/auth/me`, not the demo role switcher. The
learner list is the backend's union of authorized relationships, not a per-role
grant. A listed learner can still be denied for a specific report role; the report
endpoint rechecks the exact relationship and returns an unavailable state. Selecting
a UI role cannot manufacture consent or learner-level permission. An empty list
shows No authorized learners are available to this account. Refresh Learner List
clears selection before reloading. Role/account/learner changes unmount old live
evidence; new selection is required after changing report roles.

## Session security and lifecycle

Remember Me is enabled by default. Nonsecret server/handle settings use a separate
local settings file. Only the rotating refresh credential uses approved Expo
SecureStore; passwords and access JWTs remain in memory. Startup consumes the saved
refresh credential and fetches authoritative identity and learners again. See
[remembered authentication](../../../../../../docs/component-4-remembered-authentication.md)
for storage failure handling and device verification.

Access expiry uses the backend's expires_in, not unverified JWT claims. Access-token
lookup refreshes near expiry. POST `/auth/refresh` sends the current refresh token
and stores only the validated replacement. Concurrent refresh callers share one
promise because the backend rotates single-use refresh credentials. Refresh failure
or an uncertain response clears local credentials and requests a fresh sign-in; the
old refresh token is never automatically replayed. Component 4's existing analytics
client invokes this same refresh callback following 401, with no infinite retries.

Sign Out immediately clears local tokens, identity, learners and selected evidence,
then POSTs `/auth/logout` with the last refresh token. If unreachable, the UI reports
any local storage cleanup failure or unconfirmed server revocation. Existing
backend expiry still applies. Returning to Demo Mode also signs out locally and
requests server logout. Process termination/disposal cannot guarantee server logout.
Account operations use bounded HTTPS requests, sanitized errors and no raw response
logging. Canceled or superseded requests cannot restore an old authenticated view.

## Boundaries and blockers

Successful login is not processing consent. The backend learning_support evaluator
remains deny-by-default, so authorized analytics currently show the consent-required
state. Missing/revoked/expired relationships remain denied. No database seed, account
provisioning, consent evaluator or teammate-owned module is changed.

No demo telemetry is submitted by this account host. The upstream raw-measurement
adapter remains a separate approved integration. The saved Qwen3 report, PDFs,
recommendations and local demo profile/settings/feedback remain in Demo Mode and
are never relabelled as live results. No credentials are included in those exports.

## Verification and physical iPhone checklist

Automated tests mock HTTP transport for login, me, refresh, logout, paginated learners
and consent-blocked analytics. They do not perform a real login, create accounts,
send real learner data or establish device connectivity.

On a physical iPhone, with a trusted HTTPS backend and an authorized synthetic test
account already provisioned through the approved workflow:

- Enter the address and sign in; check invalid password, unavailable server and
  rate-limit messages without credential exposure.
- Check empty authorized-list behavior, pagination and selection. Each permitted
  role must request its own endpoint; absent relationships must remain unavailable.
- Confirm consent-required reports stay blocked. Do not expect successful analytics
  until the approved backend consent integration is completed.
- Check access expiry, concurrent refresh, revoked sessions, logout and account
  switching. Previous learner evidence must disappear immediately.
- Return to Demo Mode, verify existing scenarios and AI/PDF, restart the app and
  confirm no automatic sign-in after explicit sign-out; the password stays empty.

No physical-device success is claimed by this implementation.
