import { z } from "zod";
export const educatorForm = z
  .object({
    login_handle: z
      .string()
      .trim()
      .toLowerCase()
      .regex(
        /^[a-z0-9][a-z0-9._-]{2,63}$/,
        "Use 3–64 lowercase letters, numbers, dots, underscores or hyphens.",
      ),
    password: z.string().min(15, "Use at least 15 characters.").max(128),
    confirm: z.string(),
  })
  .refine((v) => v.password === v.confirm, {
    path: ["confirm"],
    message: "Passwords must match.",
  })
  .transform(({ confirm: _, ...body }) => body);
export const learnerForm = z.object({
  display_name: z.string().trim().min(1).max(80),
});
export const grantForm = z.object({
  learner_id: z.uuid(),
  educator_user_id: z.uuid(),
  access_level: z.enum(["instructor", "viewer"]),
  expires_at: z.iso
    .datetime({ offset: true })
    .refine((v) => Date.parse(v) > Date.now(), "Choose a future expiry."),
});
export const revokeForm = z.object({
  learner_id: z.uuid(),
  grant_id: z.uuid(),
});
