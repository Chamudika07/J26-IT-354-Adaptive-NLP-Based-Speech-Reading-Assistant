# Connected role analytics: sample data only

The existing Guardian and Educator screens select separate, closed backend artifacts.
The only shared runtime value is an example scenario identifier (prefix, source
digest, period, context and generation revision). It is not a learner identity or authorization token.
No profile name, avatar, settings, feedback, raw sessions, learner-only report or
recommendation is passed to another role. Production providers remain unchanged.

The artifact exporter reuses `project_guardian_summary` and
`project_educator_analytics` on the same validated evidence used for each Learner
prefix. Both exports exclude recommendations and experimental engagement.

- Guardian: permitted metrics, counts, context, support exposures and summaries.
- Educator: detailed metric trends, missingness, context and support-exposure history.
- Missing or mismatched artifacts show unavailable. A separate fixture requires an
  explicit **View separate example** action; it is never silently substituted.
- The legacy separate role examples remain available, with recommendation UI omitted
  in those roles as well. The saved Learner AI report and PDF are not shared.

To regenerate after a custom synthetic import, from `apps/backend`:

```powershell
uv run --frozen python -m app.modules.learner_modelling.role_scenarios --development-synthetic-only
```

This reads only the existing synthetic input/reference files, rejects mismatch,
and writes role-specific Results/Contract JSON files. Reload Expo after regeneration.
There is no database, live AI request or production endpoint. Pins protect build-time
demo consistency; they are not authentication. Learner startup restores the saved
demo selection, and role changes retain only its identifier. Live/release views
cannot select these role artifacts.

## Production multi-learner boundary

The real service contracts use UUID learner identities with separately authorized
self/guardian/educator access paths. Identity-free sample projections do not
establish relationships. The demo role switcher cannot grant access. Production
multi-learner support still requires approved Learners/Auth relationships and
applicable consent checks. The fictional demonstration below is not that integration.

## Fictional Educator student list (STEP 284)

The development/demo Educator dashboard now opens My Students. These display-only
names are not learner identities or authorized classroom relationships:

- Alex Storybook resolves only the current selected scenario's Educator artifact.
- Robin Page and Jamie Bookmark use distinct validated synthetic input histories in
  educatorStudentSources.json. They do not change when the learner scenario changes.
- Each history is processed by CompletedSessionEvidence and project_educator_analytics.
  No Learner artifact, recommendation decision or engagement estimate enters the list.
- Missing or mismatched current evidence shows unavailable. The original independent
  role fixture remains available only through View separate example.
- Student selection is temporary UI state. Existing learner evidence persistence,
  profile/preferences and AI/PDF snapshots are untouched.

Regenerate only the two fictional histories from apps/backend:

    uv run --frozen python -m app.modules.learner_modelling.educator_students --development-synthetic-only

The generated Results/Contract pins detect altered demo bundles; they are not an
access-control mechanism. Production roster, learner relationships, authorization
and consent remain unimplemented here. Do not use this list with real learner data.
The development role-control row reserves right-side space for the reported overlay;
actual Expo Go overlay placement and large-font layout require iPhone inspection.


## Educator PDF reports (STEP 285)

Class Overview and individual student pages offer device-local analytics PDFs using
existing Expo Print and Sharing. They are factual summaries, not AI reports. Only
pinned Educator projections are resolved by the exporter; callers cannot supply
Learner evidence or editable profile names. Display names are fictional constants.

The class report lists all three students with their individual periods and contexts.
It sums completed-session counts across the distinct fictional student histories;
performance measurements are never pooled. Trend counts mean at least one backend
metric has sufficient comparison evidence. Missing-measurement counts cover available
records; unavailable student records have a separate count and make totals incomplete.
Alex follows the current selection; Robin and Jamie remain independent. An unavailable
Alex record cannot be exported as an individual PDF and is marked unavailable in class
reports, never replaced by a different scenario.

Files use ReadBuddy-<student>-Analytics-<date>-<unique-suffix>.pdf or
ReadBuddy-Class-Analytics-<date>-<unique-suffix>.pdf. Generated intermediates and
failed export copies are cleaned up. Successfully shared copies remain in OS-managed
device cache so native share targets can finish reading them; they are not persisted
in the demo data store. The native share sheet controls Save to Files/sharing;
a resolved share operation does not establish that a user saved a copy. Exports are
cancelled before sharing if the view/selection changes during generation.

The existing backend build_structured_report accepts EducatorAnalyticsProjection,
and validate_narrative checks factual claims, references and role fingerprints.
Those pure primitives can support future approved, per-student Educator AI work;
there is no connected Educator AI snapshot/export or class AI-report contract here.
No AI request is made and the Learner-only saved Qwen3 report is never reused.
Native pagination, share-sheet behavior and overlay placement need physical-device
verification after this change, including large system font settings.
