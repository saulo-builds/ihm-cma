/* Contador de alarmes ativos no ícone da sidebar — mesma fonte de dados da
   tela de Alarmes (GET /api/alarmes?ativos=true, resolvido_em IS NULL).
   Atualizado ao navegar para qualquer página e após Reconhecer/Resolver. */

window.CMA = window.CMA || {};

(function () {
  function aplicarContador(total) {
    var badge = document.querySelector('.app-sidebar__badge');
    if (badge) badge.textContent = String(total);
  }

  /* Aceita a lista de alarmes já carregada (evita nova requisição) ou,
     se omitida, busca na API. */
  function atualizarContadorAlarmes(alarmesAtivos) {
    if (Array.isArray(alarmesAtivos)) {
      aplicarContador(alarmesAtivos.length);
      return Promise.resolve();
    }
    if (!window.CMA.api || typeof window.CMA.api.getAlarmes !== 'function') {
      return Promise.resolve();
    }
    return window.CMA.api
      .getAlarmes(true)
      .then(function (lista) {
        aplicarContador(lista.length);
      })
      .catch(function (err) {
        console.error('[alarmes-badge] falha ao atualizar contador', err);
      });
  }

  /* Chamado pelo bootstrap do shell após a sidebar estar no DOM */
  function initAlarmesBadge() {
    atualizarContadorAlarmes();
    window.addEventListener('router:navigated', function () {
      atualizarContadorAlarmes();
    });
  }

  window.CMA.initAlarmesBadge = initAlarmesBadge;
  window.CMA.atualizarContadorAlarmes = atualizarContadorAlarmes;
})();
