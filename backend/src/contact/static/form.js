// The contact form's only script: it loads Cloudflare Turnstile and keeps "Send message"
// disabled until the widget hands over a token. If the widget cannot load or fails, it offers
// the email address instead. Without JavaScript the page hides the form and shows the address.
(() => {
  const send = document.querySelector(".form button[type=submit]");
  const alternative = document.getElementById("alternative");
  const offerEmail = () => {
    alternative.hidden = false;
  };

  window.turnstileReady = () => {
    send.disabled = false;
  };
  window.turnstileExpired = () => {
    send.disabled = true;
  };
  window.turnstileFailed = offerEmail;

  const script = document.createElement("script");
  script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js";
  script.async = true;
  script.onerror = offerEmail;
  document.head.append(script);
})();
