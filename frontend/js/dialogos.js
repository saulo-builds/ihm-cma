/* Diálogos compartilhados entre páginas (alarmes, tabela):
   - CMA.confirmar(opcoes)            → Promise<boolean>
   - CMA.abrirDialogoSupressao(equip) → Promise<supressão criada | null>

   Os <dialog> são anexados ao <body> (fora de #content), então sobrevivem à
   troca de página do router e são criados uma única vez. */

window.CMA = window.CMA || {};

(function () {
  'use strict';

  /* Durações oferecidas no diálogo. "Sem prazo" (null) só para Administrador —
     a API valida de novo e responde 403 se o perfil não permitir. */
  var DURACOES = [
    { horas: 1, rotulo: '1h' },
    { horas: 4, rotulo: '4h' },
    { horas: 8, rotulo: '8h' },
    { horas: 24, rotulo: '24h' },
    { horas: null, rotulo: 'Sem prazo', somenteAdmin: true }
  ];

  function escapeHtml(texto) {
    var div = document.createElement('div');
    div.textContent = texto == null ? '' : String(texto);
    return div.innerHTML;
  }

  function criarDialog(html, classes) {
    var dlg = document.createElement('dialog');
    dlg.className = 'modal' + (classes ? ' ' + classes : '');
    dlg.innerHTML = html;
    document.body.appendChild(dlg);
    return dlg;
  }

  /* ===== Confirmação ===== */
  var dlgConfirm = null;

  function confirmar(opcoes) {
    opcoes = opcoes || {};
    if (!dlgConfirm) {
      dlgConfirm = criarDialog(
        '<div class="modal-header">' +
        '<div class="modal-title" data-ref="titulo"></div>' +
        '<button type="button" class="modal-close" data-acao="nao" aria-label="Fechar">✕</button>' +
        '</div>' +
        '<div class="modal-body"><p class="modal-confirm__text" data-ref="mensagem"></p></div>' +
        '<div class="modal-footer">' +
        '<button type="button" class="btn btn-ghost" data-acao="nao">Cancelar</button>' +
        '<button type="button" class="btn" data-acao="sim" data-ref="botao"></button>' +
        '</div>',
        'modal-confirm'
      );
    }

    dlgConfirm.querySelector('[data-ref="titulo"]').textContent = opcoes.titulo || 'Confirmar';
    dlgConfirm.querySelector('[data-ref="mensagem"]').textContent = opcoes.mensagem || '';
    var botao = dlgConfirm.querySelector('[data-ref="botao"]');
    botao.textContent = opcoes.textoConfirmar || 'Confirmar';
    botao.className = 'btn ' + (opcoes.perigo ? 'btn-danger' : 'btn-primary');

    return new Promise(function (resolve) {
      function fechar(resultado) {
        dlgConfirm.removeEventListener('click', onClick);
        dlgConfirm.removeEventListener('cancel', onCancel);
        if (dlgConfirm.open) dlgConfirm.close();
        resolve(resultado);
      }
      function onClick(evt) {
        var acao = evt.target.closest('[data-acao]');
        if (acao) fechar(acao.getAttribute('data-acao') === 'sim');
      }
      function onCancel(evt) {
        evt.preventDefault();
        fechar(false);
      }
      dlgConfirm.addEventListener('click', onClick);
      dlgConfirm.addEventListener('cancel', onCancel);
      dlgConfirm.showModal();
      botao.focus();
    });
  }

  /* ===== Supressão ===== */
  var dlgSupr = null;

  function montarDialogoSupressao() {
    dlgSupr = criarDialog(
      '<form method="dialog" data-ref="form">' +
      '<div class="modal-header">' +
      '<div class="modal-title">Suprimir alarmes do equipamento</div>' +
      '<button type="button" class="modal-close" data-acao="fechar" aria-label="Fechar">✕</button>' +
      '</div>' +
      '<div class="modal-body">' +
      '<div class="supr-alvo" data-ref="alvo"></div>' +
      '<div class="supr-field">' +
      '<label class="form-label" for="supr-motivo">Motivo *</label>' +
      '<textarea class="input" id="supr-motivo" data-ref="motivo" maxlength="200" required ' +
      'placeholder="Ex.: manutenção programada no AMV"></textarea>' +
      '<div class="supr-contador" data-ref="contador">0/200</div>' +
      '</div>' +
      '<div class="supr-field">' +
      '<span class="form-label">Duração</span>' +
      '<div class="supr-duracoes" data-ref="duracoes" role="radiogroup" aria-label="Duração"></div>' +
      '</div>' +
      '<p class="supr-nota">Todos os alarmes deste equipamento deixam de aparecer na aba Ativos, no sino e no VideoWall. ' +
      'Os alarmes não são fechados, e o status do equipamento continua sendo atualizado.</p>' +
      '<p class="supr-erro" data-ref="erro" hidden></p>' +
      '</div>' +
      '<div class="modal-footer">' +
      '<button type="button" class="btn btn-ghost" data-acao="fechar">Cancelar</button>' +
      '<button type="submit" class="btn btn-primary" data-ref="enviar">Suprimir</button>' +
      '</div>' +
      '</form>'
    );

    var motivo = dlgSupr.querySelector('[data-ref="motivo"]');
    var contador = dlgSupr.querySelector('[data-ref="contador"]');
    motivo.addEventListener('input', function () {
      contador.textContent = motivo.value.length + '/200';
    });
  }

  function abrirDialogoSupressao(equipamento) {
    if (!dlgSupr) montarDialogoSupressao();

    var form = dlgSupr.querySelector('[data-ref="form"]');
    var motivo = dlgSupr.querySelector('[data-ref="motivo"]');
    var erro = dlgSupr.querySelector('[data-ref="erro"]');
    var enviar = dlgSupr.querySelector('[data-ref="enviar"]');

    dlgSupr.querySelector('[data-ref="alvo"]').innerHTML =
      escapeHtml(equipamento.nome) +
      (equipamento.dispositivo_id
        ? ' <span class="supr-alvo__disp">(' + escapeHtml(equipamento.dispositivo_id) + ')</span>'
        : '');

    var admin = window.CMA.api.ehAdmin();
    dlgSupr.querySelector('[data-ref="duracoes"]').innerHTML = DURACOES
      .filter(function (d) { return admin || !d.somenteAdmin; })
      .map(function (d, i) {
        return '<label class="supr-duracao">' +
          '<input type="radio" name="supr-duracao" value="' + (d.horas === null ? '' : d.horas) + '"' +
          (i === 0 ? ' checked' : '') + ' />' +
          '<span>' + escapeHtml(d.rotulo) + '</span></label>';
      }).join('');

    motivo.value = '';
    dlgSupr.querySelector('[data-ref="contador"]').textContent = '0/200';
    erro.hidden = true;
    enviar.disabled = false;

    return new Promise(function (resolve) {
      function fechar(resultado) {
        form.removeEventListener('submit', onSubmit);
        dlgSupr.removeEventListener('click', onClick);
        dlgSupr.removeEventListener('cancel', onCancel);
        if (dlgSupr.open) dlgSupr.close();
        resolve(resultado);
      }
      function onClick(evt) {
        if (evt.target.closest('[data-acao="fechar"]')) fechar(null);
      }
      function onCancel(evt) {
        evt.preventDefault();
        fechar(null);
      }
      function onSubmit(evt) {
        evt.preventDefault();
        var texto = motivo.value.trim();
        if (!texto) {
          erro.textContent = 'Informe o motivo da supressão.';
          erro.hidden = false;
          motivo.focus();
          return;
        }
        var marcado = form.querySelector('input[name="supr-duracao"]:checked');
        var duracao = marcado && marcado.value !== '' ? parseInt(marcado.value, 10) : null;

        enviar.disabled = true;
        erro.hidden = true;
        window.CMA.api.suprimirEquipamento(equipamento.id, texto, duracao)
          .then(function (supressao) { fechar(supressao); })
          .catch(function (err) {
            enviar.disabled = false;
            erro.textContent = err.message;
            erro.hidden = false;
          });
      }
      form.addEventListener('submit', onSubmit);
      dlgSupr.addEventListener('click', onClick);
      dlgSupr.addEventListener('cancel', onCancel);
      dlgSupr.showModal();
      motivo.focus();
    });
  }

  window.CMA.confirmar = confirmar;
  window.CMA.abrirDialogoSupressao = abrirDialogoSupressao;
})();
