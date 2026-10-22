---
name: "adhoc-frontend-design-quality"
description: "Single end-to-end ruleset for designing, implementing, reviewing, and repairing distinctive production frontend UI that avoids generic AI patterns. Use for websites, product interfaces, dashboards, components, design systems, responsive layouts, UI audits, and frontend polish."
---

# Frontend Design Quality

This is a Claude Code mirror of `adhoc_frontend_design_quality` from `.agents/skills/`.
Original source: `.agents/skills/adhoc_frontend_design_quality/SKILL.md`
Skill class: `adhoc`

Use this skill as one complete operating system for frontend design work. It covers discovery, information architecture, visual direction, design tokens, component behavior, implementation, repair, and verification.

The goal is not novelty for its own sake. The goal is an interface that:

- makes its purpose and primary action obvious;
- expresses a specific, defensible visual point of view;
- behaves like production software, not a static mockup;
- remains accessible, responsive, maintainable, and fast;
- cannot be mistaken for an unedited AI-generated template.

## Instruction Priority

Apply rules in this order:

1. User instructions and confirmed product requirements
2. Repository `AGENTS.md` and project-specific guidance
3. Existing brand, design system, and established product conventions
4. Accessibility, usability, correctness, and security
5. This skill's design-quality rules
6. Personal aesthetic preference

Do not make an interface less usable merely to make it more distinctive. Do not discard a coherent existing design system to impose a new style.

## Operating Modes

Infer the mode from the request. State the mode only when it helps coordination.

### Build

Use when creating a page, component, flow, prototype, or design system.

- Inspect the project before choosing a direction.
- Define the design contract before styling.
- Implement working behavior and applicable states.
- Verify the result in the running interface when practical.

### Repair

Use when the interface exists but feels generic, inconsistent, unattractive, or unfinished.

- Preserve working content, behavior, and framework unless the user asks for replacement.
- Diagnose the three highest-impact causes first.
- Fix system-level causes before polishing isolated components.
- Prefer targeted refactoring over regenerating the whole interface.

### Review

Use when the user asks for critique, diagnosis, audit, or recommendations.

- Inspect and report; do not modify code unless the user also asks for changes.
- Ground every finding in visible behavior, code evidence, or a stated requirement.
- Prioritize a short fix sequence over a long inventory of taste opinions.

## Core Principles

1. **Intent before aesthetics.** Know who the interface serves, what they need to do, and what must be understood first.
2. **Hierarchy before decoration.** Establish narrative order, density, and primary actions before cards, gradients, illustrations, or motion.
3. **One direction, fully executed.** Choose one coherent base language. Do not mix unrelated styles as a substitute for judgment.
4. **Rules must be executable.** Replace vague adjectives with tokens, layout behavior, component states, and forbidden defaults.
5. **Constraints create identity.** A short, enforced avoid-list is as important as the positive specification.
6. **Real content drives design.** Use representative copy, data, labels, and edge cases; do not judge only a polished hero.
7. **Components are behavior.** Default appearance alone is incomplete. Include relevant focus, hover, active, selected, loading, empty, error, success, and disabled behavior.
8. **Responsive means adaptation.** Reorder, regroup, simplify, and change interaction patterns; do not merely shrink the desktop layout.
9. **Accessibility is a design input.** Contrast, focus, semantics, motion, and touch targets shape the visual system from the start.
10. **Verification beats confidence.** Run the interface, inspect it at multiple widths, use the keyboard, and check critical states.

## Phase 0: Inspect Before Designing

Before asking questions or editing code, inspect available local evidence:

- README, product notes, specifications, and project snapshots
- package manifests and framework configuration
- route and component structure
- existing design-system components and UI libraries
- global styles, CSS variables, theme files, and utility configuration
- typography, icon, image, logo, and brand assets
- representative screens and existing responsive behavior
- tests, lint rules, accessibility tooling, and browser support

Record what is **confirmed**, what is **inferred**, and what remains **unknown**. Do not present guesses as product facts.

### Minimum Context

Proceed only when these are known or safely inferable:

- target users and their context;
- the main job or outcome;
- primary action and content priority;
- product or brand personality;
- technical constraints and existing stack;
- required devices, browsers, and accessibility level;
- whether the work should preserve or intentionally change the existing visual language.

Ask at most three concise questions only when a missing answer would materially change the design. Prefer questions about users, primary task, and brand direction over questions about decorative preferences.

## Phase 1: Create the Design Contract

Before implementation, establish a compact contract. It may remain internal unless the user asks to review it.

```markdown
## Design Contract

### Users and task
- Audience:
- Situation:
- Primary job:
- Primary action:

### Content hierarchy
1. First thing users must understand
2. Proof or context needed next
3. Primary action
4. Secondary information

### Visual direction
- Direction name:
- Three traits:
- Signature move:
- Anti-reference:

### System
- Palette roles:
- Type roles:
- Spacing rhythm:
- Corner/border/shadow language:
- Motion language:

### Component behavior
- Core components:
- Required states:
- Responsive transformations:

### Drift rules
- Must use:
- Must avoid:

### Acceptance gates
- Functional:
- Visual:
- Responsive:
- Accessibility:
- Performance:
```

### Contract Rules

- Use a named direction plus concrete rules; never rely on `modern`, `clean`, `premium`, `sleek`, or `futuristic` alone.
- Define one memorable signature move: a composition, typography treatment, navigation behavior, data treatment, illustration language, or interaction pattern.
- The signature move must reinforce meaning or brand. A decorative gradient does not qualify by itself.
- List five to ten drift rules that can be checked in code or in the browser.
- When positive and negative rules conflict, usability and accessibility win, then explicit prohibitions, then aesthetic preferences.
- Treat examples as evidence, not authority. If an example contradicts the contract, follow the contract.

## Phase 2: Plan Information Architecture and Content

Do not start by styling components. First define the page's narrative and task flow.

### Universal Hierarchy Rules

- Each page has one dominant purpose.
- Each viewport or section has one visually dominant action or focal point.
- The first viewport must answer: where am I, what is this, why does it matter, and what can I do next?
- Put the most decision-relevant content first, not the most decorative content.
- Group by user intent, not database schema or backend ownership.
- Use progressive disclosure for complexity; do not hide essential actions.
- Remove headings, intros, badges, and captions that repeat the same information.
- Prefer specific labels and real examples over generic filler.
- Design long names, missing values, validation failures, and empty collections from the start.

### Marketing and Landing Pages

- Build a clear sequence: proposition, evidence, mechanism, objections, action.
- Use one primary call to action and a genuinely secondary path.
- Do not invent customer logos, metrics, awards, testimonials, or claims.
- Avoid repeating the same CTA after every shallow section.
- Show the product or outcome with meaningful evidence, not an abstract dashboard mockup that conveys nothing.

### Product Interfaces and Dashboards

- Start from user tasks, decisions, and exceptions—not KPI cards.
- Give primary work more space than navigation chrome.
- Use cards only for true grouped objects or independent modules.
- Prefer tables, lists, timelines, split panes, or direct layouts when they fit the data better.
- Show units, time ranges, data freshness, comparison basis, and empty/error meaning.
- Charts must answer a question; decorative sparklines are not evidence.

### Editorial and Content Experiences

- Let typography, pacing, image treatment, and section rhythm carry the identity.
- Use readable line lengths and distinct hierarchy for title, standfirst, metadata, body, captions, and pull elements.
- Do not turn every paragraph into a card or callout.
- Preserve reading flow on narrow screens.

### Forms and Transactional Flows

- Group fields by user decision, not by implementation model.
- Make required information and consequences clear before submission.
- Use specific verb-object actions.
- Validate at the appropriate time and provide recovery steps.
- Preserve user input after errors.

## Phase 3: Choose One Visual Direction

Choose the direction that supports the product context. Do not choose based only on what looks striking in a screenshot.

Use one base direction. A secondary motif may support it, but must not introduce a competing component, radius, shadow, typography, or motion language.

| Direction | Best fit | Defining moves | Default avoid list | Main risk |
|---|---|---|---|---|
| Neo-brutalist | Creative campaigns, expressive tools, youth or countercultural brands | Heavy borders, hard offset shadows, sharp corners, direct type, high contrast | Soft shadows, glass, timid pastels, rounded-card softness, slow fades | Noise, fatigue, and weak hierarchy |
| Editorial | Publishing, portfolios, cultural brands, premium storytelling | Distinct display typography, restrained palette, fine rules, asymmetry, generous pacing | Card grids, pill stacks, loud accent soup, heavy shadows, centered-everything layouts | Beautiful but impractical low-contrast text |
| Neumorphic | Small tactile controls, calm device-like surfaces, limited decorative systems | One surface family, consistent light direction, raised/recessed depth | Hard shadows, arbitrary borders, multiple light sources, high-density use | Poor affordance and contrast; never rely on shadow alone |
| Bento | Modular overviews, portfolios, feature summaries, high-level dashboards | Deliberately varied spans, clear visual priority, consistent gaps, responsive reordering | Equal-sized repeated cards, arbitrary spans, overcrowded modules | Becoming the same generic rounded card grid it was meant to avoid |
| Corporate clean | Enterprise workflows, admin tools, B2B products | Readability, predictable structure, compact density, restrained depth, brand-specific details | Default-blue sameness, excessive whitespace, cartoon icons, generic three-card sections | Safe but indistinguishable SaaS UI |
| Minimalist flat | Art, portfolios, focused products, content-first interfaces | Flat color, strong typography, crisp structure, generous space, minimal effects | Shadows, gradients, mixed radii, unnecessary ornament, weak contrast | Empty minimalism without enough hierarchy or affordance |

### Direction-Specific Guardrails

#### Neo-brutalist

- Use borders and hard shadows consistently; random thickness changes look accidental.
- Make pressed displacement match the apparent shadow depth when using physical press behavior.
- Keep color changes decisive and transitions short.
- Use semantic HTML and strong focus styles; visual aggression does not excuse interaction ambiguity.
- Reduce density on mobile so borders and shadows do not consume the content area.

#### Editorial

- Use a deliberate display/body pairing with clear roles.
- Prefer soft black and warm or tinted surfaces unless brand rules specify otherwise.
- Use thin rules, whitespace, and composition for grouping rather than card containers.
- Validate all low-opacity text; decorative delicacy often fails contrast.
- Keep body measure and line height comfortable even when headlines are dramatic.

#### Neumorphic

- Use sparingly. Do not use as the sole language for critical forms, navigation, or dense dashboards.
- Maintain a single, physically consistent light direction.
- Add visible focus rings, labels, and sufficient contrast; shadow alone cannot communicate state.
- Raised controls become recessed when activated; do not combine that model with unrelated floating translation.
- If accessibility requires borders or stronger contrast, add them or select another direction.

#### Bento

- Assign size by information priority. Large cards are not random decoration.
- Use no more spans than needed to create a clear first-read path.
- On small screens, linearize by priority and remove meaningless empty grid areas.
- Do not make every section a bento grid. Use it where modular comparison helps.
- Keep card internals quiet enough that the composition remains the main visual system.

#### Corporate clean

- Find a brand-specific differentiator: type, density, navigation model, illustration, data treatment, or distinctive accent use.
- Do not use default blue simply because the product is B2B.
- Prefer readable compactness to oversized empty dashboards.
- Use subtle radii and shadows only where elevation or grouping is real.
- Make complex states, permissions, errors, and data provenance first-class design elements.

#### Minimalist flat

- Remove effects, not information.
- Use typography, scale, space, border, and flat color to create hierarchy.
- Choose a coherent corner rule; do not mix sharp cards, rounded inputs, and pill buttons without a reason.
- Keep interactions visible through inversion, underline, border, or color—not invisible minimalism.
- If the page feels empty, improve content structure before adding decoration.

## Phase 4: Define the Token System

Use semantic tokens. Avoid scattering raw values through components.

### Required Token Families

```css
:root {
  /* Color roles */
  --color-canvas: ...;
  --color-surface: ...;
  --color-surface-strong: ...;
  --color-text: ...;
  --color-text-muted: ...;
  --color-border: ...;
  --color-accent: ...;
  --color-on-accent: ...;
  --color-success: ...;
  --color-warning: ...;
  --color-danger: ...;

  /* Typography roles */
  --font-display: ...;
  --font-body: ...;
  --font-mono: ...;
  --text-xs: ...;
  --text-sm: ...;
  --text-body: ...;
  --text-lead: ...;
  --text-title: ...;
  --text-display: ...;

  /* Spatial and shape roles */
  --space-1: ...;
  --space-2: ...;
  --space-3: ...;
  --space-4: ...;
  --space-6: ...;
  --space-8: ...;
  --radius-control: ...;
  --radius-surface: ...;
  --border-subtle: ...;
  --border-strong: ...;

  /* Depth and motion roles */
  --shadow-raised: ...;
  --shadow-overlay: ...;
  --duration-fast: ...;
  --duration-normal: ...;
  --ease-standard: ...;
  --ease-exit: ...;
}
```

Adapt names to the existing project conventions. Do not introduce duplicate token systems.

### Color Rules

- Start with roles, not a pile of swatches.
- Use one dominant neutral family, one main accent family, and semantic status colors unless the direction requires more.
- Tint neutral surfaces toward the brand when appropriate.
- Do not default to pure black or white, but allow them when the chosen direction intentionally depends on them.
- Never assume a palette is accessible because it looks strong. Test actual foreground/background pairs.
- Normal text should meet WCAG AA contrast of 4.5:1; large text and meaningful UI graphics should meet 3:1.
- Do not place generic gray text on a colored background. Derive a compatible darker or lighter tone from that background family.
- Do not use color alone to communicate error, selection, status, or chart series.
- Limit gradients to cases where they are part of the selected direction and carry structural or brand meaning.

### Typography Rules

- Preserve an existing licensed brand type system when present.
- For a new identity, choose typefaces because their shape supports the tone, not because they are the model's default.
- Do not replace an established accessible product font merely to appear distinctive.
- Use no more type families than necessary; usually display plus body is enough.
- Use monospaced text for code, identifiers, or intentionally specific character—not as automatic shorthand for “tech”.
- Create hierarchy through size, weight, width, line height, spacing, and placement; color alone is insufficient.
- Use fluid type where useful, with bounded values such as `clamp()`.
- Keep body text generally at 16px or larger and line length around 45–75 characters.
- Avoid very light weights for small text.
- Use tabular numerals for aligned metrics and tables.
- Load only required font weights and provide robust fallbacks.

### Spacing and Grid Rules

- Use a consistent base rhythm, commonly 4px, but preserve the project's existing scale.
- Name spacing by role or keep one clear numeric scale; do not use random one-off gaps everywhere.
- Create rhythm with tight internal groups and generous separation between unrelated groups.
- Do not apply identical padding to every container.
- Use grid for two-dimensional composition and flex for one-dimensional alignment.
- Use container queries when component behavior depends on its container rather than the viewport.
- Break the grid only to reinforce hierarchy, not to simulate creativity.

### Radius, Border, and Shadow Rules

- Define at most a few intentional radius roles.
- Pill shapes are for compact controls, tags, status, and true capsules—not every button or surface.
- Borders communicate grouping, emphasis, or state; do not add them as decorative noise.
- Shadows communicate elevation or physical style. If nothing is elevated, prefer no shadow.
- Use one coherent light model. Random shadow directions make the interface feel assembled from templates.
- Do not nest elevated cards inside elevated cards.

### Motion Rules

- Motion explains state, continuity, hierarchy, or cause and effect.
- Prefer one strong orchestrated moment over animations on every element.
- Keep control feedback roughly 120–250ms and larger transitions roughly 250–500ms unless the direction specifies otherwise.
- Prefer `transform` and `opacity`; avoid animating layout properties when possible.
- Use natural deceleration. Avoid bounce and elastic easing unless the product's established motion language explicitly calls for it.
- Respect `prefers-reduced-motion` and provide a no-motion equivalent.
- Never require motion to understand content or complete a task.
- Avoid continuous decorative movement, cursor-following effects, or scroll hijacking unless explicitly requested and justified.

## Phase 5: Build a Coherent Component Language

Create reusable components when repetition or behavior warrants them. Do not abstract one-off markup prematurely.

### Every Interactive Component

Implement the applicable states:

- default
- hover for pointer devices
- focus-visible for keyboard users
- active or pressed
- selected or current
- disabled
- loading
- error
- success

Not every component needs every state, but every applicable state must be intentional.

### Buttons and Links

- Keep one primary action style, one secondary style, and a quiet/tertiary treatment.
- Use verb-object labels such as `Save changes`, not `Submit` or `OK`.
- Links navigate; buttons perform actions.
- Do not make all buttons primary.
- Maintain at least 44×44px touch targets, even if the visible control is smaller.
- Loading must preserve layout and prevent accidental duplicate actions.
- Destructive actions must state the consequence and support undo when practical.

### Navigation

- Show current location and clear wayfinding.
- Preserve essential destinations on mobile; adapt the pattern instead of amputating features.
- Keep tab order logical.
- Use native links and buttons before custom clickable containers.
- Provide skip navigation for repeated large navigation regions where appropriate.

### Forms

- Use visible labels; placeholders are examples, not labels.
- Connect help and error text programmatically.
- Validate on blur or submit as appropriate, not destructively on every keystroke.
- Explain format and recovery in plain language.
- Do not clear valid input after an error.
- Mark required fields consistently.
- Use correct input types, autocomplete attributes, and input modes.

### Cards and Surfaces

- Use a card only when the content is a discrete object, action group, or independent module.
- Do not wrap headings, paragraphs, and every section in identical rounded rectangles.
- Never nest cards merely to create hierarchy.
- Use layout, rules, spacing, or background shifts when they communicate structure better.
- A clickable card needs a clear target, focus behavior, and no conflicting nested interactions.

### Tables and Dense Data

- Use real table semantics for tabular data.
- Keep headers visible when it helps orientation.
- Align numbers consistently and include units.
- Design sorting, filtering, selection, pagination, empty, loading, stale, and error states.
- On narrow screens, choose deliberate reflow, priority columns, or horizontal containment; do not silently remove critical information.

### Charts and Metrics

- State the question the chart answers.
- Label axes, units, time range, comparison, and source or freshness where relevant.
- Use direct labels when possible.
- Ensure series remain distinguishable without color alone.
- Do not add a sparkline, donut, or gradient area chart solely to make a card look sophisticated.
- Avoid oversized numbers without context, units, or comparison basis.

### Empty, Loading, Error, and Success States

- Empty states explain what belongs here, why it matters, and the next action.
- Skeletons should resemble the expected content and avoid layout shift.
- Long operations set expectations or show progress.
- Errors explain what happened, why if known, and how to recover.
- Success confirms the action and what happens next.
- Do not use humor when the user is blocked or has lost work.

### Overlays

- Use modals only when focus must be isolated or the action cannot remain in context.
- Prefer inline expansion, drawers, popovers, or dedicated pages when they better preserve context.
- Use native `dialog` and popover behavior when supported and appropriate.
- Trap focus correctly, support Escape, restore focus, and prevent interaction with the background.

## Phase 6: Apply the Anti-Slop Filter

The following are forbidden by default. Use one only when the design contract gives it a clear role and the result remains coherent.

### Visual Defaults to Reject

- blue-purple gradient as automatic “technology” branding
- cyan-on-dark neon dashboards with glow everywhere
- gradient text for headings or metrics
- floating blurred color orbs behind the hero
- glassmorphism applied to every surface
- generic white cards with large radii, faint borders, and soft shadows repeated across the page
- identical three-column feature grids repeated section after section
- icon in a rounded square above every heading
- excessive pills for navigation, labels, actions, and decorative copy
- enormous radius values applied indiscriminately
- centered text and centered controls in every section
- a hero composed of eyebrow, huge vague headline, two pill buttons, and decorative mock dashboard without product evidence
- big metric plus small label repeated without context
- decorative sparklines, fake charts, or meaningless data visualization
- card-inside-card hierarchy
- random one-off gradients, shadows, and radii that drift from the selected direction
- overuse of pure black, pure white, or default gray without intentional palette logic
- arbitrary emoji or mixed icon families as visual decoration

### Content Defaults to Reject

- generic claims such as `Revolutionize your workflow`, `Unlock the future`, or `Built for teams that move fast` without evidence
- fake testimonials, companies, awards, user counts, or revenue metrics
- repeated introduction copy that restates the heading
- vague buttons such as `Learn more`, `Get started`, or `Submit` when a specific outcome is available
- labels that expose implementation terms instead of the user's mental model
- empty states that say only `No data`
- error messages that say only `Something went wrong`

### Interaction Defaults to Reject

- hover animation without keyboard focus treatment
- removing outlines without an accessible replacement
- every element lifting and scaling on hover
- bounce, elastic, or gratuitous spring motion
- animated width, height, margin, or padding that causes jank
- hidden gesture-only actions without a visible alternative
- critical actions available only on hover
- animation used to disguise slow or incomplete behavior

### Code Signals of Template Drift

Investigate when several of these appear repeatedly without a design contract:

- the same `rounded-xl/2xl + border + shadow-sm + p-6` combination across unrelated components
- `grid-cols-3 gap-6` used as the default section pattern throughout the page
- arbitrary raw color values mixed with semantic tokens
- repeated gradient utilities in headings, buttons, charts, and backgrounds
- widespread `transition-all`
- dozens of one-off spacing or z-index values
- duplicated card, button, or input markup rather than a shared behavior pattern
- icon-only controls without names
- `outline: none` without `:focus-visible` treatment
- absolute positioning used to force the desktop screenshot while breaking flow

Do not fail code merely because one suspicious class appears. Judge repetition, context, and whether the contract explains it.

## Phase 7: Responsive Adaptation

Design mobile, intermediate, and wide layouts as related but distinct compositions.

### Required Checks

- Test at least one narrow phone width, one intermediate/tablet width, and one desktop width.
- Add a very wide check when the product commonly runs on large monitors.
- Check landscape and software-keyboard behavior for important mobile forms.
- Ensure no unintended horizontal page scroll.
- Ensure text does not clip at 200% zoom.

### Adaptation Rules

- Reorder by task priority, not source order convenience.
- Convert multi-column comparisons into deliberate stacks, scrollers, or priority views.
- Replace hover-dependent behavior on touch devices.
- Keep critical actions reachable and stable.
- Avoid hiding essential functionality to make the layout fit.
- Use sticky UI only when it preserves context and does not consume too much small-screen space.
- Let long localized text wrap without overlapping controls.
- Respect safe-area insets when using edge-to-edge layouts.
- Give media explicit dimensions or aspect ratios to prevent layout shift.

## Phase 8: Accessibility Gates

Accessibility is a release requirement, not a final polish pass.

### Semantics and Keyboard

- Use semantic landmarks, headings, buttons, links, lists, tables, and form controls.
- Maintain a logical heading outline.
- Ensure every function is available by keyboard.
- Show a visible, high-contrast `:focus-visible` indicator.
- Keep focus order aligned with visual and task order.
- Manage focus after dialogs, route changes, deletions, and dynamic insertions.
- Use ARIA only when native semantics are insufficient.

### Visual Access

- Meet WCAG AA contrast for text and meaningful UI graphics.
- Do not use opacity to create “refined” text that becomes unreadable.
- Do not encode state with color alone.
- Support zoom, text resizing, and reflow.
- Keep touch targets at least 44×44px where practical.
- Use alt text for informative images and empty alt text for purely decorative images.

### Motion and Time

- Respect reduced motion.
- Avoid flashing and rapid high-contrast animation.
- Provide enough time or user control for timed interactions.
- Announce meaningful async status changes when screen-reader users need them.

### Style-Specific Accessibility Warnings

- Neo-brutalism: high contrast is helpful, but dense borders and competing accents can destroy hierarchy.
- Editorial: muted opacity and fine rules commonly fail contrast.
- Neumorphism: low contrast and shadow-only affordances are high risk.
- Bento: visual order can differ from DOM order; keep reading and focus order logical.
- Corporate clean: gray-on-blue and low-emphasis metadata can fail contrast.
- Minimalist flat: accent colors may not support white text; test every pairing.

## Phase 9: Frontend Implementation Quality

### Preserve the Project

- Reuse the existing framework, routing, component library, tokens, and conventions.
- Do not add a dependency when existing CSS, native platform features, or current libraries solve the problem well.
- Do not replace a component library wholesale for aesthetic reasons.
- Keep the smallest implementation that fully supports the design contract.

### Component Design

- Keep components focused and readable.
- Extract repeated behavior, not every repeated wrapper.
- Prefer explicit variants over uncontrolled class strings spread across call sites.
- Keep state ownership close to the interaction that needs it.
- Avoid giant components containing unrelated page sections and business logic.
- Keep visual variants aligned with semantic meaning.

### CSS and Tokens

- Use cascade layers, modules, scoped styles, or the project's established method predictably.
- Prefer logical properties when supporting different writing directions matters.
- Avoid global selectors that accidentally restyle third-party or unrelated UI.
- Remove dead styles and contradictory utilities.
- Avoid `!important` except for a documented boundary problem.
- If using utilities, promote repeated visual rules into tokens, components, or variants.

### Performance

- Prevent layout shift with explicit media dimensions and stable loading states.
- Optimize images and use responsive sources.
- Lazy-load off-screen heavy media, not above-the-fold primary content.
- Load only required font files and weights; use `font-display` deliberately.
- Keep animation on compositor-friendly properties.
- Avoid client JavaScript for behavior available through HTML or CSS.
- Preserve the project's performance budget and verify critical routes.

### Reliability

- No console errors or warnings caused by the change.
- No missing keys, hydration mismatches, broken routes, or focus traps.
- No TypeScript escapes or ignored errors added for convenience.
- No production debug logs, dead code, or unrelated refactors.
- Critical states work with slow, failed, empty, and long-content conditions.

## Phase 10: Build Workflow

Follow this order for new work:

1. Inspect project context and existing design language.
2. Establish users, task, content hierarchy, and constraints.
3. Write the compact design contract and avoid list.
4. Outline page regions and component boundaries before detailed styling.
5. Define or extend semantic tokens.
6. Build the structural layout with representative content.
7. Create one exemplar component that proves the visual and interaction language.
8. Implement the rest section by section, reusing the language rather than copying markup blindly.
9. Add all applicable interaction, async, empty, error, and disabled states.
10. Adapt mobile and intermediate layouts.
11. Verify accessibility, performance, build quality, and visual consistency.
12. Fix root causes, then perform a final polish pass.

Do not generate a complex product interface in one undifferentiated block and call it finished.

## Phase 11: Repair Workflow

When an existing interface looks generic or bad, diagnose instead of asking for “prettier.”

### Diagnose the Top Three Causes

Classify each problem:

- unclear purpose or information architecture
- weak first-viewport hierarchy
- generic or contradictory visual direction
- inconsistent tokens
- over-cardification
- weak typography
- timid or incoherent color
- missing component states
- broken responsive adaptation
- inaccessible interactions or contrast
- fake, vague, or repetitive content
- excessive or meaningless motion
- implementation drift and duplicated patterns

### Fix in This Order

1. User task, content, and information architecture
2. Page structure and visual hierarchy
3. Token system and chosen direction
4. Component grammar and reuse
5. Interaction and async states
6. Responsive behavior
7. Accessibility and performance defects
8. Fine visual polish

Do not start by changing colors, adding gradients, or increasing shadows when structure is the problem.

### Preserve Value

- Keep real content, validated information architecture, and working interactions.
- Preserve brand recognition unless the user requests a rebrand.
- Repair shared tokens or component variants before patching dozens of instances.
- Do not regenerate the whole application when focused changes will solve the problem.

## Phase 12: Source-Contradiction Guard

Design references, generated prompts, component libraries, and copied examples may contradict themselves. Detect this before implementation.

- Establish one canonical contract for palette, typography, radii, border, shadow, motion, and forbidden patterns.
- Check every imported snippet, global style, helper class, and component variant against it.
- A snippet labelled for the chosen style is not automatically valid.
- Remove unused helpers that introduce a competing visual language.
- Do not ship generic gradient, frosted, glow, or animation helpers in a flat or anti-gradient direction merely because an export included them.
- Do not trust a palette's accessibility label; test actual color pairs and states.
- When the source spec conflicts with accessibility, correct the spec or select another direction.
- Document intentional exceptions so future agents do not “normalize” them away.

## Phase 13: Review Rubric

Use this rubric for audits and final verification. Scores help prioritize; hard gates still determine release readiness.

| Dimension | Weight | Questions |
|---|---:|---|
| Purpose and hierarchy | 20 | Is the page goal obvious? Is the primary action clear? Does information arrive in the right order? |
| Direction and distinctiveness | 15 | Is there one coherent visual point of view and a memorable, contextual signature? |
| System consistency | 15 | Are color, type, spacing, radii, borders, shadows, and motion tokenized and consistent? |
| Components and states | 15 | Do components have clear semantics, variants, and applicable interaction/async states? |
| Responsive adaptation | 10 | Does the composition adapt intelligently across widths and input types? |
| Accessibility | 15 | Do semantics, keyboard, focus, contrast, zoom, motion, and labels meet the required standard? |
| Implementation quality | 10 | Is the code maintainable, reliable, dependency-conscious, and performant? |

### Hard Gates

The result is not ready regardless of score when any of these are true:

- the primary user task is unclear or cannot be completed;
- the build, route, or critical interaction is broken;
- keyboard users cannot complete the critical flow;
- visible focus is missing from critical controls;
- required contrast fails without an approved exception;
- the main layout breaks or scrolls unintentionally at a required width;
- a critical async flow lacks loading, error, or recovery behavior;
- the implemented UI materially contradicts the chosen design contract;
- fake evidence or invented business claims are presented as real;
- source examples introduced forbidden or contradictory style helpers.

### Slop Risk Verdict

Use one of these verdicts:

- **Low:** clear intent, coherent system, contextual signature, complete states, and verified behavior.
- **Medium:** usable and consistent, but several sections still rely on familiar template patterns or generic content.
- **High:** vague direction, weak hierarchy, repeated default components, missing states, or no meaningful verification.

## Phase 14: Verification Matrix

Verify in proportion to the task and risk.

### Functional

- critical tasks complete successfully
- links, buttons, forms, menus, dialogs, tabs, and filters behave correctly
- loading, empty, error, success, disabled, and permission states work where relevant
- back, refresh, deep links, and route transitions preserve expected behavior

### Visual

- hierarchy survives the squint test
- the selected direction is recognizable without reading its name
- tokens and component treatments do not drift
- content aligns optically, not just mathematically
- real long and short content does not break composition
- no accidental card nesting, orphaned headings, or decorative noise remains

### Responsive

- narrow phone, intermediate/tablet, and desktop inspected
- no unintended horizontal scroll
- touch targets and mobile navigation work
- critical content remains available
- layout order matches task priority and DOM order remains logical

### Accessibility

- keyboard-only walkthrough completed
- focus visibility and focus return verified
- contrast checked on actual token combinations and states
- labels, names, roles, status announcements, and alt text verified
- reduced motion checked
- zoom and text reflow checked when material

### Engineering

- relevant lint, typecheck, tests, and production build pass
- no new console errors or warnings
- no unnecessary dependencies or unrelated changes
- no obvious layout shift or animation jank
- responsive images and font loading are appropriate

### Visual Evidence

When browser tooling is available and the task changes visible UI:

- run the app;
- inspect the actual page, not only source code;
- capture or compare representative widths when useful;
- interact with critical controls;
- inspect the console;
- repeat after fixes.

Do not claim visual quality was verified if the interface was never rendered.

## Phase 15: Delivery Format

For build or repair work, report:

1. the outcome and design direction;
2. the important files or components changed;
3. what was verified and at which representative widths;
4. any remaining limitation or user decision.

For reviews, report:

1. slop-risk verdict;
2. top three findings in priority order;
3. evidence for each finding;
4. the smallest high-impact fix sequence;
5. hard-gate failures, if any.

Keep delivery concise. The quality belongs in the artifact, not in a long self-congratulatory explanation.

## Final Self-Check

Before declaring completion, confirm:

- [ ] Users, task, primary action, and content hierarchy are understood.
- [ ] One visual direction and one signature move are defined.
- [ ] Five to ten concrete drift rules exist.
- [ ] Vague adjectives were translated into executable rules.
- [ ] The page is not built from repeated generic cards by default.
- [ ] Real or representative content was used without inventing claims.
- [ ] Palette, typography, spacing, radius, border, shadow, and motion are coherent.
- [ ] Imported examples do not contradict the design contract.
- [ ] All applicable component states are implemented.
- [ ] Mobile behavior is an adaptation, not a compressed desktop layout.
- [ ] Keyboard, focus, semantics, labels, contrast, zoom, and reduced motion are addressed.
- [ ] Critical empty, loading, error, and recovery states work.
- [ ] The project stack and conventions were preserved.
- [ ] No unnecessary dependency or unrelated refactor was introduced.
- [ ] The interface was rendered and inspected when possible.
- [ ] Relevant tests, checks, and builds pass.
- [ ] The result would not immediately read as an unedited AI template.

## Research Basis

This ruleset synthesizes the StyleKit article and every unique link in its main article body, while correcting contradictions found between some linked style prompts, exported helpers, and accessibility results:

- [Avoid AI slop](https://www.stylekit.top/en/avoid-ai-slop)
- [AI web design workflow](https://www.stylekit.top/en/ai-web-design)
- [AI frontend design workflow](https://www.stylekit.top/en/ai-frontend-design)
- [AI-generated website repair](https://www.stylekit.top/en/ai-generated-website-fix)
- [UI style catalog](https://www.stylekit.top/en/styles)
- [UI prompt library](https://www.stylekit.top/en/ui-prompts)
- [Neo-brutalist](https://www.stylekit.top/en/styles/neo-brutalist)
- [Editorial](https://www.stylekit.top/en/styles/editorial)
- [Neumorphism](https://www.stylekit.top/en/styles/neumorphism)
- [Bento grid](https://www.stylekit.top/en/styles/bento-grid)
- [Corporate clean](https://www.stylekit.top/en/styles/corporate-clean)
- [Minimalist flat](https://www.stylekit.top/en/styles/minimalist-flat)
