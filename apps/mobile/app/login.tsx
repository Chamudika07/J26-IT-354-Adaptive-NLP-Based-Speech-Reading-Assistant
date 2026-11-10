import { Redirect } from "expo-router";
import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import type { z } from "zod";
import { useApp } from "../src/providers";
import { loginForm } from "../src/forms";
import {
  Button,
  Card,
  ErrorNotice,
  Field,
  Message,
  Screen,
  Title,
} from "../src/ui";

export default function Login() {
  const { session, active } = useApp();
  const { control, handleSubmit, resetField } = useForm<
    z.infer<typeof loginForm>
  >({
    resolver: zodResolver(loginForm),
    defaultValues: { login_handle: "", password: "" },
  });
  const login = useMutation({
    mutationFn: session.login.bind(session),
    onSuccess: () => resetField("password"),
  });
  if (active) return <Redirect href="/" />;
  return (
    <Screen>
      <Title>A little reading, every day.</Title>
      <Message>
        Sign in with your assigned account to open your authorized learners.
      </Message>
      <Card>
        <Controller
          control={control}
          name="login_handle"
          render={({ field, fieldState }) => (
            <Field
              label="Login handle"
              autoCapitalize="none"
              autoCorrect={false}
              autoComplete="username"
              value={field.value}
              onChangeText={field.onChange}
              onBlur={field.onBlur}
              error={fieldState.error?.message}
              editable={!login.isPending}
            />
          )}
        />
        <Controller
          control={control}
          name="password"
          render={({ field, fieldState }) => (
            <Field
              label="Password"
              secureTextEntry
              autoCapitalize="none"
              autoCorrect={false}
              autoComplete="current-password"
              value={field.value}
              onChangeText={field.onChange}
              onBlur={field.onBlur}
              error={fieldState.error?.message}
              editable={!login.isPending}
            />
          )}
        />
        <ErrorNotice error={login.error} context="login" />
        <Button
          title={login.isPending ? "Signing in…" : "Sign in"}
          disabled={login.isPending}
          onPress={handleSubmit((value) => login.mutate(value))}
        />
      </Card>
      <Message>
        Accounts are created by an administrator. Use synthetic learner data for
        this research prototype.
      </Message>
    </Screen>
  );
}
