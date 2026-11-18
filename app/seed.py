"""Dados fictícios de demonstração. Nenhum dado pessoal real."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Operador, Produto
from app.security import gerar_hash

OPERADOR_DEMO = {
    "nome": "Balcão 01",
    "email": "operador.balcao@casamoura-demo.local",
    "senha": "SenhaDemo123",
}

# (nome, preço em centavos, estoque)
PRODUTOS_DEMO = [
    ("Cimento CP-II 50kg", 3490, 42),
    ("Argamassa AC-III 20kg", 2850, 18),
    ("Tubo PVC Soldável 25mm 6m", 1900, 30),
    ("Tinta Acrílica Fosca Branca 18L", 18990, 9),
]


def popular_dados_demo(db: Session) -> None:
    """Cria o operador e os produtos de demonstração, se o banco estiver vazio."""
    if db.scalar(select(func.count()).select_from(Operador)):
        return
    db.add(
        Operador(
            nome=OPERADOR_DEMO["nome"],
            email=OPERADOR_DEMO["email"],
            senha_hash=gerar_hash(OPERADOR_DEMO["senha"]),
        )
    )
    db.add_all(
        Produto(nome=nome, preco_centavos=preco, estoque=estoque)
        for nome, preco, estoque in PRODUTOS_DEMO
    )
    db.commit()
