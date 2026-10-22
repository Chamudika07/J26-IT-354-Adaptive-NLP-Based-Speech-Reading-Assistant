# Native synthetic AI report PDF export

## Current status

STEP 164 explicitly approved and installed `expo-print 57.0.2` and
`expo-sharing 57.0.23` for Expo SDK 57. `installedPdfModules()` now connects the
public `printToFileAsync`, `isAvailableAsync` and `shareAsync` APIs. The button is
enabled on Android/iOS only after development-only learner demo opt-in and successful
snapshot validation; duplicate taps are blocked during generation/sharing.

The app creates a cached local PDF and opens the native share sheet. It performs no
upload, new model generation or automatic permanent save. No web fallback is used.
Installation changed only package.json and yarn.lock. The installer's automatic
incoming-share plugin entry was removed: receiving shares/extensions are not part of
this feature. No shared app configuration or native project was changed.

Installed using the approved command from `apps/mobile`:

```powershell
yarn expo install expo-print expo-sharing --yarn
yarn expo install --check
```

Rebuild an existing development client if its native modules need updating, or use
matching SDK 57 Expo Go. The user physically verified the existing iPhone export/share workflow. Updated
pagination and Android behavior still require physical-device verification. Automated tests mock native calls and cannot
prove that a PDF renders, opens or saves on a physical device.

## What is exported

Only the explicitly selected, revalidated learner synthetic local AI snapshot.
The snapshot's January UTC dates and six sessions come from its approved statements,
never the separate September/October mobile dashboard. Snapshot validation remains
unchanged. Extra fields, private data, unknown claims, incomplete evidence and
Guardian/Educator requests are rejected before native operations.

The HTML is self-contained and uses no remote fonts, images, JavaScript, APIs or model
calls. It contains original validated statements unchanged, simple unit conversions
for first/latest measurements, all limitations, source/model/generation timestamp,
synthetic disclosures and advisory disclaimers. It introduces no recommendations.
Accuracy is shown as percent, fluency as words/minute and hesitation rate as
hesitations per 100 attempted words. The original units remain in the full statements.
The insufficient-evidence explanation remains visible beside hesitation measurements.

A4 styling uses 16 mm margins, readable system typography, blue ReadBuddy branding,
repeated table headings and natural pagination. There is no forced source-section
page break. Short blocks/rows are kept together, headings stay with their content,
and the closing advisory disclosure stays with the final source statements rather
than appearing as a standalone pre-appendix footer. Original statements remain exact
in a clearly identified source section. The main table uses friendly metric names,
unit conversions and existing validated explanation text without technical prefixes.
Display formatting is explicitly distinguished from unchanged source facts.

A Student Information section uses only fixed display-only labels: Demo Learner,
DEMO-001, Sample Data. It explicitly says these are not authoritative learner
identities and are not inferred from reading sessions. These labels are inserted
only after the existing learner/development/synthetic snapshot checks succeed; they
are never added to the saved snapshot, source statements or Ollama input. Future
production identities require approved Learners/Auth integration, not session UUIDs.

The updated saved fixture was rendered locally in desktop Edge and both pages were
visually inspected using the Windows PDF renderer: two pages, no disclaimer-only
page, no clipped content observed. This does not verify Expo Print/WKWebView on
physical iPhone or Android. Native page breaks can differ and must be rechecked.

The deterministic demo PDF is not enabled and is clearly distinguished from the
validated local AI PDF action. Invalid/missing/unselected snapshots cannot export.
Release builds and live providers cannot use this workflow. No generation takes
place on download. Native errors are sanitized; duplicate taps are blocked; sharing
is not opened if the report selection is invalidated while generation is pending.

## Physical iPhone verification steps

1. Confirm a valid saved snapshot is available; do not regenerate AI content to download.
2. Start Expo (`yarn start:go --clear`), open on iPhone, select Learner demo and open
   **AI Progress Report**.
3. Tap **View saved local AI snapshot** and check its January period and generation time.
4. Tap **Download validated local AI PDF**. The system share sheet should open.
5. Choose **Save to Files**, choose a location, then tap **Save**. Cancelling is allowed.

On Android, select an available save/file destination in the native share sheet;
options depend on installed apps. Only a local cached file URI is passed to the OS.
The app performs no upload or automatic permanent save. A dismissed share sheet is
not proof that the user saved a copy. The OS manages the Print cache; deletion of a
saved copy is the user's responsibility. Production learner exports remain inactive.

Physical-device acceptance on both platforms must confirm readable page breaks,
complete statements, correct metadata, successful file opening/saving, cancellation,
share unavailability and storage/generation failures. Mocked tests do not prove this.


## Updated iPhone layout acceptance

Repeat the already working Learner > AI Progress Report > saved local AI snapshot >
Download validated local AI PDF workflow. Use Save to Files, open the new PDF and
check: Demo Learner / DEMO-001 / Sample Data are explicitly demo identity labels;
January dates and six sessions are unchanged; accuracy is 65 to 85 percent, fluency
100 to 100 words/minute and hesitation 9 to 5 events/100 attempted words. Hesitation
must still say there is insufficient comparable trend evidence. Inspect every page
for clipped rows, isolated headings and disclaimer-only pages. Original technical
statements must remain available in the clearly labeled unchanged-source section.
The updated pagination has not yet been physically verified by the implementation
agent. A resolved native share sheet still does not prove the user saved a copy.
