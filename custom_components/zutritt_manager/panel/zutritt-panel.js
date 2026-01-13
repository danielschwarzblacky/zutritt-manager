// /config/www/zutritt-panel.js
class ZutrittManagerPanel extends HTMLElement {
  set hass(hass) {
    // hass wird von Home Assistant gesetzt
  }

  connectedCallback() {
    this.style.height = "100%";
    this.style.width = "100%";
    this.style.display = "block";

    // iframe einmal erstellen
    if (this._iframe) return;

    const iframe = document.createElement("iframe");
    iframe.style.border = "0";
    iframe.style.width = "100%";
    iframe.style.height = "100%";
    iframe.style.display = "block";

    // Das ist deine HTML im www-Ordner
    iframe.src = "/local/zutritt.html";

    this._iframe = iframe;
    this.appendChild(iframe);
  }
}

customElements.define("zutritt-manager-panel", ZutrittManagerPanel);
