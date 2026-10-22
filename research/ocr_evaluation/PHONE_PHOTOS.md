# Category P: researcher photo handoff

The protocol needs **five photographs of five distinct printed pages**: **two development**
and **three held-out**. The two development captures are now supplied; three held-out
captures remain pending. One photograph per page is enough. Extra photos/crops of the same
page remain derivatives in that same source family, never additional independent cases.
No downloaded, stock, generated or external images are admissible substitutes.

## What to print and photograph

The **two development photographs were captured from the original two-line sheets**
under `artifacts/development-drafts-v1/`. Those sheets and their original ground truth
are authoritative for the registered photographs. Do not replace their text or score
these photographs against the later, longer `development-v2` print sheets. The v2 sheets
remain preserved as unused alternatives; they are not the source of the existing photos.
For any recapture of these exact development fixtures, print each archived v1 PNG
on its own plain white sheet, at normal readable size, without adding headers/footers:

| Split | Fixture ID / photo basename | Printed source |
|---|---|---|
| Development | `phone_camera_photo-development-01` | `artifacts/development-drafts-v1/phone_camera_photo-development-01.png`, titled **Photo print master one** |
| Development | `phone_camera_photo-development-02` | `artifacts/development-drafts-v1/phone_camera_photo-development-02.png`, titled **Photo print master two** |
| Held-out | `phone_camera_photo-heldout-01` | Reserved **Held-out photo page 01**, a new original prose page; print master not generated yet |
| Held-out | `phone_camera_photo-heldout-02` | Reserved **Held-out photo page 02**, a new original punctuation/numbers page; print master not generated yet |
| Held-out | `phone_camera_photo-heldout-03` | Reserved **Held-out photo page 03**, a new original small-table page; print master not generated yet |

**The two development photos now exist; wait for the three held-out print masters.**
Their exact visible text and geometry must be authored and frozen after
development selection, as required by the original execution order. They will be supplied
under `artifacts/phone_print_masters/heldout/`, with filenames
`phone_camera_photo-heldout-01.png` through `phone_camera_photo-heldout-03.png`.
Those files do not exist yet; do not reuse the development pages or improvise substitutes.
The captured photo, archived-v1 master and truth hashes are in
`manifests/phone-development.v1.json`. The later v2 print-master manifest records
unused alternatives and does not supply ground truth for the registered photos.

## Capture and filenames

Use the phone's ordinary camera, not a document-scanning/OCR/filter app. Capture the
whole page with all text visible, in readable focus, on a plain neutral surface. For the
first development page use a nearly overhead view; for the second use a mild natural
camera angle. Exclude people, private surroundings, names and private documents.
Disable location tagging. Keep the original capture; do not digitally add blur, perspective
or contrast changes. Record any necessary format conversion separately.

Supply JPEG files with `.jpg` extension (actual JPEG bytes, not renamed HEIC). Each must
be <=10 MiB, <=6000 pixels on either axis and <=12 million decoded pixels. Use an
appropriate camera resolution; if resizing/export is necessary, retain the original
outside Git and record the conversion. The harness applies EXIF orientation once.

Place files at these exact paths (directories have been created):

```text
/Users/chamudikapramod/4 year 1 sem/Research /NLP_Project/research/ocr_evaluation/artifacts/phone_photos/development/phone_camera_photo-development-01.jpg
/Users/chamudikapramod/4 year 1 sem/Research /NLP_Project/research/ocr_evaluation/artifacts/phone_photos/development/phone_camera_photo-development-02.jpg
/Users/chamudikapramod/4 year 1 sem/Research /NLP_Project/research/ocr_evaluation/artifacts/phone_photos/heldout/phone_camera_photo-heldout-01.jpg
/Users/chamudikapramod/4 year 1 sem/Research /NLP_Project/research/ocr_evaluation/artifacts/phone_photos/heldout/phone_camera_photo-heldout-02.jpg
/Users/chamudikapramod/4 year 1 sem/Research /NLP_Project/research/ocr_evaluation/artifacts/phone_photos/heldout/phone_camera_photo-heldout-03.jpg
```

These directories are ignored by Git. The researcher attested that the two development
files are genuine phone captures; visual inspection confirmed their printed title/body
against the matching archived masters. Neither image carries EXIF tags. The two samples
contain only two short lines each, so they have limited representativeness. Final held-out
execution must still pass all freeze gates and is blocked while any required photograph
is missing. All three held-out photos remain absent and unexecuted.
