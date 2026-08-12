/* Relógio do header — hora:min:seg + data pt-BR, atualizado a cada segundo */

window.CMA = window.CMA || {};

(function () {
  /* Zero à esquerda para números de 1 dígito */
  function pad(n) {
    return String(n).padStart(2, '0');
  }

  function tick() {
    const timeEl = document.getElementById('clock-time');
    const dateEl = document.getElementById('clock-date');
    if (!timeEl || !dateEl) return;

    const now = new Date();
    timeEl.textContent = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
    dateEl.textContent = `${pad(now.getDate())}/${pad(now.getMonth() + 1)}/${now.getFullYear()}`;
  }

  let intervalId = null;

  /* Chamado pelo bootstrap do shell após o header estar no DOM */
  function initClock() {
    tick();
    if (intervalId) clearInterval(intervalId);
    intervalId = setInterval(tick, 1000);
  }

  window.CMA.initClock = initClock;
})();
