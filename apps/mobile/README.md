# Mobile placeholder

Reserved for one React Native application using TypeScript.

No React Native project, dependency manifest, native project, or application feature
has been scaffolded. Decide between Expo development builds and React Native CLI
after checking required native recording/speech support, then use the supported
template for that toolchain.

Future conventions:
- Feature folders mirror the seven backend modules.
- All server requests use the shared backend under /api/v1.
- API types come from packages/api-client; never access PostgreSQL directly.
- Only public configuration such as API_BASE_URL belongs in the mobile bundle.
- Store session tokens using platform-backed secure storage, never plain AsyncStorage.
- Build accessible reading controls and component tests when UI work is authorized.
