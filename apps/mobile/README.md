# ReadBuddy mobile

The single ReadBuddy mobile client is an Expo React Native application written in
TypeScript. It currently exposes a development-only Component 4 preview backed only
by deterministic synthetic data.

## Requirements

- Node.js 22.13 or newer for Expo SDK 57
- Yarn 1.22
- Expo Go for the quickest physical-device preview, or Android Studio for an emulator

## Commands

From `apps/mobile`:

```powershell
yarn install --frozen-lockfile
yarn start:go
```

Scan the QR code with Expo Go, or press `a` to open an available Android emulator.
For an installed Expo development build, use `yarn start:dev-client` instead.

Validation commands:

```powershell
yarn typecheck
yarn lint
yarn test
yarn config:check
yarn doctor
```

## Safety boundary

The Component 4 preview makes no HTTP requests and does not authenticate users,
evaluate consent, or access learner records. Role switching changes synthetic preview
projections only. Production requests must eventually use the generated client in
`packages/api-client`, the shared `/api/v1` backend, server-side learner authorization,
and an approved consent evaluator.

Only public configuration such as `API_BASE_URL` may enter a mobile bundle. Future
session credentials must use platform-backed secure storage, never plain AsyncStorage.
