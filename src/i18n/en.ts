/** Everything the page says, in English, the default language. See `texts.ts`. */

import type { Texts } from "./texts.ts";

export const en: Texts = {
  language: "en",
  ogLocale: "en_US",
  title: "Alejandro Brunacci · Senior Software Engineer (Python, Data, GenAI)",
  description:
    "Alejandro Brunacci, Senior Software Engineer. APIs in Python and FastAPI, data pipelines on Databricks and GenAI, end to end. Available for remote contract work.",
  share: {
    title: "Alejandro Brunacci · Senior Software Engineer",
    description:
      "Available for contract and consulting work. 10+ years. Web products end to end: APIs, data pipelines and GenAI in Python. Remote, with US time zone overlap.",
    image: "og-image.png",
    imageAlt:
      "Alejandro Brunacci, Senior Software Engineer. I build web products end to end: APIs, data pipelines and GenAI in Python, with the frontend to ship them.",
  },
  languageGroup: "Language",

  availability: "Available for contract and consulting work",
  role: "Senior Software Engineer",
  tagline: {
    before: "I build web products end to end: ",
    mark: "APIs, data pipelines and GenAI",
    after: " in Python, with the frontend to ship them.",
  },
  location: ["Argentina", "Remote", "US time zone overlap"],
  emailMe: "Email me",
  profile: { before: "", after: " profile" },
  technologies: "Technologies",

  about: {
    eyebrow: "Who I am",
    title: "About",
    lead: "I make backends faster, more scalable and more robust: performance and process optimization is what I specialize in.",
    points: [
      "Backends for GenAI and data products across Fintech, AgTech and event management systems.",
      "Python, microservices architecture and cloud technologies, from MVPs to monolith-to-microservices migrations.",
      "Led multidisciplinary teams of up to 10 people.",
      "Over 10 years of experience in the IT industry. Available for remote contract and consulting work.",
    ],
  },

  projects: {
    eyebrow: "Selected work",
    title: "Projects",
    builtWith: "Built with",
    liveSite: "Live site",
    liveSiteOf: " of ",
    sourceCode: "Source code",
    sourceCodeOf: " on GitHub: ",
  },

  contact: {
    eyebrow: "Get in touch",
    title: "Need a senior engineer?",
    text: "Tell me about your product, your team and what you need built.",
    button: "Get in touch",
  },
};
