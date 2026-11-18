"""Modelos do banco de dados. Valores monetários são armazenados em centavos (inteiros)."""

from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _agora() -> datetime:
    return datetime.now(UTC)


class Operador(Base):
    __tablename__ = "operadores"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    senha_hash: Mapped[str] = mapped_column(String(255))
    ativo: Mapped[bool] = mapped_column(default=True)


class Produto(Base):
    __tablename__ = "produtos"
    __table_args__ = (
        CheckConstraint("estoque >= 0", name="ck_produto_estoque_nao_negativo"),
        CheckConstraint("preco_centavos >= 0", name="ck_produto_preco_nao_negativo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(160), index=True)
    preco_centavos: Mapped[int]
    estoque: Mapped[int]


class Cliente(Base):
    __tablename__ = "clientes"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    telefone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    documento: Mapped[str | None] = mapped_column(String(18))


class Venda(Base):
    __tablename__ = "vendas"

    id: Mapped[int] = mapped_column(primary_key=True)
    operador_id: Mapped[int] = mapped_column(ForeignKey("operadores.id"))
    cliente_id: Mapped[int | None] = mapped_column(ForeignKey("clientes.id"))
    forma_pagamento: Mapped[str] = mapped_column(String(20))
    total_centavos: Mapped[int]
    valor_recebido_centavos: Mapped[int | None]
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_agora)

    operador: Mapped[Operador] = relationship()
    cliente: Mapped[Cliente | None] = relationship()
    itens: Mapped[list["ItemVenda"]] = relationship(
        back_populates="venda", cascade="all, delete-orphan"
    )


class ItemVenda(Base):
    __tablename__ = "itens_venda"

    id: Mapped[int] = mapped_column(primary_key=True)
    venda_id: Mapped[int] = mapped_column(ForeignKey("vendas.id"))
    produto_id: Mapped[int] = mapped_column(ForeignKey("produtos.id"))
    quantidade: Mapped[int]
    preco_unitario_centavos: Mapped[int]

    venda: Mapped[Venda] = relationship(back_populates="itens")
    produto: Mapped[Produto] = relationship()
