# MVP Casa Moura — Gestão de Balcão

[![CI](https://github.com/lucasarqads/mvp-casa-moura/actions/workflows/ci.yml/badge.svg)](https://github.com/lucasarqads/mvp-casa-moura/actions/workflows/ci.yml)

Sistema de atendimento de balcão para uma loja de materiais de construção de pequeno porte. O operador
entra no sistema, consulta o catálogo com o saldo em estoque, monta o carrinho, vincula o cliente e
finaliza a venda. O estoque é baixado automaticamente quando a venda é aprovada e permanece intacto
quando ela é recusada.

> **Projeto de demonstração.** "Casa Moura" é uma loja fictícia. Todos os dados (operador, clientes,
> produtos, telefones e documentos) são inventados.

## Sumário

- [Contexto e ODS 8](#contexto-e-ods-8)
- [Funcionalidades](#funcionalidades)
- [Arquitetura](#arquitetura)
- [Requisitos](#requisitos)
- [Como executar](#como-executar)
- [Testes e qualidade](#testes-e-qualidade)
- [Referência da API](#referência-da-api)
- [Estrutura de pastas](#estrutura-de-pastas)
- [Próximos passos](#próximos-passos)

## Contexto e ODS 8

O projeto se alinha ao **Objetivo de Desenvolvimento Sustentável 8 da ONU — Trabalho Decente e
Crescimento Econômico**, em especial à meta 8.3, que incentiva a formalização e o crescimento de
micro, pequenas e médias empresas, inclusive por meio do acesso a serviços e tecnologia.

Pequenos comércios costumam controlar vendas e estoque em cadernos ou planilhas, o que causa erros de
saldo, vendas de itens que já acabaram e retrabalho no fechamento do caixa. Este MVP mostra como uma
ferramenta simples e acessível pode:

- reduzir erros de estoque com baixa automática e transacional a cada venda;
- dar ao operador de balcão uma interface clara, rápida e utilizável por teclado e leitor de tela,
  ampliando quem pode exercer a função (WCAG 2.1 AA);
- gerar histórico de vendas por operador e cliente, base para decisões de compra e crescimento.

## Funcionalidades

| Tela | O que faz |
| --- | --- |
| **Login** (`index.html`) | Autentica o operador e mostra um alerta claro quando as credenciais são inválidas. |
| **Catálogo e carrinho** (`catalogo-checkout.html`) | Busca de produtos, saldo em estoque, carrinho com controle de quantidade limitado ao estoque, cadastro rápido de cliente e escolha da forma de pagamento (com cálculo de troco em dinheiro). |
| **Resultado** (`resultado-checkout.html`) | Confirmação da venda com número do pedido e novo saldo de cada item, ou recusa (saldo ou estoque insuficiente) com o estoque inalterado. |

## Arquitetura

```text
┌──────────────────────────────┐        HTTP/JSON         ┌─────────────────────────────────┐
│ Frontend (HTML5 + Tailwind)  │ ───────────────────────▶ │ API FastAPI (Python 3.12)       │
│ index / catálogo / resultado │   Authorization: Bearer  │  • Pydantic v2 (validação)      │
│ servido pela própria API     │ ◀─────────────────────── │  • JWT (PyJWT) + bcrypt         │
└──────────────────────────────┘                          │  • SQLAlchemy 2.0 (ORM)         │
                                                          └───────────────┬─────────────────┘
                                                                          │
                                                          ┌───────────────▼─────────────────┐
                                                          │ SQLite (dev) / PostgreSQL (prod)│
                                                          └─────────────────────────────────┘
```

| Camada | Tecnologia | Papel |
| --- | --- | --- |
| Linguagem | Python 3.12 | Base do backend. |
| API | FastAPI | Rotas REST, documentação automática em `/docs` e serviço dos arquivos do frontend. |
| Validação | Pydantic v2 | Esquemas de entrada e saída, com rejeição de campos inesperados. |
| Persistência | SQLAlchemy 2.0 | ORM e baixa de estoque atômica. |
| Banco de dados | SQLite / PostgreSQL | SQLite para desenvolvimento e testes; PostgreSQL em produção, trocando só a `DATABASE_URL`. |
| Segurança | PyJWT, passlib + bcrypt | Token de acesso com expiração e senhas armazenadas como hash. |
| Interface | HTML5 semântico + Tailwind CSS | Três telas responsivas, sem etapa de build. |
| Qualidade | pytest, Ruff, GitHub Actions | Testes automatizados e lint a cada push e pull request. |

**Decisões de projeto**

- **Valores em centavos (inteiros).** Evita erros de arredondamento de ponto flutuante em dinheiro.
- **Baixa de estoque atômica.** Cada item é baixado com `UPDATE ... WHERE estoque >= quantidade`, dentro
  de uma única transação. Se qualquer item falhar, nada é baixado, inclusive em vendas simultâneas.
- **Erros padronizados.** Toda recusa de negócio responde `{"detail": {"codigo", "mensagem", ...}}`,
  para o frontend decidir o que mostrar pelo `codigo`.

## Requisitos

### Requisitos funcionais

| ID | Requisito | Onde |
| --- | --- | --- |
| **RF01** | Autenticar operadores por e-mail e senha, emitindo um token de acesso com validade. Credenciais inválidas são recusadas com mensagem genérica, sem revelar se o e-mail existe. | `POST /api/auth/login`, `index.html` |
| **RF02** | Listar o catálogo de produtos com preço e saldo em estoque, com busca por nome. | `GET /api/produtos`, `catalogo-checkout.html` |
| **RF03** | Cadastrar clientes rapidamente (nome, telefone e CPF/CNPJ opcional) e consultá-los. Um telefone já cadastrado reaproveita o cliente existente. | `GET/POST /api/clientes` |
| **RF04** | Finalizar a venda com baixa automática do estoque. Recusar a venda, sem alterar o estoque, quando faltar saldo de produto (HTTP 409) ou quando o valor recebido em dinheiro não cobrir o total (HTTP 402). | `POST /api/checkout`, `resultado-checkout.html` |

### Requisitos não funcionais

| ID | Requisito | Como é atendido |
| --- | --- | --- |
| **RNF01** | **Acessibilidade WCAG 2.1 AA** | Contraste mínimo de 4,5:1 no texto, foco sempre visível, áreas de toque de pelo menos 44 px, rótulos em todos os campos, alertas anunciados por leitores de tela (`role="alert"` e `role="status"`) e estados diferenciados por cor, ícone e texto. |
| **RNF02** | **Segurança** | Senhas com hash bcrypt, JWT com expiração, rotas protegidas por token, segredos fora do código (`.env`), validação estrita de entrada e escape de dados exibidos no HTML. |
| **RNF03** | **Integridade dos dados** | Checkout transacional (tudo ou nada), restrição de estoque não negativo no banco e valores monetários em inteiros. |
| **RNF04** | **Qualidade e manutenibilidade** | Testes automatizados com pytest, lint com Ruff e pipeline de CI no GitHub Actions bloqueando regressões na branch `main`. |

## Como executar

### Pré-requisitos

- Python 3.12
- Git

### Passo a passo

```bash
# 1. Clonar o repositório
git clone https://github.com/lucasarqads/mvp-casa-moura.git
cd mvp-casa-moura

# 2. Criar e ativar o ambiente virtual
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows (PowerShell ou CMD)

# 3. Instalar as dependências
pip install -r requirements.txt

# 4. Configurar as variáveis de ambiente
cp .env.example .env             # Windows: copy .env.example .env

# 5. Subir a aplicação
uvicorn app.main:app --reload --env-file .env
```

Abra **http://127.0.0.1:8000** e entre com o operador de demonstração:

| Campo | Valor |
| --- | --- |
| E-mail | `operador.balcao@casamoura-demo.local` |
| Senha | `SenhaDemo123` |

Na primeira execução, o banco `casamoura_demo.db` é criado e populado com o operador e quatro produtos
de demonstração. Para recomeçar do zero, apague esse arquivo.

A documentação interativa da API fica em **http://127.0.0.1:8000/docs**.

### Experimentando os cenários de recusa

- **Saldo insuficiente:** escolha *Dinheiro* como forma de pagamento e informe um valor recebido menor
  que o total.
- **Estoque indisponível:** ocorre quando outro atendimento vende o mesmo item antes. Para simular,
  abra duas abas, monte o mesmo carrinho com todo o estoque de um produto e finalize nas duas.
- **Apenas visual:** abra `resultado-checkout.html` sem ter feito uma venda na sessão; aparece um
  alternador "Simular Aprovação / Simular Recusa".

### Usando PostgreSQL

```bash
pip install "psycopg[binary]"
```

No `.env`:

```env
DATABASE_URL=postgresql+psycopg://usuario:senha@localhost:5432/casamoura
```

As tabelas são criadas automaticamente na inicialização.

## Testes e qualidade

```bash
pytest -v        # testes automatizados
ruff check .     # lint
```

Os testes usam um banco SQLite em memória recriado a cada teste, sem tocar no banco de desenvolvimento.
A suíte cobre:

- login válido, senha incorreta, e-mail inexistente e token inválido;
- proteção das rotas sem token;
- listagem e busca do catálogo;
- cadastro de cliente e reaproveitamento por telefone;
- checkout aprovado com baixa de estoque e cálculo de troco;
- recusa por **saldo insuficiente** (402) e por **estoque insuficiente** (409), confirmando que o estoque
  não muda;
- recusa atômica: se um item falha, os outros itens da mesma venda também não são baixados;
- validação de entrada (carrinho vazio, quantidade zero, forma de pagamento inválida).

O workflow [`.github/workflows/ci.yml`](.github/workflows/ci.yml) roda `ruff check .` e `pytest -v` a
cada `push` e `pull_request` na branch `main`.

## Referência da API

Todas as rotas, exceto login e saúde, exigem o cabeçalho `Authorization: Bearer <token>`.

| Método | Rota | Descrição | Respostas |
| --- | --- | --- | --- |
| `GET` | `/api/saude` | Verificação de funcionamento | 200 |
| `POST` | `/api/auth/login` | Login do operador | 200, 401, 422 |
| `GET` | `/api/produtos?busca=` | Catálogo com saldo | 200, 401 |
| `GET` | `/api/clientes?busca=` | Busca de clientes por nome ou telefone | 200, 401 |
| `POST` | `/api/clientes` | Cadastro rápido de cliente | 201 (novo), 200 (telefone já cadastrado), 401, 422 |
| `POST` | `/api/checkout` | Finaliza a venda | 201, 401, 402, 404, 409, 422 |

Exemplo de checkout:

```bash
curl -X POST http://127.0.0.1:8000/api/checkout \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "forma_pagamento": "dinheiro",
        "valor_recebido_centavos": 10000,
        "itens": [
          {"produto_id": 1, "quantidade": 2},
          {"produto_id": 2, "quantidade": 1}
        ]
      }'
```

Formas de pagamento aceitas: `pix`, `dinheiro`, `cartao_debito` e `cartao_credito`. Em `dinheiro`, o
campo `valor_recebido_centavos` é obrigatório.

## Estrutura de pastas

```text
mvp-casa-moura/
├── .github/workflows/ci.yml   # Pipeline de lint e testes
├── app/
│   ├── main.py                # Aplicação FastAPI e rotas
│   ├── config.py              # Variáveis de ambiente
│   ├── database.py            # Conexão SQLAlchemy
│   ├── models.py              # Tabelas
│   ├── schemas.py             # Esquemas Pydantic
│   ├── security.py            # Hash de senha e JWT
│   └── seed.py                # Dados fictícios de demonstração
├── frontend/
│   ├── index.html              # Login
│   ├── catalogo-checkout.html  # Catálogo e carrinho
│   └── resultado-checkout.html # Resultado da venda
├── tests/
│   ├── conftest.py            # Banco em memória e fixtures
│   └── test_api.py            # Testes da API
├── .env.example
├── .gitignore
├── pyproject.toml             # Configuração do Ruff e do pytest
├── requirements.txt
└── README.md
```

## Próximos passos

- Migrações de banco com Alembic.
- Limite de tentativas de login e registro de auditoria.
- Gerar o CSS do Tailwind no build (o CDN é indicado apenas para protótipos).
- Cancelamento e estorno de vendas, com devolução ao estoque.
- Relatórios de vendas por período, operador e produto.
