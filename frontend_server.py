#!/usr/bin/env python3
"""Servidor estático da SPA IHM-CMA.

Serve os arquivos de frontend/ na porta 8080. Para qualquer rota que não
corresponda a um arquivo existente (ex.: /alarmes, /tabela — rotas da SPA
resolvidas no navegador pelo router via History API), devolve
frontend/index.html no lugar de um 404, permitindo F5 e acesso direto por URL.

Uso: python3 frontend_server.py
Somente biblioteca padrão — sem dependências externas (VM sem internet).
"""
import http.server
import os

PORTA = 8080
RAIZ_FRONTEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")


class SPARequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=RAIZ_FRONTEND, **kwargs)

    def translate_path(self, path):
        caminho = super().translate_path(path)
        if not os.path.isdir(caminho) and not os.path.isfile(caminho):
            caminho = super().translate_path("/index.html")
        return caminho


if __name__ == "__main__":
    http.server.test(
        HandlerClass=SPARequestHandler,
        ServerClass=http.server.ThreadingHTTPServer,
        port=PORTA,
    )
