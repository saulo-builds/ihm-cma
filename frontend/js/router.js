/* Router SPA — troca o conteúdo de <main> via fetch, sem reload, sincroniza breadcrumb e sidebar */

window.CMA = window.CMA || {};

(function () {
  /* Mapa de rotas — caminho do arquivo é relativo à raiz de frontend/ */
  const ROUTES = {
    '/': { file: '/pages/monitoramento/dashboard.html', module: 'Monitoramento', page: 'Dashboard' },
    '/mapeamento': { file: '/pages/monitoramento/mapeamento.html', module: 'Monitoramento', page: 'Mapeamento' },
    '/tabela': { file: '/pages/monitoramento/tabela.html', module: 'Monitoramento', page: 'Tabela' },
    '/disponibilidade': { file: '/pages/monitoramento/disponibilidade.html', module: 'Monitoramento', page: 'Disponibilidade' },
    '/localidade': { file: '/pages/monitoramento/localidade.html', module: 'Monitoramento', page: 'Localidade' },
    '/alarmes': { file: '/pages/monitoramento/alarmes.html', module: 'Monitoramento', page: 'Alarmes' },

    '/cadastro/mda': { file: '/pages/cadastro/mda.html', module: 'Cadastro', page: 'MDA' },
    '/cadastro/status': { file: '/pages/cadastro/status.html', module: 'Cadastro', page: 'Status' },
    '/cadastro/tipo-equipamento': { file: '/pages/cadastro/tipo-equipamento.html', module: 'Cadastro', page: 'Tipo de Equipamento' },
    '/cadastro/equipamento': { file: '/pages/cadastro/equipamento.html', module: 'Cadastro', page: 'Equipamento' },
    '/cadastro/notificacao': { file: '/pages/cadastro/notificacao.html', module: 'Cadastro', page: 'Notificação' },
    '/cadastro/usuarios': { file: '/pages/cadastro/usuarios.html', module: 'Cadastro', page: 'Usuários' },

    '/relatorios/disponibilidade': { file: '/pages/relatorios/disponibilidade.html', module: 'Relatórios', page: 'Disponibilidade' },
    '/relatorios/historico-alarmes': { file: '/pages/relatorios/historico-alarmes.html', module: 'Relatórios', page: 'Hist. Alarmes' },
    '/relatorios/mtbf-mttr': { file: '/pages/relatorios/mtbf-mttr.html', module: 'Relatórios', page: 'MTBF/MTTR' },
    '/relatorios/resumo-mensal': { file: '/pages/relatorios/resumo-mensal.html', module: 'Relatórios', page: 'Resumo Mensal' },
    '/relatorios/indisponibilidade-linha': { file: '/pages/relatorios/indisponibilidade-linha.html', module: 'Relatórios', page: 'Indisp. por Linha' },

    '/videowall': { file: '/pages/videowall/index.html', module: 'VideoWall', page: 'VideoWall' },
  };

  const state = { currentPath: '/' };

  function updateBreadcrumb(moduleLabel, pageLabel) {
    const moduleEl = document.getElementById('header-module');
    const pageEl = document.getElementById('header-page');
    if (moduleEl) moduleEl.textContent = moduleLabel;
    if (pageEl) pageEl.textContent = pageLabel;
  }

  function updateActiveNav(path) {
    document.querySelectorAll('.app-sidebar__item').forEach((item) => item.classList.remove('active'));
    const active = document.querySelector(`.app-sidebar__item[data-route="${path}"]`);
    if (active) active.classList.add('active');
  }

  /* <script> inserido via innerHTML nunca executa (regra do parser HTML) —
     recria cada um como elemento novo para que o JS específico da página rode. */
  function executeInlineScripts(container) {
    container.querySelectorAll('script').forEach((oldScript) => {
      const newScript = document.createElement('script');
      for (const { name, value } of oldScript.attributes) {
        newScript.setAttribute(name, value);
      }
      newScript.textContent = oldScript.textContent;
      oldScript.replaceWith(newScript);
    });
  }

  async function navigate(path, { pushHistory = true } = {}) {
    const route = ROUTES[path] || ROUTES['/'];
    const resolvedPath = ROUTES[path] ? path : '/';
    const main = document.getElementById('content');
    if (!main) return;

    main.setAttribute('aria-busy', 'true');

    try {
      const res = await fetch(route.file, { cache: 'no-store' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      main.innerHTML = await res.text();
      executeInlineScripts(main);
    } catch (err) {
      console.error('[router] falha ao carregar', route.file, err);
      main.innerHTML = `
        <div class="router-error">
          <p>Não foi possível carregar esta página.</p>
          <p class="router-error__hint">Sirva os arquivos por um servidor local (ex.: <code>npx serve frontend</code>) para navegação completa.</p>
        </div>`;
    } finally {
      main.removeAttribute('aria-busy');
    }

    state.currentPath = resolvedPath;
    updateBreadcrumb(route.module, route.page);
    updateActiveNav(resolvedPath);

    if (pushHistory) {
      history.pushState({ path: resolvedPath }, '', resolvedPath);
    }

    window.dispatchEvent(new CustomEvent('router:navigated', { detail: { path: resolvedPath, route } }));
  }

  /* Delega cliques em qualquer link [data-route] (sidebar, atalhos internos etc.) */
  function onDocumentClick(event) {
    const link = event.target.closest('[data-route]');
    if (!link) return;
    event.preventDefault();
    const path = link.getAttribute('data-route');
    if (path === state.currentPath) return;
    navigate(path);
  }

  function onPopState() {
    navigate(window.location.pathname, { pushHistory: false });
  }

  /* Chamado pelo bootstrap do shell após header/sidebar/main estarem no DOM */
  function initRouter() {
    document.addEventListener('click', onDocumentClick);
    window.addEventListener('popstate', onPopState);
    navigate(window.location.pathname, { pushHistory: false });
  }

  window.CMA.router = state;
  window.CMA.initRouter = initRouter;
})();
