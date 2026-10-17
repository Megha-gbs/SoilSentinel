const menuButton = document.querySelector(".menu-toggle");
const navLinks = document.querySelector(".nav-links");
if (menuButton && navLinks) {
  menuButton.addEventListener("click", () => {
    const open = navLinks.classList.toggle("open");
    menuButton.setAttribute("aria-expanded", String(open));
    menuButton.setAttribute("aria-label", open ? "Close navigation" : "Open navigation");
  });
  navLinks.querySelectorAll("a").forEach(link => link.addEventListener("click", () => {
    navLinks.classList.remove("open");
    menuButton.setAttribute("aria-expanded", "false");
  }));
}

const revealObserver = new IntersectionObserver(entries => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.classList.add("is-visible");
      revealObserver.unobserve(entry.target);
    }
  });
}, { threshold: 0.12 });
document.querySelectorAll(".reveal").forEach((el, index) => {
  // Tiny stagger within a section gives the page a deliberate cinematic rhythm.
  el.style.transitionDelay = `${Math.min(index % 4, 3) * 70}ms`;
  revealObserver.observe(el);
});

// If the remote hero video is unavailable, the locally bundled SVG poster remains visible.
const heroVideo = document.querySelector(".hero-video");
if (heroVideo) {
  heroVideo.addEventListener("error", () => {
    heroVideo.style.display = "none";
    // The hero section's CSS background supplies a local photographic fallback.
  });
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  if (reduceMotion.matches) {
    heroVideo.pause();
    heroVideo.removeAttribute("autoplay");
  }
}


// Scroll-driven soil journey. Progressive enhancement: static soil remains visible without JS.
(() => {
  const journey = document.querySelector(".soil-journey");
  const frame = document.querySelector(".journey-visual-frame");
  const stageItems = [...document.querySelectorAll(".journey-stage")];
  if (!journey || !frame) return;

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  let ticking = false;
  let lastProgress = -1;

  function updateJourney() {
    ticking = false;
    if (reducedMotion.matches) {
      frame.style.setProperty("--journey-p", "0");
      return;
    }

    const rect = journey.getBoundingClientRect();
    const available = Math.max(1, rect.height - window.innerHeight * 0.55);
    const travelled = Math.min(available, Math.max(0, -rect.top + window.innerHeight * 0.18));
    const progress = Math.max(0, Math.min(1, travelled / available));
    if (Math.abs(progress - lastProgress) < 0.003) return;
    lastProgress = progress;

    frame.style.setProperty("--journey-p", progress.toFixed(3));
    frame.closest(".journey-visual").setAttribute("data-progress", progress.toFixed(3));
    const activeStage = Math.min(3, Math.floor(progress * 4));
    stageItems.forEach((item, index) => {
      const active = index === activeStage;
      item.classList.toggle("active", active);
      if (active) item.setAttribute("aria-current", "step");
      else item.removeAttribute("aria-current");
    });
  }

  function requestUpdate() {
    if (!ticking) {
      ticking = true;
      window.requestAnimationFrame(updateJourney);
    }
  }

  window.addEventListener("scroll", requestUpdate, { passive: true });
  window.addEventListener("resize", requestUpdate, { passive: true });
  if (reducedMotion.addEventListener) reducedMotion.addEventListener("change", requestUpdate);
  else if (reducedMotion.addListener) reducedMotion.addListener(requestUpdate);
  requestUpdate();
})();
