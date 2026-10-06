/** Everything the page says, in Spanish (Argentina, with "vos"). See `texts.ts`. */

import type { Texts } from "./texts.ts";

export const es: Texts = {
  language: "es",
  ogLocale: "es_AR",
  title: "Alejandro Brunacci · Desarrollador senior (Python, datos, GenAI)",
  description:
    "Alejandro Brunacci, desarrollador de software senior. APIs en Python y FastAPI, pipelines de datos en Databricks y GenAI, de punta a punta. Disponible para trabajo remoto.",
  share: {
    title: "Alejandro Brunacci · Desarrollador de software senior",
    description:
      "Disponible para proyectos y consultoría. Más de 10 años. Productos web de punta a punta: APIs, pipelines de datos y GenAI en Python. Remoto.",
    image: "og-image-es.png",
    imageAlt:
      "Alejandro Brunacci, desarrollador de software senior. Hago productos web de punta a punta: APIs, pipelines de datos y GenAI en Python, con el frontend incluido.",
  },
  languageGroup: "Idioma",

  availability: "Disponible para proyectos y consultoría",
  role: "Desarrollador de software senior",
  tagline: {
    before: "Hago productos web de punta a punta: ",
    mark: "APIs, pipelines de datos y GenAI",
    after: " en Python, con el frontend incluido.",
  },
  location: ["Argentina", "Remoto"],
  emailMe: "Escribime",
  profile: { before: "Perfil de ", after: "" },
  technologies: "Tecnologías",

  about: {
    eyebrow: "Quién soy",
    title: "Sobre mí",
    lead: "Hago backends más rápidos, escalables y robustos: me especializo en optimizar rendimiento y procesos.",
    points: [
      "Backends para productos de GenAI y de datos en fintech, agtech y sistemas de gestión de eventos.",
      "Python, arquitectura de microservicios y cloud, desde MVPs hasta migraciones de monolito a microservicios.",
      "Lideré equipos multidisciplinarios de hasta 10 personas.",
      "Más de 10 años de experiencia en IT. Disponible para proyectos remotos y consultoría.",
    ],
  },

  projects: {
    eyebrow: "Algunos trabajos",
    title: "Proyectos",
    builtWith: "Hecho con",
    liveSite: "Ver sitio",
    liveSiteOf: " de ",
    sourceCode: "Código fuente",
    sourceCodeOf: " en GitHub: ",
  },

  contact: {
    eyebrow: "Contacto",
    title: "¿Necesitás un desarrollador senior?",
    text: "Contame de tu producto, tu equipo y qué necesitás construir.",
    button: "Escribime",
  },
};
