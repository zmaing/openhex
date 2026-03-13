# OpenHex Apple-Pro Layout Spec

## Design Direction

- Tone: Apple-inspired professional tooling
- Keywords: modern, precise, restrained, technology-first, high-end desktop
- Visual principle: dark graphite workspace + soft blue emphasis + layered card surfaces

## Shell Layout

- App window: default `1440 x 920`, minimum `1080 x 720`
- Workspace padding: `12px`
- Column gap: `12px`
- Top toolbar height: `48px`
- Bottom status bar height: `34px`

## Primary Columns

- Left explorer: default `296px`, minimum `248px`
- Center editor: flexible, always dominant visual area
- Right intelligence panel: default `372px`
- Right panel horizontal split mode: recommended width `720px`

## Component Sizes

### Explorer

- Header height: `44px`
- Action button: `28 x 28`
- Path bar height: `34px`
- Tree row height: `28px`
- Tree card radius: `14px`

### Editor Tabs

- Tab top inset: `10px`
- Tab padding: `9px 14px`
- Tab corner radius: `12px`
- Editor pane radius: `18px`

### Status Bar

- Outer radius: `14px`
- Mode pill radius: `10px`
- Mode pill padding: `4px 10px`
- Progress height: `14px`

### Value / Structure Panels

- Panel outer radius: `18px`
- Internal padding: `16px`
- Summary card radius: `14px`
- Metric chip min height: `36px`
- Table row height: `30px`
- Control radius: `12px`

### AI Panel

- Panel outer radius: `18px`
- Internal padding: `14px`
- Composer radius: `16px`
- Mode / model / attach controls height: `26px`
- Primary action button: `36 x 30`
- Transcript cards radius: `12px`

### Dialogs And Settings

- Dialog outer padding: `18px`
- Dialog header card radius: `18px`
- Dialog section card radius: `16px`
- Dialog tabs padding: `8px 14px`
- Form row vertical gap: `10px`
- Validation style: tinted danger surface + danger border, never solid red fill
- Primary dialog action: use default button highlight, not a separate random palette

## Form Language

- Panel: soft rounded rectangle with 1px border
- Input: filled surface with subtle border, never fully flat
- Toggle: segmented / capsule feel instead of IDE-style sharp buttons
- Data display: use mono chips and restrained highlights, not dense boxes
- Accent usage: only for current state, important action, and active selection

## Color Roles

- App background: `#0B0E14`
- Workspace background: `#11161F`
- Surface: `#171D27`
- Elevated surface: `#242E3D`
- Border: `#2E3A4D`
- Primary text: `#F5F7FB`
- Secondary text: `#B4C0D3`
- Accent: `#4DA2FF`

## Interaction Rules

- Hover only changes color and border, no scale-jump
- Selected state uses blue surface, not saturated full-fill everywhere
- Dense data zones keep mono typography, shell UI uses system sans
- Every panel remains readable under split and tabbed modes
