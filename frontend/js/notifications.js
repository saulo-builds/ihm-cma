/* Painel de notificações do header — lista, badge de não lidas, marcar todas como lidas e fechar ao clicar fora */

window.CMA = window.CMA || {};

(function () {
  /* Dados iniciais do CMA — implantações em andamento sinalizadas como maturidade parcial */
  const notifications = [
    {
      id: 'n1',
      tipo: 'parcial',
      titulo: 'STO L10 — Implantação parcial',
      meta: 'Linha 10',
      descricao: 'Parte em implantação — Maturidade: Parcial',
      tempo: 'há 1h',
      lida: false,
    },
    {
      id: 'n2',
      tipo: 'parcial',
      titulo: 'Fibra Ebilock Luz L10 — Em teste',
      meta: 'Sala Técnica LUZ',
      descricao: 'Sistema parcialmente em teste — Maturidade: Parcial',
      tempo: 'há 40 min',
      lida: false,
    },
  ];

  function render() {
    const list = document.getElementById('notif-list');
    const badge = document.getElementById('notif-badge');
    if (!list || !badge) return;

    list.innerHTML = notifications
      .map(
        (n) => `
      <div class="notif-item ${n.lida ? '' : 'is-unread'}" data-id="${n.id}">
        <span class="notif-item__dot notif-item__dot--${n.tipo}"></span>
        <div class="notif-item__body">
          <div class="notif-item__title">${n.titulo}</div>
          <div class="notif-item__desc">${n.meta} · ${n.descricao}</div>
          <div class="notif-item__time">${n.tempo}</div>
        </div>
      </div>`
      )
      .join('');

    const unread = notifications.filter((n) => !n.lida).length;
    badge.textContent = String(unread);
    badge.hidden = unread === 0;
  }

  function togglePanel(force) {
    const panel = document.getElementById('notif-panel');
    const btn = document.getElementById('btn-notif');
    if (!panel || !btn) return;

    const show = force !== undefined ? force : panel.hidden;
    panel.hidden = !show;
    btn.setAttribute('aria-expanded', String(show));
  }

  function markAllRead() {
    notifications.forEach((n) => (n.lida = true));
    render();
  }

  /* Fecha o painel ao clicar fora da área do sino/dropdown */
  function onDocumentClick(event) {
    const wrap = document.getElementById('notif-wrap');
    if (!wrap || wrap.contains(event.target)) return;
    togglePanel(false);
  }

  /* Chamado pelo bootstrap do shell após o header estar no DOM */
  function initNotifications() {
    render();

    const bellBtn = document.getElementById('btn-notif');
    const markAllBtn = document.getElementById('notif-mark-all');

    if (bellBtn) {
      bellBtn.addEventListener('click', (event) => {
        event.stopPropagation();
        togglePanel();
      });
    }
    if (markAllBtn) {
      markAllBtn.addEventListener('click', markAllRead);
    }

    document.addEventListener('click', onDocumentClick);
  }

  window.CMA.initNotifications = initNotifications;
})();
