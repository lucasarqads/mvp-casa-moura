"""Esquemas Pydantic v2 de entrada e saída da API."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Entrada(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class Saida(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Autenticação -----------------------------------------------------------


class LoginIn(Entrada):
    email: str = Field(min_length=3, max_length=254)
    senha: str = Field(min_length=1, max_length=128)


class OperadorOut(Saida):
    id: int
    nome: str
    email: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expira_em: datetime
    operador: OperadorOut


# --- Catálogo e clientes ----------------------------------------------------


class ProdutoOut(Saida):
    id: int
    nome: str
    preco_centavos: int
    estoque: int


class ClienteIn(Entrada):
    nome: str = Field(min_length=2, max_length=120)
    telefone: str = Field(pattern=r"^[0-9()+\-\s]{8,20}$")
    documento: str | None = Field(default=None, pattern=r"^[0-9./\-]{11,18}$")

    @field_validator("documento", mode="before")
    @classmethod
    def documento_vazio_vira_nulo(cls, valor: object) -> object:
        if isinstance(valor, str) and not valor.strip():
            return None
        return valor


class ClienteOut(Saida):
    id: int
    nome: str
    telefone: str
    documento: str | None


# --- Checkout ---------------------------------------------------------------


class FormaPagamento(StrEnum):
    PIX = "pix"
    DINHEIRO = "dinheiro"
    CARTAO_DEBITO = "cartao_debito"
    CARTAO_CREDITO = "cartao_credito"


class ItemCheckoutIn(Entrada):
    produto_id: int = Field(gt=0)
    quantidade: int = Field(ge=1, le=999)


class CheckoutIn(Entrada):
    itens: list[ItemCheckoutIn] = Field(min_length=1, max_length=100)
    cliente_id: int | None = Field(default=None, gt=0)
    forma_pagamento: FormaPagamento
    valor_recebido_centavos: int | None = Field(default=None, ge=0)


class ItemVendaOut(BaseModel):
    produto_id: int
    nome: str
    quantidade: int
    preco_unitario_centavos: int
    subtotal_centavos: int
    novo_saldo: int


class VendaOut(BaseModel):
    id: int
    numero: str
    criado_em: datetime
    operador: str
    cliente: ClienteOut | None
    forma_pagamento: FormaPagamento
    itens: list[ItemVendaOut]
    total_centavos: int
    valor_recebido_centavos: int | None
    troco_centavos: int | None
