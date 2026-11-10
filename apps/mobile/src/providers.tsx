import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { AppState, Platform } from "react-native";
import * as SecureStore from "expo-secure-store";
import {
  QueryClient,
  QueryClientProvider,
  focusManager,
} from "@tanstack/react-query";
import { ApiError } from "@j26/api-client";
import { Session, apiUrl } from "./api/session";
import { workflows } from "./api/workflows";
import { Button, Message, Screen, Title } from "./ui";

const Context = createContext<{
  session: Session;
  api: ReturnType<typeof workflows>;
  active: boolean;
} | null>(null);
export function useApp() {
  const value = useContext(Context);
  if (!value) throw new Error("Missing application provider");
  return value;
}

export function Providers({ children }: { children: ReactNode }) {
  // Resolve on every render: Fast Refresh preserves useState initializers, so
  // creating the client there alone can retain a previous development API URL.
  try {
    const base = apiUrl(process.env.EXPO_PUBLIC_API_URL, __DEV__);
    if (Platform.OS === "web")
      throw new Error("Use the iOS or Android app for secure sessions.");
    return (
      <SessionProviders key={base} base={base}>
        {children}
      </SessionProviders>
    );
  } catch (error) {
    return (
      <Screen>
        <Title>App setup</Title>
        <Message>
          {error instanceof Error
            ? error.message
            : "Invalid app configuration."}
        </Message>
      </Screen>
    );
  }
}

function SessionProviders({
  base,
  children,
}: {
  base: string;
  children: ReactNode;
}) {
  const [active, setActive] = useState(false);
  const [ready, setReady] = useState(false);
  const [failure, setFailure] = useState(false);
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { retry: false, staleTime: 0, gcTime: 0 },
          mutations: { retry: false },
        },
      }),
  );
  const [runtime] = useState(() => {
    try {
      const key = `j26.session.${encodeURIComponent(base).replace(/%/g, "_")}`;
      const session = new Session(
        base,
        {
          read: () => SecureStore.getItemAsync(key),
          write: (value) =>
            SecureStore.setItemAsync(key, value, {
              keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
            }),
          clear: () => SecureStore.deleteItemAsync(key),
        },
        (loggedIn) => {
          if (!loggedIn) {
            void queryClient.cancelQueries();
            queryClient.clear();
          }
          setActive(loggedIn);
        },
      );
      return { session, api: workflows(session) };
    } catch (error) {
      return {
        error:
          error instanceof Error ? error.message : "Invalid app configuration.",
      };
    }
  });

  const restore = async () => {
    if (!runtime.session) return;
    setFailure(false);
    setReady(false);
    try {
      await runtime.session.restore();
      setReady(true);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) setReady(true);
      else setFailure(true);
    }
  };
  useEffect(() => {
    void restore();
  }, [runtime]); // stable runtime, one secure restore
  useEffect(
    () => () => {
      void queryClient.cancelQueries();
      queryClient.clear();
    },
    [queryClient],
  );
  useEffect(() => {
    const subscription = AppState.addEventListener("change", (state) =>
      focusManager.setFocused(state === "active"),
    );
    return () => subscription.remove();
  }, []);
  if (!runtime.session)
    return (
      <Screen>
        <Title>App setup</Title>
        <Message>{runtime.error}</Message>
      </Screen>
    );
  if (!ready)
    return (
      <Screen>
        <Title>Reading Companion</Title>
        <Message>
          {failure
            ? "Session could not be restored. Check your connection and secure storage."
            : "Restoring secure session…"}
        </Message>
        {failure && (
          <>
            <Button title="Retry" onPress={() => void restore()} />
            <Button
              title="Clear saved session"
              onPress={() => {
                void runtime.session
                  .forget()
                  .then(() => {
                    setFailure(false);
                    setReady(true);
                  })
                  .catch(() => setFailure(true));
              }}
            />
          </>
        )}
      </Screen>
    );
  return (
    <QueryClientProvider client={queryClient}>
      <Context.Provider
        value={{ session: runtime.session, api: runtime.api, active }}
      >
        {children}
      </Context.Provider>
    </QueryClientProvider>
  );
}
