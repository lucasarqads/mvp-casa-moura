from fastapi.testclient import TestClient

from app.seed import OPERADOR_DEMO

# IDs dos produtos de demonstração, na ordem em que são criados em app/seed.py.
CIMENTO, ARGAMASSA, TUBO, TINTA = 1, 2, 3, 4


def estoque(client: TestClient, auth: dict[str, str]) -> dict[int, int]:
    produtos = client.get("/api/produtos", headers=auth).json()
    return {p["id"]: p["estoque"] for p in produtos}


# --- Infra ------------------------------------------------------------------


def test_saude(client: TestClient) -> None:
    resposta = client.get("/api/saude")
    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}


def test_frontend_servido_na_raiz(client: TestClient) -> None:
    resposta = client.get("/")
    assert resposta.status_code == 200
    assert "Casa Moura" in resposta.text


# --- RF01: autenticação -----------------------------------------------------


def test_login_valido(client: TestClient) -> None:
    resposta = client.post(
        "/api/auth/login",
        json={"email": OPERADOR_DEMO["email"], "senha": OPERADOR_DEMO["senha"]},
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["token_type"] == "bearer"
    assert corpo["access_token"]
    assert corpo["operador"]["email"] == OPERADOR_DEMO["email"]
    assert "senha_hash" not in corpo["operador"]


def test_login_ignora_maiusculas_e_espacos_no_email(client: TestClient) -> None:
    resposta = client.post(
        "/api/auth/login",
        json={"email": f"  {OPERADOR_DEMO['email'].upper()} ", "senha": OPERADOR_DEMO["senha"]},
    )
    assert resposta.status_code == 200


def test_login_senha_invalida(client: TestClient) -> None:
    resposta = client.post(
        "/api/auth/login", json={"email": OPERADOR_DEMO["email"], "senha": "senha-errada"}
    )
    assert resposta.status_code == 401
    assert resposta.json()["detail"]["codigo"] == "credenciais_invalidas"


def test_login_email_inexistente(client: TestClient) -> None:
    resposta = client.post(
        "/api/auth/login",
        json={"email": "ninguem@casamoura-demo.local", "senha": OPERADOR_DEMO["senha"]},
    )
    assert resposta.status_code == 401
    assert resposta.json()["detail"]["codigo"] == "credenciais_invalidas"


def test_rotas_protegidas_exigem_token(client: TestClient) -> None:
    assert client.get("/api/produtos").status_code == 401
    assert client.get("/api/clientes").status_code == 401
    assert client.post("/api/checkout", json={}).status_code == 401


def test_token_invalido_e_recusado(client: TestClient) -> None:
    resposta = client.get("/api/produtos", headers={"Authorization": "Bearer token-falso"})
    assert resposta.status_code == 401
    assert resposta.json()["detail"]["codigo"] == "nao_autenticado"


# --- RF02: catálogo ---------------------------------------------------------


def test_listar_produtos(client: TestClient, auth: dict[str, str]) -> None:
    resposta = client.get("/api/produtos", headers=auth)
    assert resposta.status_code == 200
    produtos = resposta.json()
    assert len(produtos) == 4
    assert produtos[0] == {
        "id": CIMENTO,
        "nome": "Cimento CP-II 50kg",
        "preco_centavos": 3490,
        "estoque": 42,
    }


def test_buscar_produto_por_nome(client: TestClient, auth: dict[str, str]) -> None:
    resposta = client.get("/api/produtos", params={"busca": "TINTA"}, headers=auth)
    assert [p["nome"] for p in resposta.json()] == ["Tinta Acrílica Fosca Branca 18L"]


# --- RF03: clientes ---------------------------------------------------------


def test_cadastro_rapido_de_cliente_reaproveita_telefone(
    client: TestClient, auth: dict[str, str]
) -> None:
    dados = {"nome": "João Silva Santos", "telefone": "(11) 99999-0101", "documento": ""}
    primeiro = client.post("/api/clientes", json=dados, headers=auth)
    assert primeiro.status_code == 201
    assert primeiro.json()["documento"] is None

    repetido = client.post("/api/clientes", json=dados, headers=auth)
    assert repetido.status_code == 200
    assert repetido.json()["id"] == primeiro.json()["id"]

    lista = client.get("/api/clientes", params={"busca": "joão"}, headers=auth).json()
    assert len(lista) == 1


def test_cliente_com_telefone_invalido(client: TestClient, auth: dict[str, str]) -> None:
    resposta = client.post(
        "/api/clientes", json={"nome": "Cliente Teste", "telefone": "abc"}, headers=auth
    )
    assert resposta.status_code == 422


# --- RF04: checkout ---------------------------------------------------------


def test_checkout_aprovado_baixa_estoque(client: TestClient, auth: dict[str, str]) -> None:
    cliente = client.post(
        "/api/clientes",
        json={"nome": "João Silva Santos", "telefone": "(11) 99999-0101"},
        headers=auth,
    ).json()

    resposta = client.post(
        "/api/checkout",
        json={
            "cliente_id": cliente["id"],
            "forma_pagamento": "pix",
            "itens": [
                {"produto_id": CIMENTO, "quantidade": 2},
                {"produto_id": ARGAMASSA, "quantidade": 1},
            ],
        },
        headers=auth,
    )

    assert resposta.status_code == 201, resposta.text
    venda = resposta.json()
    assert venda["numero"] == "#00001"
    assert venda["total_centavos"] == 9830
    assert venda["operador"] == OPERADOR_DEMO["nome"]
    assert venda["cliente"]["nome"] == "João Silva Santos"
    assert [(i["nome"], i["subtotal_centavos"], i["novo_saldo"]) for i in venda["itens"]] == [
        ("Cimento CP-II 50kg", 6980, 40),
        ("Argamassa AC-III 20kg", 2850, 17),
    ]
    assert estoque(client, auth)[CIMENTO] == 40
    assert estoque(client, auth)[ARGAMASSA] == 17


def test_checkout_agrupa_itens_repetidos(client: TestClient, auth: dict[str, str]) -> None:
    resposta = client.post(
        "/api/checkout",
        json={
            "forma_pagamento": "cartao_debito",
            "itens": [
                {"produto_id": TUBO, "quantidade": 1},
                {"produto_id": TUBO, "quantidade": 2},
            ],
        },
        headers=auth,
    )
    assert resposta.status_code == 201
    assert resposta.json()["itens"][0]["quantidade"] == 3
    assert estoque(client, auth)[TUBO] == 27


def test_checkout_em_dinheiro_calcula_troco(client: TestClient, auth: dict[str, str]) -> None:
    resposta = client.post(
        "/api/checkout",
        json={
            "forma_pagamento": "dinheiro",
            "valor_recebido_centavos": 10000,
            "itens": [
                {"produto_id": CIMENTO, "quantidade": 2},
                {"produto_id": ARGAMASSA, "quantidade": 1},
            ],
        },
        headers=auth,
    )
    assert resposta.status_code == 201
    assert resposta.json()["troco_centavos"] == 170


def test_checkout_recusado_por_saldo_insuficiente(
    client: TestClient, auth: dict[str, str]
) -> None:
    resposta = client.post(
        "/api/checkout",
        json={
            "forma_pagamento": "dinheiro",
            "valor_recebido_centavos": 5000,
            "itens": [
                {"produto_id": CIMENTO, "quantidade": 2},
                {"produto_id": ARGAMASSA, "quantidade": 1},
            ],
        },
        headers=auth,
    )
    assert resposta.status_code == 402
    detalhe = resposta.json()["detail"]
    assert detalhe["codigo"] == "saldo_insuficiente"
    assert detalhe["total_centavos"] == 9830
    # Estoque permanece inalterado.
    assert estoque(client, auth)[CIMENTO] == 42
    assert estoque(client, auth)[ARGAMASSA] == 18


def test_checkout_recusado_por_estoque_insuficiente(
    client: TestClient, auth: dict[str, str]
) -> None:
    resposta = client.post(
        "/api/checkout",
        json={"forma_pagamento": "pix", "itens": [{"produto_id": TINTA, "quantidade": 10}]},
        headers=auth,
    )
    assert resposta.status_code == 409
    detalhe = resposta.json()["detail"]
    assert detalhe["codigo"] == "estoque_insuficiente"
    assert detalhe["itens"] == [
        {
            "produto_id": TINTA,
            "nome": "Tinta Acrílica Fosca Branca 18L",
            "solicitado": 10,
            "disponivel": 9,
        }
    ]
    assert estoque(client, auth)[TINTA] == 9


def test_checkout_recusado_nao_baixa_nenhum_item(
    client: TestClient, auth: dict[str, str]
) -> None:
    """Se um item não tem estoque, os demais itens da mesma venda também não são baixados."""
    resposta = client.post(
        "/api/checkout",
        json={
            "forma_pagamento": "pix",
            "itens": [
                {"produto_id": CIMENTO, "quantidade": 2},
                {"produto_id": TINTA, "quantidade": 10},
            ],
        },
        headers=auth,
    )
    assert resposta.status_code == 409
    assert estoque(client, auth)[CIMENTO] == 42


def test_checkout_vende_todo_o_estoque(client: TestClient, auth: dict[str, str]) -> None:
    resposta = client.post(
        "/api/checkout",
        json={"forma_pagamento": "pix", "itens": [{"produto_id": TINTA, "quantidade": 9}]},
        headers=auth,
    )
    assert resposta.status_code == 201
    assert resposta.json()["itens"][0]["novo_saldo"] == 0


def test_checkout_produto_inexistente(client: TestClient, auth: dict[str, str]) -> None:
    resposta = client.post(
        "/api/checkout",
        json={"forma_pagamento": "pix", "itens": [{"produto_id": 999, "quantidade": 1}]},
        headers=auth,
    )
    assert resposta.status_code == 404
    assert resposta.json()["detail"]["codigo"] == "produto_nao_encontrado"


def test_checkout_dinheiro_sem_valor_recebido(client: TestClient, auth: dict[str, str]) -> None:
    resposta = client.post(
        "/api/checkout",
        json={"forma_pagamento": "dinheiro", "itens": [{"produto_id": TUBO, "quantidade": 1}]},
        headers=auth,
    )
    assert resposta.status_code == 422
    assert estoque(client, auth)[TUBO] == 30


def test_checkout_valida_entrada(client: TestClient, auth: dict[str, str]) -> None:
    sem_itens = client.post(
        "/api/checkout", json={"forma_pagamento": "pix", "itens": []}, headers=auth
    )
    quantidade_zero = client.post(
        "/api/checkout",
        json={"forma_pagamento": "pix", "itens": [{"produto_id": TUBO, "quantidade": 0}]},
        headers=auth,
    )
    forma_invalida = client.post(
        "/api/checkout",
        json={"forma_pagamento": "fiado", "itens": [{"produto_id": TUBO, "quantidade": 1}]},
        headers=auth,
    )
    assert sem_itens.status_code == 422
    assert quantidade_zero.status_code == 422
    assert forma_invalida.status_code == 422
