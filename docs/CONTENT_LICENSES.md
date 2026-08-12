# Content Licensing

## Summary

**Every piece of educational content shipped in this repository was originally authored for
HieuTrienEducation.** No third-party educational content is bundled — not from OpenStax, not from
Khan Academy, not from OATutor's content repository, not from anywhere else.

That is a deliberate choice, not an oversight. It means the platform can be operated commercially
with no attribution obligations and no licence-compatibility analysis, and it removes an entire
class of legal risk from a product that charges course fees.

## What is shipped

| Content | Location | Licence | Author |
|---|---|---|---|
| Mathematics curriculum, grades 6–9 | `content/mathematics/curriculum/` | Proprietary | HieuTrienEducation |
| Physics curriculum, grades 6–9 | `content/physics/curriculum/` | Proprietary | HieuTrienEducation |
| 186 question templates | `content/*/questions/` | Proprietary | HieuTrienEducation |
| 14 lessons | `content/*/lessons/` | Proprietary | HieuTrienEducation |
| Testimonials, blog posts, marketing copy | `services/api/app/seed/seed.py` | Proprietary | HieuTrienEducation |
| Design system, illustrations, logo | `packages/ui/`, `apps/web/` | Proprietary | HieuTrienEducation |

All illustration is generated SVG (blobs, squiggles, the logo mark, the plotting and geometry
figures). There are no bitmap assets, so there is no image licensing to track.

### Seed content that looks like real people

The testimonials and teacher biographies in `seed.py` are **fictional demonstration content**
written for this project. Thầy Hiếu and Cô Triền are the real founders the platform is named for;
their biographies are placeholder text to be replaced with their own words before launch. The
parent and student names attached to testimonials are invented.

Anyone deploying this should replace all of it via the admin dashboard, which is exactly why
testimonials and blog posts are database rows rather than hard-coded strings.

## Third-party code

Bundled code dependencies and their licences:

| Package | Licence |
|---|---|
| Next.js, React | MIT |
| Tailwind CSS | MIT |
| KaTeX | MIT |
| lucide-react | ISC |
| framer-motion | MIT |
| clsx, tailwind-merge | MIT |
| FastAPI, Starlette, Pydantic | MIT |
| SQLAlchemy, Alembic | MIT |
| SymPy | BSD-3-Clause |
| PyJWT | MIT |
| bcrypt | Apache-2.0 |
| PyYAML | MIT |

All permissive. **No AGPL or GPL code is present** — see
[OPEN_SOURCE_RESEARCH.md](OPEN_SOURCE_RESEARCH.md) for how Frappe Learning, ClassroomIO and
OpenStax Exercises were surveyed and then deliberately not used.

## GeoGebra — an outstanding action item

⚠️ **This needs a human decision before commercial launch if GeoGebra activities are wanted.**

GeoGebra's licence page (<https://www.geogebra.org/license>) states that its materials may be used
"for non-commercial purposes" and that "any use of GeoGebra for a commercial purpose is subject to
and requires a special license" — explicitly including *charging course fees for courses that
incorporate GeoGebra resources*.

HieuTrienEducation charges course fees. Therefore:

- The `GeoGebraEmbed` component exists but is **disabled by default**
  (`NEXT_PUBLIC_GEOGEBRA_ENABLED=false`). With the flag off it loads nothing from GeoGebra's
  servers and renders a notice explaining why.
- **No lesson in the shipped curriculum uses it.** Interactive mathematics is served by our own
  dependency-free SVG widgets, so the product does not depend on a licence we do not hold.
- To enable it, contact office@geogebra.org for a License and Collaboration Agreement first.

The `apiterms` page returned HTTP 403 to automated fetching during research, so the summary above
is from the main licence page. **A human should confirm the exact commercial terms with GeoGebra
directly.**

## Importing open content later

`scripts/import_open_content.py` exists so an operator can bring in content they have established
the rights to. It enforces the rules rather than trusting the caller:

- `--license` is **required**. A file that does not state its licence is a file we cannot legally
  redistribute.
- Only these licences are accepted, and the whole batch is refused otherwise:
  `CC-BY-4.0`, `CC-BY-3.0`, `CC-BY-SA-4.0`, `CC-BY-SA-3.0`, `CC0-1.0`, `PUBLIC-DOMAIN`.
- Every imported row keeps `source`, `license` and `attribution`, which are columns on the
  `questions` and `lessons` tables specifically so attribution can never be lost.
- Imported questions land as `pending_review`, so a human sees them before a student does.

### A share-alike warning

`CC-BY-SA` content is accepted by the importer but carries a consequence worth stating plainly:
**share-alike may oblige you to license derivative content under the same terms.** Mixing CC BY-SA
material into a proprietary lesson is not straightforwardly safe. If you import share-alike
content, keep it in questions that are clearly separable from your own work, and take advice.

`CC-BY` (attribution only) has no such complication and is the safer choice.

### Candidate sources, not yet used

| Source | Content licence | Notes |
|---|---|---|
| OpenStax | CC BY 4.0 (typically) | High quality, aligned to US standards; would need adaptation for the Vietnamese curriculum |
| CK-12 | CC BY-NC | **Non-commercial — unusable here** |
| Khan Academy exercises | Varies, often CC BY-NC-SA | **Non-commercial — unusable here** |
| OATutor content | CC BY (per its repository) | Adapted OpenStax material, already structured for tutoring |

Note how many otherwise excellent sources are ruled out by a `-NC` clause. That is the single
biggest reason the curriculum here was written from scratch.

## Attribution obligations we currently have

**None.** No content requiring attribution is shipped.

If that changes, the mechanism is already in place: the `attribution` column is rendered in the
lesson footer (`apps/web/src/app/[locale]/lessons/[slug]/page.tsx`) and stored on every question.

## For anyone deploying this

1. Replace the fictional testimonials and teacher biographies with real ones.
2. Decide the GeoGebra question — obtain a licence, or leave the flag off.
3. If importing open content, keep the licence and attribution columns populated; the importer
   does this automatically, but hand-inserted rows will not.
4. Review this file whenever a new content source is added.
