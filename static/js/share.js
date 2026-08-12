(function () {
  const toggle = document.getElementById("uploadToggle");
  const zone = document.querySelector(".upload-zone");
  if (toggle && zone) {
    toggle.addEventListener("click", () => {
      const hidden = zone.classList.toggle("hidden");
      toggle.textContent = hidden ? "Upload files" : "Hide upload";
    });
  }
})();
