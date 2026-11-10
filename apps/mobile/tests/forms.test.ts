import assert from "node:assert/strict";
import test from "node:test";
import { educatorForm, grantForm } from "../src/admin-forms";
import { completionForm, preferenceForm } from "../src/learning-forms";
test("admin validation rejects mismatched passwords and expired assignments", () => {
  assert.equal(
    educatorForm.safeParse({
      login_handle: "valid.user",
      password: "Synthetic long passphrase",
      confirm: "wrong",
    }).success,
    false,
  );
  assert.equal(
    grantForm.safeParse({
      learner_id: "not-a-uuid",
      educator_user_id: "not-a-uuid",
      access_level: "instructor",
      expires_at: "2000-01-01T00:00:00Z",
    }).success,
    false,
  );
  assert.deepEqual(
    educatorForm.parse({
      login_handle: " DEMO.USER ",
      password: "Synthetic long passphrase",
      confirm: "Synthetic long passphrase",
    }),
    { login_handle: "demo.user", password: "Synthetic long passphrase" },
  );
});
test("preference form preserves inherited nulls and rejects fractional precision overflow", () => {
  const input = {
    preferred_language_tag: "",
    text_scale: "",
    line_spacing: "",
    theme: "",
    reduce_motion: "",
  };
  assert.equal(preferenceForm.parse(input).reduce_motion, null);
  assert.equal(
    preferenceForm.safeParse({ ...input, text_scale: "1.234" }).success,
    false,
  );
  assert.equal(
    preferenceForm.safeParse({ ...input, line_spacing: "0.5" }).success,
    false,
  );
  assert.equal(
    preferenceForm.parse({ ...input, reduce_motion: "false" }).reduce_motion,
    false,
  );
});
test("assessment observations reject impossible counts and preserve unmeasured values", () => {
  const values = {
    reading_duration_ms: "30000",
    attempted_word_count: "6",
    correct_word_count: "5",
    omission_count: "0",
    substitution_count: "1",
    insertion_count: "0",
    repetition_count: "0",
    self_correction_count: "0",
    unfamiliar_word_count: "",
  };
  const schema = completionForm(0, 6);
  assert.equal(schema.parse(values).comprehension_total, null);
  assert.equal(schema.parse(values).unfamiliar_word_count, null);
  assert.equal(
    schema.safeParse({ ...values, omission_count: "1" }).success,
    false,
  );
  assert.equal(
    schema.safeParse({ ...values, correct_word_count: "7" }).success,
    false,
  );
  assert.equal(
    schema.safeParse({ ...values, reading_duration_ms: "" }).success,
    false,
  );
  assert.equal(
    completionForm(2, 6).safeParse({ ...values, comprehension_correct: "3" })
      .success,
    false,
  );
});
