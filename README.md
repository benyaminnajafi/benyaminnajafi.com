# Benyamin Najafi — Senior Product Designer

10+ years of experience leading design teams to build scalable products, from
0→1 startups to market-leading platforms. I drive product discovery and align
cross-functional teams to deliver measurable business outcomes.

**[benyaminnajafi.com](https://benyaminnajafi.com)** ·
[LinkedIn](https://www.linkedin.com/in/benyaminnajafi/) ·
[CV](https://docs.google.com/document/d/1U0G8k3SevXh0VfPRWspxLJo8dXJe-QLG2PvuZFJpFEg/edit?usp=sharing) ·
[ben.najafi@gmail.com](mailto:ben.najafi@gmail.com)

---

## Selected case studies

### Scaling to 4.5M Users: A Data-Driven Platform Redesign

*Product Design Manager · Product Strategy · Crypto & Investment*

Spearheaded a complete platform redesign by establishing a robust, scalable
design system to ensure long-term consistency.

- **Leadership** — led a team of 7 to iterate and enhance the core product experience.
- **Continuous discovery** — targeted user needs by blending qualitative insights
  with quantitative data (Heap, Clarity, PostHog, Metabase).
- **Massive impact** — fueled hyper-growth by scaling the platform's user base
  from 700,000 to over 4.5 million.

### Redefining Grocery Discovery: The Shift to a Vendor-Less Shopping Architecture

*Product Designer · Flow & Research · FMCG (Grocery)*

Led the transition from a restrictive vendor-first model to a unified
"Product-Based" experience by analyzing quantitative funnels (Metabase) and
qualitative behaviors (Hotjar session recordings and usability tests). To reduce
interaction cost, I completely redesigned the core purchase flow — an iterative,
data-driven strategy that drastically shortened the user journey and decision time.

- Shifted user behavior by prioritizing product discovery over store selection.
- Scaled the feature from an experimental MVP to a core flow, increasing
  search-to-cart conversion.
- Established a robust foundation for a vendor-less shopping architecture
  across the platform.

### Orchestrating Delivery at Scale: A Complete Upgrade of a National Fintech Platform

*Product Design Manager · Shipping & Delivery · Fintech*

Managed the entire product development process end-to-end to ensure seamless
delivery from design to deployment. This included handing over finalized designs
to infrastructure, backend, frontend, and QA teams, and supervising the planning,
testing, and release phases. Overseeing the full workflow kept execution
efficient, high-quality, and aligned with both user needs and business objectives.

### Modernization Without Disruption: Rolling Out a Design System on a Live Operation

*Product Designer Lead · Design System & Flow · Retail*

A dual mandate: build the team and modernize the product without disrupting a
live operation.

- Assembled the product design team end-to-end — defining roles, hiring and
  onboarding, and setting rituals (crits, design reviews, async specs) that
  tightened collaboration with Product & Engineering.
- Architected a new design system (tokens, components, accessibility, content
  guidelines) with clear governance and versioning.
- De-risked change by auditing and documenting every current-state flow,
  clarifying ownership, and establishing canonical user journeys, then managing
  a phased migration with compatibility tracking and team training.

### Founding a Fintech: From Rapid Ideation to Market Launch

*Founding Product Designer · MVP Design & Planning · Fintech (Investment)*

Spearheaded the zero-to-one product and service design for a novel melted gold
trading and storage platform, navigating established market limitations and
shaping a strong go-to-market strategy.

- **Accelerated product delivery** — partnered cross-functionally with two 10x
  engineers for rapid ideation, swift decision-making, and seamless implementation.
- **Strategic market positioning** — conducted comprehensive UX audits of all
  competitors to analyze qualitative and quantitative market realities.
- **Scaled team infrastructure** — recruited and onboarded the foundational
  product and engineering team, including senior product designers and frontend
  developers.

---

## About this repository

This repo holds the source of [benyaminnajafi.com](https://benyaminnajafi.com) —
a fully self-contained static build of the site, with every JS module, image,
and font served from this repository rather than a third-party CDN. It is
deployed to GitHub Pages by [a workflow](.github/workflows/deploy.yml) on every
push to `main`.

Run it locally:

```bash
python3 tools/serve.py
```

Then open <http://127.0.0.1:8000/>. It has to be served over HTTP rather than
opened as a `file://` path, because the page loads its bundles as ES modules.

The site is built with React 18 and framer-motion, bundled by Rolldown, with all
CSS inline in `index.html` and no build step of its own. Custom components
(smooth scroll, theme switching, ticker) have their original TypeScript sources
under [`sources/`](sources).

For how the mirror was produced, what it verifies, and the known gaps, see
[docs/MIRROR.md](docs/MIRROR.md).
