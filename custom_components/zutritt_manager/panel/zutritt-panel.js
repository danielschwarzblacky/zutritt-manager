class ZutrittPanel extends HTMLElement {
  set hass(hass) {
    this.innerHTML = "<h1>Zutritt Manager</h1><p>Panel geladen</p>";
  }
}
customElements.define("zutritt-panel", ZutrittPanel);
document.body.appendChild(document.createElement("zutritt-panel"));
