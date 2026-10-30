# Berkas: Case File Direction

## Identity

Berkas is an investigation workspace that behaves like a physical case file: an index rail on the left, an evidence map in the center, and a findings sheet on the right. The interface should feel handled, annotated, and accountable, not futuristic.

Audience: analysts and investigators working with public-source data who need to see provenance, confidence, and the next pivot without losing the thread.

## Dials

Dial: ENERGY 2 / RHYTHM 3 / MOTION 2

- ENERGY 2: confident but quiet. The graph is the focal point, not decoration.
- RHYTHM 3: the landing intake, workspace, and findings sheet use different compositions because they carry different content.
- MOTION 2: short transitions for state changes and graph layout only. No scroll reveals, no floating elements, no ambient animation.

Reading this as: OSINT investigation workspace for analysts, in a case-file and archival language, dial ENERGY 2 / RHYTHM 3 / MOTION 2.

## Palette

Core palette is limited to parchment, graphite, and warm grey. Vermilion is the single accent.

- Parchment `#f2ebdd`: page ground, evokes paper without a texture pattern.
- Graphite `#23201b`: primary text and structural rules.
- Warm grey `#6b6357`: secondary text, borders, metadata.
- Vermilion `#b8432b`: confidence stamp, active pivot, destructive emphasis. Used sparingly.
- Teal `#2f6b63`: verified or confirmed evidence state.
- Ochre `#9a6b1f`: caution and blocked sources.

Graph entity colors are a functional categorical encoding, not decoration:

- person: graphite
- email: vermilion
- phone: ochre
- username and account: teal
- domain and url: slate `#3f5d78`
- ip: plum `#6a4a72`
- document and image: warm grey
- other: muted brown

Reason: analysts need to scan entity type at a glance. The colors are muted to stay inside the paper palette.

Dark mode uses the same hue relationships on a graphite ground, with parchment text. Both themes ship and both are tested.

## Typography

- Case titles and section headings: `Iowan Old Style`, `Palatino Linotype`, `Book Antiqua`, Georgia, serif. Reason: archival ledger voice, distinct from product UI.
- Interface text: system sans (`Segoe UI`, `system-ui`). Reason: dense controls and long evidence text need neutral readability.
- Identifiers, hashes, confidence scores, and timestamps: `ui-monospace`, `Cascadia Mono`, Consolas. Reason: fixed-width helps comparison and scanning; mono is never used for headings.

## Layout

Desktop workspace is a three-pane grid:

1. Case rail: case metadata, entity intake, file intake, run log, export controls.
2. Evidence map: Cytoscape graph, legend, layout control, node detail.
3. Findings sheet: confidence, identities, clues, warnings, next pivots, timeline.

Below 1080px the panes stack in reading order: evidence map, findings sheet, case rail. No horizontal overflow. Tap targets are at least 44px.

## Identity Motif

The repeated motif is the file tab and the stamp:

- Section labels sit on small file tabs with a thin top rule.
- Confidence bands appear as an angled stamp outline, not a pill badge.
- Section headers use a double hairline rule, like a typed form.

Reason: the motif belongs to case files and appears consistently without adding ornament to every card.

## Component Rules

- Radius: 2px for inputs and stamps, 4px for panels, 0 for the workspace frame. No pill buttons.
- Shadow: one soft elevation only on the intake sheet and node detail popover. Panels use borders, not floating shadows.
- Icons: custom inline SVG with square terminals and 1.6px strokes. No icon library defaults. Icons only where they clarify an action.
- Empty, loading, and error states are designed for every data surface.
- Focus ring: 2px vermilion offset ring, visible on parchment and graphite.
- Motion: 160ms ease for hover and state changes, 420ms graph layout. Respect `prefers-reduced-motion`.

## Copy Rules

- Indonesian interface copy, specific to investigation work.
- No em dashes, no marketing buzzwords, no invented statistics.
- Confidence language is explicit: Low, Possible, Probable, High, with the numeric score and the reasons that produced it.
- Warnings name the limitation, for example "HIBP_API_KEY belum diset" or "satu domain sumber".

## Anti-Slop Decisions

- No gradient backgrounds, glow, glassmorphism, or neon.
- No background grid or graph-paper texture.
- No fake terminal window.
- No testimonial, logo bar, pricing, or FAQ sections.
- No fabricated metrics. Counts come from the active case.
- No decorative arrows on buttons. The only arrow is the graph edge direction.
