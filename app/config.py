"""Configurações lidas de variáveis de ambiente (veja `.env.example`)."""

import os
from datetime import timedelta

SECRET_KEY: str = os.getenv("SECRET_KEY", "chave-insegura-apenas-para-desenvolvimento")
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./casamoura_demo.db")
TOKEN_EXPIRA: timedelta = timedelta(hours=int(os.getenv("TOKEN_EXPIRA_HORAS", "8")))
