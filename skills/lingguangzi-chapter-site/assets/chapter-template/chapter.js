(() => {
  const entryHash = `#entry-${document.body.dataset.chapter}`;
  if (location.hash === entryHash) {
    history.replaceState(null, "", location.pathname + location.search);
    requestAnimationFrame(() => requestAnimationFrame(() => {
      scrollTo({ top: 0, behavior: "auto" });
    }));
  }

  const entries = [...document.querySelectorAll("[data-entry]")];
  const setActiveEntry = () => {
    const chapter = document.body.dataset.chapter;
    const current = ["", `#original-reader-${chapter}`].includes(location.hash) ? `#original-${chapter}` : location.hash;
    entries.forEach(entry => {
      const selected = entry.getAttribute("href") === current;
      entry.classList.toggle("active", selected);
      entry.toggleAttribute("aria-current", selected);
    });
  };
  entries.forEach(entry => entry.addEventListener("click", event => {
    event.preventDefault();
    const hash = entry.getAttribute("href");
    const target = document.querySelector(hash);
    if (!target) return;
    history.pushState(null, "", hash);
    setActiveEntry();
    requestAnimationFrame(() => requestAnimationFrame(() => target.scrollIntoView({ behavior: "smooth", block: "start" })));
  }));
  addEventListener("hashchange", setActiveEntry);
  setActiveEntry();

  document.querySelector(".go-top").addEventListener("click", event => {
    event.preventDefault();
    document.querySelector(".entry-nav").scrollIntoView({ behavior: "smooth", block: "start" });
  });

  const media = [...document.querySelectorAll("audio, video")];
  const player = document.querySelector("#mini-player");
  const title = document.querySelector("#mini-player-title");
  const pause = document.querySelector("#mini-pause");
  const resume = document.querySelector("#mini-resume");
  const stop = document.querySelector("#mini-stop");
  let activeMedia = null;
  const updateControls = () => { const paused = !activeMedia || activeMedia.paused; pause.hidden = paused; resume.hidden = !paused; };
  const stopAllMedia = () => { media.forEach(item => { item.pause(); item.currentTime = 0; }); activeMedia = null; player.hidden = true; };
  media.forEach(item => {
    item.addEventListener("play", () => { media.forEach(other => { if (other !== item) other.pause(); }); activeMedia = item; title.textContent = `正在播放：${item.dataset.title || "本章媒體"}`; player.hidden = false; updateControls(); });
    item.addEventListener("pause", () => { if (activeMedia === item && !item.ended) updateControls(); });
    item.addEventListener("ended", () => { if (activeMedia === item) stopAllMedia(); });
  });
  pause.addEventListener("click", () => activeMedia?.pause());
  resume.addEventListener("click", () => activeMedia?.play());
  stop.addEventListener("click", stopAllMedia);
  addEventListener("pagehide", stopAllMedia);

  const counter = document.querySelector("[data-goatcounter]");
  if (counter && !["localhost", "127.0.0.1"].includes(location.hostname)) {
    const code = counter.dataset.goatcounter;
    if (/^[a-z0-9-]+$/i.test(code)) {
      const script = document.createElement("script");
      script.async = true;
      script.dataset.goatcounter = `https://${code}.goatcounter.com/count`;
      script.src = "https://gc.zgo.at/count.js";
      document.head.append(script);
    }
  }
})();
