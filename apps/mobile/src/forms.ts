import { z } from "zod";

export const loginForm = z.object({
  login_handle: z.string().trim().min(1, "Enter your login handle.").max(128),
  password: z.string().min(1, "Enter your password.").max(128),
});
export const textForm = z.object({
  title: z.string().trim().min(1, "Enter a title.").max(200),
  text: z
    .string()
    .min(1, "Paste an English passage.")
    .max(50_000)
    .refine((value) => !!value.trim(), "Enter text, not just spaces."),
});
