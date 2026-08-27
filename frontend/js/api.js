/* Camada central de comunicação com a API — usada por todas as páginas.
   Login, sessão (sessionStorage), fetch autenticado e um método por endpoint. */

window.CMA = window.CMA || {};

(function () {
  'use strict';

  var API_BASE = 'http://10.148.53.111:8000';
  var CHAVE_TOKEN = 'cma_token';
  var CHAVE_USUARIO = 'cma_usuario';

  function getToken() {
    return localStorage.getItem(CHAVE_TOKEN);
  }

  function getUsuario() {
    var raw = localStorage.getItem(CHAVE_USUARIO);
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch (err) {
      return null;
    }
  }

  function salvarSessao(token, usuario) {
    localStorage.setItem(CHAVE_TOKEN, token);
    localStorage.setItem(CHAVE_USUARIO, JSON.stringify(usuario));
  }

  function caminhoLogin() {
    return window.location.origin + '/login.html';
  }

  function logout() {
    localStorage.removeItem(CHAVE_TOKEN);
    localStorage.removeItem(CHAVE_USUARIO);
    window.location.href = caminhoLogin();
  }

  function construirQuery(filtros) {
    if (!filtros) return '';
    var params = new URLSearchParams();
    Object.keys(filtros).forEach(function (chave) {
      var valor = filtros[chave];
      if (valor !== undefined && valor !== null && valor !== '') {
        params.append(chave, valor);
      }
    });
    var qs = params.toString();
    return qs ? '?' + qs : '';
  }

  /* Fetch autenticado — injeta o Bearer token e trata 401 redirecionando pro login */
  async function apiFetch(path, options) {
    options = options || {};
    var headers = Object.assign({}, options.headers || {});
    var token = getToken();
    if (token) headers['Authorization'] = 'Bearer ' + token;
    if (options.body && !(options.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
    }

    var res;
    try {
      res = await fetch(API_BASE + path, Object.assign({}, options, { headers: headers }));
    } catch (err) {
      throw new Error('Não foi possível conectar à API em ' + API_BASE + '. Verifique se o serviço está no ar.');
    }

    if (res.status === 401) {
      logout();
      throw new Error('Sessão expirada. Faça login novamente.');
    }

    if (!res.ok) {
      var detail = 'Erro na requisição (HTTP ' + res.status + ')';
      try {
        var errJson = await res.json();
        if (errJson && errJson.detail) detail = errJson.detail;
      } catch (err) {
        /* corpo sem JSON — mantém mensagem padrão */
      }
      throw new Error(detail);
    }

    if (res.status === 204) return null;

    var texto = await res.text();
    return texto ? JSON.parse(texto) : null;
  }

  async function login(email, senha) {
    var res;
    try {
      res = await fetch(API_BASE + '/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email, senha: senha }),
      });
    } catch (err) {
      throw new Error('Não foi possível conectar à API em ' + API_BASE + '. Verifique se o serviço está no ar.');
    }

    if (!res.ok) {
      var detail = 'E-mail ou senha inválidos';
      try {
        var errJson = await res.json();
        if (errJson && errJson.detail) detail = errJson.detail;
      } catch (err) {
        /* corpo sem JSON — mantém mensagem padrão */
      }
      throw new Error(detail);
    }

    var dados = await res.json();
    salvarSessao(dados.access_token, dados.usuario);
    return dados;
  }

  window.CMA.api = {
    API_BASE: API_BASE,

    // ---- Autenticação / sessão ----
    login: login,
    logout: logout,
    getToken: getToken,
    getUsuario: getUsuario,
    fetch: apiFetch,

    // ---- Dashboard / equipamentos ----
    getDashboard: function () {
      return apiFetch('/api/dashboard');
    },
    getEquipamentos: function (filtros) {
      return apiFetch('/api/equipamentos' + construirQuery(filtros));
    },
    getEquipamento: function (id) {
      return apiFetch('/api/equipamentos/' + id);
    },
    criarEquipamento: function (dados) {
      return apiFetch('/api/equipamentos', { method: 'POST', body: JSON.stringify(dados) });
    },
    atualizarEquipamento: function (id, dados) {
      return apiFetch('/api/equipamentos/' + id, { method: 'PUT', body: JSON.stringify(dados) });
    },
    excluirEquipamento: function (id) {
      return apiFetch('/api/equipamentos/' + id, { method: 'DELETE' });
    },
    atualizarStatus: function (id, dados) {
      return apiFetch('/api/equipamentos/' + id + '/status', {
        method: 'PATCH',
        body: JSON.stringify(dados),
      });
    },
    getHistorico: function (id) {
      return apiFetch('/api/equipamentos/' + id + '/historico');
    },

    // ---- Alarmes ----
    getAlarmes: function (ativos) {
      var qs = ativos === undefined ? '' : '?ativos=' + (ativos ? 'true' : 'false');
      return apiFetch('/api/alarmes' + qs);
    },
    reconhecerAlarme: function (id) {
      return apiFetch('/api/alarmes/' + id + '/reconhecer', { method: 'PATCH' });
    },
    resolverAlarme: function (id, observacao) {
      return apiFetch('/api/alarmes/' + id + '/resolver', {
        method: 'PATCH',
        body: JSON.stringify({ observacao: observacao || null }),
      });
    },
    getHistoricoAlarmes: function (filtros) {
      return apiFetch('/api/alarmes/historico' + construirQuery(filtros));
    },

    // ---- Telemetria AMV ----
    getTelemetriaAMV: function (dispositivoId) {
      return apiFetch('/api/telemetria/amv/' + dispositivoId);
    },
    getHistoricoAMV: function (dispositivoId, params) {
      return apiFetch('/api/telemetria/amv/' + dispositivoId + '/historico' + construirQuery(params));
    },

    // ---- Usuários ----
    getUsuarios: function () {
      return apiFetch('/api/usuarios');
    },
    atualizarUsuario: function (id, dados) {
      return apiFetch('/api/usuarios/' + id, { method: 'PATCH', body: JSON.stringify(dados) });
    },
    ativarUsuario: function (id, ativo) {
      return apiFetch('/api/usuarios/' + id + '/ativo', {
        method: 'PATCH',
        body: JSON.stringify({ ativo: ativo }),
      });
    },
    redefinirSenhaUsuario: function (id, senha) {
      return apiFetch('/api/usuarios/' + id + '/senha', {
        method: 'PATCH',
        body: JSON.stringify({ senha: senha }),
      });
    },

    // ---- Cadastros auxiliares ----
    getMdas: function () {
      return apiFetch('/api/mdas');
    },
    criarMda: function (dados) {
      return apiFetch('/api/mdas', { method: 'POST', body: JSON.stringify(dados) });
    },
    atualizarMda: function (id, dados) {
      return apiFetch('/api/mdas/' + id, { method: 'PATCH', body: JSON.stringify(dados) });
    },
    excluirMda: function (id) {
      return apiFetch('/api/mdas/' + id, { method: 'DELETE' });
    },

    getStatusOperacional: function () {
      return apiFetch('/api/status');
    },
    criarStatusOperacional: function (dados) {
      return apiFetch('/api/status', { method: 'POST', body: JSON.stringify(dados) });
    },
    atualizarStatusOperacional: function (id, dados) {
      return apiFetch('/api/status/' + id, { method: 'PATCH', body: JSON.stringify(dados) });
    },
    excluirStatusOperacional: function (id) {
      return apiFetch('/api/status/' + id, { method: 'DELETE' });
    },

    getTiposEquipamento: function () {
      return apiFetch('/api/tipos-equipamento');
    },
    criarTipoEquipamento: function (dados) {
      return apiFetch('/api/tipos-equipamento', { method: 'POST', body: JSON.stringify(dados) });
    },
    atualizarTipoEquipamento: function (id, dados) {
      return apiFetch('/api/tipos-equipamento/' + id, { method: 'PATCH', body: JSON.stringify(dados) });
    },
    excluirTipoEquipamento: function (id) {
      return apiFetch('/api/tipos-equipamento/' + id, { method: 'DELETE' });
    },

    getLocalidades: function () {
      return apiFetch('/api/localidades');
    },
    getLinhas: function () {
      return apiFetch('/api/linhas');
    },

    getGruposNotificacao: function () {
      return apiFetch('/api/grupos-notificacao');
    },
    criarGrupoNotificacao: function (dados) {
      return apiFetch('/api/grupos-notificacao', { method: 'POST', body: JSON.stringify(dados) });
    },
    atualizarGrupoNotificacao: function (id, dados) {
      return apiFetch('/api/grupos-notificacao/' + id, { method: 'PATCH', body: JSON.stringify(dados) });
    },
    excluirGrupoNotificacao: function (id) {
      return apiFetch('/api/grupos-notificacao/' + id, { method: 'DELETE' });
    },
    getMembrosGrupo: function (grupoId) {
      return apiFetch('/api/grupos-notificacao/' + grupoId + '/membros');
    },
    adicionarMembroGrupo: function (grupoId, usuarioId) {
      return apiFetch('/api/grupos-notificacao/' + grupoId + '/membros', {
        method: 'POST',
        body: JSON.stringify({ usuario_id: usuarioId }),
      });
    },
    removerMembroGrupo: function (grupoId, usuarioId) {
      return apiFetch('/api/grupos-notificacao/' + grupoId + '/membros/' + usuarioId, { method: 'DELETE' });
    },
  };
})();
