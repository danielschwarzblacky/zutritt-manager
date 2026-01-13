class ZutrittManagerPanel extends HTMLElement {
  connectedCallback() {
    if (this._done) return;
    this._done = true;
    this.style.height = "100%";
    this.style.width = "100%";

    const iframe = document.createElement("iframe");
    iframe.style.border = "0";
    iframe.style.width = "100%";
    iframe.style.height = "100%";
    iframe.src = "/local/zutritt.html";

    this.appendChild(iframe);
  }
}
customElements.define("zutritt-manager-panel", ZutrittManagerPanel);
