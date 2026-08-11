import { defineCollection, z } from "astro:content";
import { glob } from "astro/loaders";

/**
 * The shape of a case study.
 *
 * This is the contract the future admin panel writes against. Because it is a
 * schema and not a convention, a bad edit fails the build instead of shipping a
 * broken page — which is the whole reason a CMS can be handed to someone who is
 * not going to read the components.
 *
 * Files live in content/ at the repo root rather than under src/, so they stay
 * obvious to anyone opening the repository and are not mistaken for code.
 */
const caseStudies = defineCollection({
  loader: glob({ pattern: "*.md", base: "./content/case-studies" }),
  schema: ({ image }) =>
    z.object({
      /** Position on the page. Sparse (10, 20, 30…) so one can be moved
       *  between two others without renumbering the rest. */
      order: z.number().int().positive(),
      title: z.string().min(1),
      role: z.string().min(1),
      expertise: z.string().min(1),
      industry: z.string().min(1),
      /** The plain lead-in before the link. One published case study has none,
       *  so it is optional — but it must never carry the link text itself. */
      caption: z.string().default(""),
      linkLabel: z.string().min(1),
      linkUrl: z.string().url(),
      /** The slide backdrop. Taken from the token's real declaration, never
       *  from the stale fallback Framer wrote beside it. */
      accent: z.string().regex(/^#[0-9a-f]{6}$/, "expected a hex colour like #ffde88"),
      /** Carousel slides, in order. The first is the frame shown at rest. */
      images: z.array(image()).min(1).max(12),
      /** The record id this came from, kept so an extraction can be traced
       *  back to the Framer payload while site/ still exists. */
      framerId: z.string().optional(),
    }),
});

export const collections = { caseStudies };
