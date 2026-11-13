/* Menyen: «katalog» står fast, resten ligg i ein nedtrekk (Ivers val 13.11.2026).
   Same meny på alle breidder: kolonna er smal òg på ein stor skjerm. */
(function () {
  "use strict";
  var btn = document.getElementById("navMoreBtn");
  var box = document.getElementById("navMore");
  if (!btn || !box) return;

  function setOpen(open) {
    box.classList.toggle("open", open);
    btn.setAttribute("aria-expanded", open ? "true" : "false");
  }

  function label() {
    var active = box.querySelector(".nav-btn.active");
    btn.textContent = (active ? active.textContent.trim() : "meir") + " ▾";
    btn.classList.toggle("active", !!active);
  }

  btn.addEventListener("click", function (e) {
    e.stopPropagation();
    setOpen(!box.classList.contains("open"));
    if (box.classList.contains("open")) {
      var first = box.querySelector(".nav-btn");
      if (first) first.focus({ preventScroll: true });
    }
  });
  box.addEventListener("click", function (e) {
    if (e.target.closest(".nav-btn")) setOpen(false);
  });
  document.addEventListener("click", function (e) {
    if (!e.target.closest("#navMore, #navMoreBtn")) setOpen(false);
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && box.classList.contains("open")) {
      setOpen(false);
      btn.focus();
    }
  });
  new MutationObserver(label).observe(box, { subtree: true, attributes: true, attributeFilter: ["class"] });
  label();
})();
