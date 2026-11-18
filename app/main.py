"""API FastAPI do MVP Casa Moura — Gestão de Balcão.

Rotas:
    POST /api/auth/login   autenticação do operador (RF01)
    GET  /api/produtos     catálogo com saldo em estoque (RF02)
    GET  /api/clientes     consulta de clientes (RF03)
    POST /api/clientes     cadastro rápido de cliente (RF03)
    POST /api/checkout     venda com baixa automática de estoque (RF04)

O frontend estático (pasta `frontend/`) é servido na raiz `/`.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, engine, get_db
from app.models import Cliente, ItemVenda, Operador, Produto, Venda
from app.schemas import (
    CheckoutIn,
    ClienteIn,
    ClienteOut,
    FormaPagamento,
    ItemVendaOut,
    LoginIn,
    OperadorOut,
    ProdutoOut,
    TokenOut,
    VendaOut,
)
from app.security import criar_token, operador_atual, senha_confere
from app.seed import popular_dados_demo

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        popular_dados_demo(db)
    yield


app = FastAPI(
    title="MVP Casa Moura — Gestão de Balcão",
    description="API de demonstração para atendimento de balcão. Todos os dados são fictícios.",
    version="0.1.0",
    lifespan=lifespan,
)

DB = Annotated[Session, Depends(get_db)]
OperadorAtual = Annotated[Operador, Depends(operador_atual)]


def erro(status_code: int, codigo: str, mensagem: str, **extra: Any) -> HTTPException:
    """Erros da API seguem o formato {"detail": {"codigo", "mensagem", ...}}."""
    return HTTPException(status_code, detail={"codigo": codigo, "mensagem": mensagem, **extra})


@app.get("/api/saude", tags=["infra"])
def saude() -> dict[str, str]:
    return {"status": "ok"}


# --- RF01: autenticação -----------------------------------------------------


@app.post("/api/auth/login", response_model=TokenOut, tags=["autenticação"])
def login(dados: LoginIn, db: DB) -> TokenOut:
    operador = db.scalar(select(Operador).where(Operador.email == dados.email.lower()))
    if not senha_confere(dados.senha, operador):
        raise erro(
            status.HTTP_401_UNAUTHORIZED,
            "credenciais_invalidas",
            "Credenciais inválidas. Verifique o e-mail e a senha informados.",
        )
    token, expira_em = criar_token(operador.id)
    return TokenOut(
        access_token=token, expira_em=expira_em, operador=OperadorOut.model_validate(operador)
    )


# --- RF02: catálogo ---------------------------------------------------------


@app.get("/api/produtos", response_model=list[ProdutoOut], tags=["catálogo"])
def listar_produtos(
    _operador: OperadorAtual,
    db: DB,
    busca: Annotated[str | None, Query(max_length=100)] = None,
) -> list[Produto]:
    consulta = select(Produto).order_by(Produto.id)
    if busca:
        consulta = consulta.where(
            func.lower(Produto.nome).contains(busca.strip().lower(), autoescape=True)
        )
    return list(db.scalars(consulta))


# --- RF03: clientes ---------------------------------------------------------


@app.get("/api/clientes", response_model=list[ClienteOut], tags=["clientes"])
def listar_clientes(
    _operador: OperadorAtual,
    db: DB,
    busca: Annotated[str | None, Query(max_length=100)] = None,
) -> list[Cliente]:
    consulta = select(Cliente).order_by(Cliente.nome).limit(50)
    if busca:
        termo = busca.strip()
        consulta = consulta.where(
            or_(
                func.lower(Cliente.nome).contains(termo.lower(), autoescape=True),
                Cliente.telefone.contains(termo, autoescape=True),
            )
        )
    return list(db.scalars(consulta))


@app.post(
    "/api/clientes",
    response_model=ClienteOut,
    status_code=status.HTTP_201_CREATED,
    tags=["clientes"],
    responses={200: {"description": "Telefone já cadastrado: retorna o cliente existente."}},
)
def criar_cliente(
    dados: ClienteIn, _operador: OperadorAtual, db: DB, response: Response
) -> Cliente:
    existente = db.scalar(select(Cliente).where(Cliente.telefone == dados.telefone))
    if existente is not None:
        response.status_code = status.HTTP_200_OK
        return existente
    cliente = Cliente(**dados.model_dump())
    db.add(cliente)
    db.commit()
    return cliente


# --- RF04: checkout com baixa de estoque -----------------------------------


@app.post(
    "/api/checkout",
    response_model=VendaOut,
    status_code=status.HTTP_201_CREATED,
    tags=["checkout"],
    responses={
        402: {"description": "Saldo insuficiente: valor recebido menor que o total."},
        404: {"description": "Produto ou cliente não encontrado."},
        409: {"description": "Estoque insuficiente para um ou mais itens."},
    },
)
def checkout(dados: CheckoutIn, operador: OperadorAtual, db: DB) -> VendaOut:
    # Agrupa itens repetidos do mesmo produto.
    quantidades: dict[int, int] = {}
    for item in dados.itens:
        quantidades[item.produto_id] = quantidades.get(item.produto_id, 0) + item.quantidade

    cliente = None
    if dados.cliente_id is not None:
        cliente = db.get(Cliente, dados.cliente_id)
        if cliente is None:
            raise erro(404, "cliente_nao_encontrado", "Cliente não encontrado.")

    ids = list(quantidades)
    produtos = {p.id: p for p in db.scalars(select(Produto).where(Produto.id.in_(ids)))}
    inexistentes = sorted(set(quantidades) - set(produtos))
    if inexistentes:
        raise erro(
            404, "produto_nao_encontrado", "Produto não encontrado.", produtos=inexistentes
        )

    faltas = [
        {
            "produto_id": pid,
            "nome": produtos[pid].nome,
            "solicitado": qtd,
            "disponivel": produtos[pid].estoque,
        }
        for pid, qtd in quantidades.items()
        if produtos[pid].estoque < qtd
    ]
    if faltas:
        raise erro(
            status.HTTP_409_CONFLICT,
            "estoque_insuficiente",
            "Estoque indisponível para um ou mais itens. A transação não foi concluída "
            "e o estoque permanece inalterado.",
            itens=faltas,
        )

    total = sum(produtos[pid].preco_centavos * qtd for pid, qtd in quantidades.items())

    valor_recebido = None
    troco = None
    if dados.forma_pagamento is FormaPagamento.DINHEIRO:
        valor_recebido = dados.valor_recebido_centavos
        if valor_recebido is None:
            raise erro(
                422, "valor_recebido_obrigatorio", "Informe o valor recebido em dinheiro."
            )
        if valor_recebido < total:
            raise erro(
                status.HTTP_402_PAYMENT_REQUIRED,
                "saldo_insuficiente",
                "A transação não foi concluída. O estoque permanece inalterado. Solicite "
                "outro meio de pagamento ou ajuste os itens.",
                total_centavos=total,
                valor_recebido_centavos=valor_recebido,
            )
        troco = valor_recebido - total

    # Baixa atômica: cada UPDATE só é aplicado se ainda houver saldo. Protege contra
    # duas vendas simultâneas do mesmo item; qualquer falha desfaz a transação inteira.
    for pid, qtd in quantidades.items():
        resultado = db.execute(
            update(Produto)
            .where(Produto.id == pid, Produto.estoque >= qtd)
            .values(estoque=Produto.estoque - qtd)
            .execution_options(synchronize_session=False)
        )
        if resultado.rowcount != 1:
            db.rollback()
            raise erro(
                status.HTTP_409_CONFLICT,
                "estoque_insuficiente",
                "O estoque foi alterado durante a venda. Atualize o catálogo e tente novamente.",
                itens=[{"produto_id": pid, "nome": produtos[pid].nome, "solicitado": qtd}],
            )

    venda = Venda(
        operador_id=operador.id,
        cliente_id=cliente.id if cliente else None,
        forma_pagamento=dados.forma_pagamento.value,
        total_centavos=total,
        valor_recebido_centavos=valor_recebido,
        criado_em=datetime.now(UTC),
        itens=[
            ItemVenda(
                produto_id=pid,
                quantidade=qtd,
                preco_unitario_centavos=produtos[pid].preco_centavos,
            )
            for pid, qtd in quantidades.items()
        ],
    )
    db.add(venda)
    db.commit()

    saldos = dict(
        db.execute(select(Produto.id, Produto.estoque).where(Produto.id.in_(ids))).tuples()
    )
    return VendaOut(
        id=venda.id,
        numero=f"#{venda.id:05d}",
        criado_em=venda.criado_em,
        operador=operador.nome,
        cliente=ClienteOut.model_validate(cliente) if cliente else None,
        forma_pagamento=dados.forma_pagamento,
        itens=[
            ItemVendaOut(
                produto_id=pid,
                nome=produtos[pid].nome,
                quantidade=qtd,
                preco_unitario_centavos=produtos[pid].preco_centavos,
                subtotal_centavos=produtos[pid].preco_centavos * qtd,
                novo_saldo=saldos[pid],
            )
            for pid, qtd in quantidades.items()
        ],
        total_centavos=total,
        valor_recebido_centavos=valor_recebido,
        troco_centavos=troco,
    )


# --- Frontend estático (montado por último para não encobrir as rotas /api) --

if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
