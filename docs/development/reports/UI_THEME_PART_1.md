# UI theme, glass components, and top bar

Implemented within the existing Next.js 16 App Router, React 19, Tailwind 4, and shared CSS architecture. No backend, API contracts, evidence retrieval, calculations, authentication logic, or claim wizard files were changed.

## Theme

`frontend/src/app/theme.css` follows the existing CSS imports and defines the shared tokens. Inter is self-hosted through `next/font`; legacy font utilities resolve to the same sans family. Original hero illustrations remain present, with the Overview illustration adapted to the light theme.

| Token | Value / purpose |
| --- | --- |
| `--cw-page-start`, `--cw-page-middle`, `--cw-page-end` | `#F4FBFA`, `#E8F6F5`, `#EAF2FB` |
| `--cw-page-background` | Gradient with three static soft radial blobs; teal 12% / 8%, blue 10% |
| `--cw-primary`, `--cw-primary-bright` | `#0F766E`, `#0D9488` |
| `--cw-blue` | `#2563EB`, reserved for sparse accents |
| `--cw-action` | `#0B2B2A`; primary task action, pill radius |
| `--cw-ink`, `--cw-muted` | Slate 900 / slate 600 |
| `--cw-glass-card`, `--cw-glass-panel`, `--cw-glass-bar` | White at 55% / 86% / 60% |
| `--cw-border`, `--cw-shadow` | 70% white border; `0 8px 32px rgba(15,118,110,.10)` |
| `--cw-radius`, `--cw-blur` | 24px radius; 20px blur with 150% saturation |
| `--cw-glass-solid` | 92% white fallback |

All four status families have separate background, text, and border tokens. The existing status decisions and caller-supplied labels are preserved. Default labels are Covered, Conditionally covered, Excluded, and Not specified, each with an icon; statuses explicitly marked potentially covered/excluded keep that qualification. Measured text/background contrast ratios: covered 6.78, conditional 5.87, excluded 6.04, unspecified 6.92 (AA minimum 4.5).

## Components and navigation

Import `GlassCard`, `GlassPanel`, and `GlassBar` from `@/components/ui/Glass`. Card and Panel accept normal HTML attributes and an optional semantic `as` element (`div`, `section`, `article`, `aside`, or `header`). Bar renders a sticky header. Use Card for summary content and Panel for forms, clauses, chat, and tables. Nested glass layers have their additional backdrop filters disabled. Existing dense cards use the opaque panel token during migration.

The top bar reuses the existing logo, links, scenario-aware URLs, profile data, menus, and authentication actions. A single persistent indicator moves between nav items in 300ms, with width/position updated after route, font, or viewport changes. `aria-current`, outside-click dismissal, Escape dismissal, and focus return remain supported. Reduced motion removes transitions. Reduced transparency and unsupported backdrop filters use 92% white; reduced transparency also disables blur. The Next.js development badge was already disabled and remains absent.

## Verification and screenshots

- TypeScript and targeted ESLint checks passed for the changed TSX files.
- Overview, policies, coverage, Ask ClaimWise, My claims, and login routes return HTTP 200.
- Isolated headless Chrome preview: desktop 1440px and mobile 390px, no horizontal overflow or runtime exceptions.
- Shared indicator persisted through client navigation and aligned with the active item; mobile menu opened and Escape closed it.
- Runtime checks confirmed Inter, sticky bar positioning, glass opacity, no nested filters, 92% white/no-blur reduced-transparency fallback, and disabled motion under reduced-motion preference.
- Screenshots show a real signed-out preview. No account identity, claims, or policy evidence was fabricated. The authenticated profile menu was not exercised in this isolated session.

Artifacts: `docs/screenshots/overview-theme-desktop.png`, `docs/screenshots/overview-theme-mobile.png`, and `docs/screenshots/theme-verification.json`.

## Issues noticed

- Fixed presentation issues: Overview displayed a raw HTTP 401 instead of a sign-in action; failed portfolio loads showed misleading zero counts. It now shows a sign-in prompt and unknown counts as an em dash.
- The homepage assistant illustration contained a hardcoded MRI coverage answer and made-up page/clause reference. Its layout remains, but the text is now a clearly labeled workspace preview with no policy selected and an honest Not specified explanation. Live clause IDs, page references, quotes, and citation controls are unchanged.
- Existing authentication issue from code inspection: `AuthContext` can populate identity from a cached profile and does not clear it if backend token verification fails; `isAuthenticated` derives from the cached user. This remains outside the UI-only changes and needs a separate authentication fix. The top bar uses the identity supplied by the existing context, with email as its fallback instead of an invented display name.

Changed frontend files: `src/app/theme.css`, `src/app/layout.tsx`, `src/app/dashboard/page.tsx`, `src/app/coverage/page.tsx` (status labels only), `src/app/page.tsx` (preview text only), `src/components/ui/Glass.tsx`, `src/components/ui/StatusBadge.tsx`, `src/components/Topbar.tsx`, and `src/components/features/dashboard/ScenarioLauncher.tsx` (presentation only). No added runtime dependencies or configuration are required.
