"""Script standalone de inicializacao do banco.

Cria o schema ihm (executa schema_ihm.sql) e substitui os hashes de
senha placeholder dos usuarios seed por hashes bcrypt reais.

Uso: python api/db/init_db.py
"""
import sys
from pathlib import Path

import psycopg2

sys.path.append(str(Path(__file__).resolve().parent.parent))

from auth import hash_senha  # noqa: E402
from config import settings  # noqa: E402

SENHA_INICIAL = "CMA@2026"

USUARIOS_SEED = [
    "saulo.lima@cptm.sp.gov.br",
    "wellingto.rios@cptm.sp.gov.br",
    "fernando.vieira@cptm.sp.gov.br",
]


def executar_schema(conn) -> None:
    caminho_sql = Path(__file__).resolve().parent / "schema_ihm.sql"
    with open(caminho_sql, "r", encoding="utf-8") as arquivo:
        sql = arquivo.read()

    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
    print("[OK] Schema ihm criado e populado com dados iniciais.")


def definir_senhas_iniciais(conn) -> None:
    senha_hash = hash_senha(SENHA_INICIAL)

    with conn.cursor() as cur:
        for email in USUARIOS_SEED:
            cur.execute(
                "UPDATE ihm.usuarios SET senha_hash = %s WHERE email = %s",
                (senha_hash, email),
            )
            print(f"[OK] Senha inicial definida para {email}")
    conn.commit()


def main() -> None:
    print(f"Conectando ao banco: {settings.DATABASE_URL}")
    conn = psycopg2.connect(settings.DATABASE_URL)

    try:
        executar_schema(conn)
        definir_senhas_iniciais(conn)
        print("\nInicializacao concluida. Senha inicial de todos os usuarios: CMA@2026")
        print("Os usuarios devem trocar a senha no primeiro acesso.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
