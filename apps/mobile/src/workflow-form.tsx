import { useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { z } from "zod";
import { Button, ErrorNotice, Field, Message } from "./ui";
import type { ErrorContext } from "./api/errors";

export type FormField = {
  name: string;
  label: string;
  secret?: boolean;
  multiline?: boolean;
  numeric?: boolean;
  options?: { label: string; value: string }[];
};

/** Form-only string inputs are parsed by Zod; API contracts remain generated types. */
export function WorkflowForm<T>({
  fields,
  schema,
  initial = {},
  submitLabel,
  onSubmit,
  context,
  resetOnSuccess = false,
}: {
  fields: FormField[];
  schema: z.ZodType<T>;
  initial?: Record<string, string>;
  submitLabel: string;
  onSubmit(value: T): Promise<void>;
  context: ErrorContext;
  resetOnSuccess?: boolean;
}) {
  const defaults = Object.fromEntries(
    fields.map((field) => [field.name, initial[field.name] ?? ""]),
  );
  const { control, handleSubmit, setError, reset, formState } = useForm<
    Record<string, string>
  >({ defaultValues: defaults });
  const [failure, fail] = useState<unknown>(null);
  return (
    <>
      {fields.map((spec) => (
        <Controller
          key={spec.name}
          control={control}
          name={spec.name}
          render={({ field, fieldState }) =>
            spec.options ? (
              <>
                <Message>{spec.label}</Message>
                {spec.options.map((option) => (
                  <Button
                    key={option.value}
                    title={`${field.value === option.value ? "✓ " : ""}${option.label}`}
                    secondary={field.value !== option.value}
                    disabled={formState.isSubmitting}
                    onPress={() => field.onChange(option.value)}
                  />
                ))}
                {fieldState.error && (
                  <Message>{fieldState.error.message}</Message>
                )}
              </>
            ) : (
              <Field
                label={spec.label}
                value={field.value}
                onChangeText={field.onChange}
                onBlur={field.onBlur}
                error={fieldState.error?.message}
                secureTextEntry={spec.secret}
                multiline={spec.multiline}
                autoCapitalize="none"
                autoCorrect={false}
                autoComplete={spec.secret ? "new-password" : "off"}
                keyboardType={spec.numeric ? "decimal-pad" : "default"}
                editable={!formState.isSubmitting}
              />
            )
          }
        />
      ))}
      <ErrorNotice error={failure} context={context} />
      <Button
        title={formState.isSubmitting ? "Please wait…" : submitLabel}
        disabled={formState.isSubmitting}
        onPress={handleSubmit(async (values) => {
          fail(null);
          const parsed = schema.safeParse(values);
          if (!parsed.success) {
            for (const issue of parsed.error.issues)
              setError(String(issue.path[0] ?? fields[0]?.name), {
                message: issue.message,
              });
            return;
          }
          try {
            await onSubmit(parsed.data);
            if (resetOnSuccess) reset(defaults);
          } catch (error) {
            fail(error);
          }
        })}
      />
    </>
  );
}
