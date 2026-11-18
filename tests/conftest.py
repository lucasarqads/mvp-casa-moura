import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

# Os testes sempre usam um banco SQLite em memória, nunca o banco de desenvolvimento.
# Precisa ser definido antes de qualquer import do pacote `app`.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ.setdefault("SECRET_KEY", "chave-somente-para-testes")


@pytest.fixture
def client() -> Iterator[TestClient]:
    from app.database import Base, SessionLocal, engine
    from app.main import app
    from app.seed import popular_dados_demo

    # Banco limpo a cada teste: um teste nunca depende do estoque deixado por outro.
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        popular_dados_demo(db)

    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth(client: TestClient) -> dict[str, str]:
    from app.seed import OPERADOR_DEMO

    resposta = client.post(
        "/api/auth/login",
        json={"email": OPERADOR_DEMO["email"], "senha": OPERADOR_DEMO["senha"]},
    )
    assert resposta.status_code == 200, resposta.text
    return {"Authorization": f"Bearer {resposta.json()['access_token']}"}
