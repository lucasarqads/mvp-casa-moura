"""Hash de senhas (bcrypt) e autenticação por token JWT."""

from datetime import UTC, datetime
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import SECRET_KEY, TOKEN_EXPIRA
from app.database import get_db
from app.models import Operador

ALGORITMO = "HS256"

_contexto_senha = CryptContext(schemes=["bcrypt"], deprecated="auto")
# Usado quando o e-mail não existe, para que o tempo de resposta não revele contas válidas.
_HASH_FICTICIO = _contexto_senha.hash("senha-ficticia-para-tempo-constante")

_bearer = HTTPBearer(auto_error=False)


def gerar_hash(senha: str) -> str:
    return _contexto_senha.hash(senha)


def senha_confere(senha: str, operador: Operador | None) -> bool:
    if operador is None:
        _contexto_senha.verify(senha, _HASH_FICTICIO)
        return False
    return operador.ativo and _contexto_senha.verify(senha, operador.senha_hash)


def criar_token(operador_id: int) -> tuple[str, datetime]:
    expira_em = datetime.now(UTC) + TOKEN_EXPIRA
    token = jwt.encode(
        {"sub": str(operador_id), "exp": expira_em}, SECRET_KEY, algorithm=ALGORITMO
    )
    return token, expira_em


def operador_atual(
    credenciais: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> Operador:
    nao_autenticado = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "codigo": "nao_autenticado",
            "mensagem": "Sessão inválida ou expirada. Faça login novamente.",
        },
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credenciais is None:
        raise nao_autenticado
    try:
        payload = jwt.decode(credenciais.credentials, SECRET_KEY, algorithms=[ALGORITMO])
        operador_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise nao_autenticado from None

    operador = db.get(Operador, operador_id)
    if operador is None or not operador.ativo:
        raise nao_autenticado
    return operador
