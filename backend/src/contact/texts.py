"""Everything the form's pages say, one ``Texts`` per language.

The eyebrow, title and lead are the landing's contact section (src/i18n/ in the site): keep
them the same. A field's error is looked up by the field and what is wrong with it, as
``submission.parse`` reports them.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from contact.language import Language
from contact.submission import MESSAGE_MAX, NAME_MAX, Problem


@dataclass(frozen=True, slots=True)
class Texts:
    language: Language
    home: str
    """The landing's path in this language."""
    title: str
    description: str
    eyebrow: str
    heading: str
    lead: str
    labels: Mapping[str, str]
    """Each field's label, by its name."""
    send: str
    check_fields: str
    """Above the form when a field is wrong."""
    errors: Mapping[tuple[str, Problem], str]
    send_failed: str
    daily_limit: str
    alternative: str
    """Before the email address, for whoever cannot use the form."""
    honeypot: str
    sent_title: str
    sent_heading: str
    sent_lead: str
    back: str


EN = Texts(
    language="en",
    home="/",
    title="Contact",
    description="Write to Alejandro Brunacci, Senior Software Engineer.",
    eyebrow="Get in touch",
    heading="Need a senior engineer?",
    lead="Tell me about your product, your team and what you need built.",
    labels={"name": "Name", "email": "Email", "message": "Message"},
    send="Send message",
    check_fields="Please check the fields marked below.",
    errors={
        ("name", Problem.MISSING): "Enter your name.",
        ("name", Problem.TOO_LONG): f"Keep the name under {NAME_MAX} characters.",
        ("email", Problem.MISSING): "Enter your email address, so I can reply.",
        ("email", Problem.INVALID): "Enter a valid email address, like name@company.com.",
        ("message", Problem.MISSING): "Write a message.",
        ("message", Problem.TOO_LONG): f"Keep the message under {MESSAGE_MAX:,} characters.",
    },
    send_failed="Your message could not be sent right now. Please try again in a few minutes.",
    daily_limit="The form has reached its limit for today. Please try again tomorrow.",
    alternative="You can also write to me directly at",
    honeypot="Leave this field empty",
    sent_title="Message received",
    sent_heading="Thanks, I got your message",
    sent_lead="I'll get back to you by email.",
    back="Back to abrunacci.dev",
)

ES = Texts(
    language="es",
    home="/es/",
    title="Contacto",
    description="Escribile a Alejandro Brunacci, desarrollador de software senior.",
    eyebrow="Contacto",
    heading="¿Necesitás un desarrollador senior?",
    lead="Contame de tu producto, tu equipo y qué necesitás construir.",
    labels={"name": "Nombre", "email": "Email", "message": "Mensaje"},
    send="Enviar mensaje",
    check_fields="Revisá los campos marcados abajo.",
    errors={
        ("name", Problem.MISSING): "Escribí tu nombre.",
        ("name", Problem.TOO_LONG): f"Usá menos de {NAME_MAX} caracteres para el nombre.",
        ("email", Problem.MISSING): "Escribí tu email, así te puedo responder.",
        ("email", Problem.INVALID): "Escribí un email válido, como nombre@empresa.com.",
        ("message", Problem.MISSING): "Escribí un mensaje.",
        ("message", Problem.TOO_LONG): (
            f"Usá menos de {MESSAGE_MAX:,} caracteres para el mensaje.".replace(",", ".")
        ),
    },
    send_failed="No se pudo enviar tu mensaje. Probá de nuevo en unos minutos.",
    daily_limit="El formulario llegó a su límite por hoy. Probá de nuevo mañana.",
    alternative="También podés escribirme directo a",
    honeypot="Dejá este campo vacío",
    sent_title="Mensaje recibido",
    sent_heading="Gracias, me llegó tu mensaje",
    sent_lead="Te respondo por email.",
    back="Volver a abrunacci.dev",
)

TEXTS: Mapping[Language, Texts] = {"en": EN, "es": ES}
