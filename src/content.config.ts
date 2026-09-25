import { defineCollection } from "astro:content";
import { file } from "astro/loaders";
import { z } from "astro/zod";

const projects = defineCollection({
  loader: file("src/data/projects.yaml"),
  schema: z
    .object({
      // The file loader reads it as the entry id; declared so .strict() accepts it.
      id: z.string(),
      title: z.string(),
      // Language of the title, when it is not English.
      lang: z.string().min(1).optional(),
      summary: z.string(),
      links: z
        .object({
          live: z.url({ protocol: /^https$/ }).optional(),
          source: z.url({ protocol: /^https$/ }).optional(),
        })
        .refine((links) => links.live || links.source, "needs a live or a source link"),
      // Lower comes first.
      order: z.number().int(),
    })
    .strict(),
});

export const collections = { projects };
