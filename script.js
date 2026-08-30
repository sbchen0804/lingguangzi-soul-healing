(() => {
  const entries = [...document.querySelectorAll('[data-entry]')];
  function setActiveEntry() {
    const current = ['#entry-521', '#original-reader', ''].includes(location.hash) ? '#original-521' : location.hash;
    entries.forEach(entry => {
      const selected = entry.getAttribute('href') === current;
      entry.classList.toggle('active', selected);
      entry.toggleAttribute('aria-current', selected);
    });
  }
  entries.forEach(entry => entry.addEventListener('click', () => window.setTimeout(setActiveEntry, 0)));
  window.addEventListener('hashchange', setActiveEntry);
  setActiveEntry();

  const audios = [...document.querySelectorAll('audio')];
  const player = document.querySelector('#mini-player');
  const title = document.querySelector('#mini-player-title');
  const pause = document.querySelector('#mini-pause');
  const resume = document.querySelector('#mini-resume');
  const stop = document.querySelector('#mini-stop');
  let activeAudio = null;
  const updateControls = () => { const isPaused = !activeAudio || activeAudio.paused; pause.hidden = isPaused; resume.hidden = !isPaused; };
  const stopAllAudio = () => { audios.forEach(audio => { audio.pause(); audio.currentTime = 0; }); activeAudio = null; player.hidden = true; };
  audios.forEach(audio => {
    audio.addEventListener('play', () => { audios.forEach(other => { if (other !== audio) other.pause(); }); activeAudio = audio; title.textContent = `正在播放：${audio.dataset.title}`; player.hidden = false; updateControls(); });
    audio.addEventListener('pause', () => { if (activeAudio === audio && !audio.ended) updateControls(); });
    audio.addEventListener('ended', () => { if (activeAudio === audio) stopAllAudio(); });
  });
  pause.addEventListener('click', () => activeAudio?.pause());
  resume.addEventListener('click', () => activeAudio?.play());
  stop.addEventListener('click', stopAllAudio);
  window.addEventListener('pagehide', stopAllAudio);
})();
