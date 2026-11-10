import { z } from "zod";
const optionalDecimal = (min: number) =>
  z
    .string()
    .trim()
    .refine(
      (v) =>
        v === "" ||
        (/^\d+(\.\d{1,2})?$/.test(v) && Number(v) >= min && Number(v) <= 3),
      `Use ${min}–3, at most two decimal places, or leave blank.`,
    )
    .transform((v) => v || null);
export const preferenceForm = z.object({
  preferred_language_tag: z
    .string()
    .trim()
    .max(35)
    .transform((v) => v || null),
  text_scale: optionalDecimal(0.75),
  line_spacing: optionalDecimal(1),
  theme: z
    .enum(["", "system", "light", "dark", "high_contrast"])
    .transform((v) => v || null),
  reduce_motion: z
    .enum(["", "true", "false"])
    .transform((v) => (v === "" ? null : v === "true")),
});
const count = z
  .string()
  .regex(/^\d+$/, "Enter a whole number.")
  .transform(Number)
  .pipe(z.number().int().min(0).max(2147483647));
const positive = count.refine((v) => v > 0, "Must be greater than zero.");
const optionalCount = z.union([z.literal("").transform(() => null), count]);
export const observationFields = [
  ["reading_duration_ms", "Reading duration (milliseconds)"],
  ["attempted_word_count", "Words attempted"],
  ["correct_word_count", "Words correct"],
  ["omission_count", "Omissions"],
  ["substitution_count", "Substitutions"],
  ["insertion_count", "Insertions"],
  ["repetition_count", "Repetitions"],
  ["self_correction_count", "Self corrections"],
  ["unfamiliar_word_count", "Unfamiliar words (optional)"],
] as const;
export function completionForm(questionCount: number, wordCount: number) {
  return z
    .object({
      reading_duration_ms: positive,
      attempted_word_count: count,
      correct_word_count: count,
      omission_count: count,
      substitution_count: count,
      insertion_count: count,
      repetition_count: count,
      self_correction_count: count,
      unfamiliar_word_count: optionalCount,
      comprehension_correct: questionCount
        ? count
        : z
            .string()
            .optional()
            .transform(() => null),
    })
    .superRefine((v, ctx) => {
      if (v.attempted_word_count > wordCount)
        ctx.addIssue({
          code: "custom",
          path: ["attempted_word_count"],
          message: "Cannot exceed the passage word count.",
        });
      if (v.attempted_word_count + v.omission_count > wordCount)
        ctx.addIssue({
          code: "custom",
          path: ["omission_count"],
          message:
            "Attempted words plus omissions cannot exceed the passage word count.",
        });
      if (v.correct_word_count > v.attempted_word_count)
        ctx.addIssue({
          code: "custom",
          path: ["correct_word_count"],
          message: "Cannot exceed words attempted.",
        });
      if (
        v.unfamiliar_word_count !== null &&
        v.unfamiliar_word_count > v.attempted_word_count
      )
        ctx.addIssue({
          code: "custom",
          path: ["unfamiliar_word_count"],
          message: "Cannot exceed words attempted.",
        });
      if (
        v.comprehension_correct !== null &&
        v.comprehension_correct > questionCount
      )
        ctx.addIssue({
          code: "custom",
          path: ["comprehension_correct"],
          message: "Cannot exceed the question count.",
        });
    })
    .transform((v) => ({ ...v, comprehension_total: questionCount || null }));
}
