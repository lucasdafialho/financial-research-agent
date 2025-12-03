# Financial Research Agent

Sistema de orquestração de agentes de IA especializados para pesquisa e análise financeira do mercado brasileiro.

## Visão Geral

O Financial Research Agent é uma plataforma que utiliza múltiplos agentes de IA trabalhando em conjunto para:

- Coletar dados de mercado em tempo real
- Buscar e analisar documentos financeiros via RAG
- Processar notícias e sentimento de mercado
- Gerar insights acionáveis e relatórios fundamentados

## Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                         Frontend                             │
│                    (Next.js + React)                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Backend                         │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │
│  │ Router  │→ │Collector│→ │   RAG   │→ │ Analyst │→ Reporter│
│  │ Agent   │  │ Agent   │  │  Agent  │  │  Agent  │        │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘        │
│                    LangGraph Orchestration                   │
└─────────────────────────────────────────────────────────────┘
          │              │              │
          ▼              ▼              ▼
    ┌──────────┐   ┌──────────┐   ┌──────────┐
    │PostgreSQL│   │  Redis   │   │  Qdrant  │
    └──────────┘   └──────────┘   └──────────┘
```

## Stack Tecnológica

### Backend
- **Python 3.11+**
- **FastAPI** - API REST
- **LangGraph** - Orquestração de agentes
- **LangChain** - Integração com LLMs
- **SQLAlchemy** - ORM assíncrono
- **Pydantic** - Validação de dados

### Frontend
- **Next.js 14** - Framework React
- **TailwindCSS** - Estilização
- **React Query** - Gerenciamento de estado
- **Zustand** - Estado global

### Infraestrutura
- **PostgreSQL** - Banco de dados relacional
- **Redis** - Cache e rate limiting
- **Qdrant** - Vector store para RAG
- **Docker** - Containerização

## Agentes

### Router Agent
Analisa a query do usuário e determina quais agentes precisam ser acionados.

### Collector Agent
Coleta dados de fontes externas:
- Yahoo Finance (cotações, indicadores)
- CVM (documentos regulatórios)
- APIs de notícias

### RAG Agent
Realiza busca semântica na base de documentos vetorizados para encontrar informações relevantes.

### Analyst Agent
Processa os dados coletados e gera análises financeiras fundamentadas.

### Reporter Agent
Sintetiza as análises em respostas formatadas e compreensíveis.

## Instalação

### Pré-requisitos
- Python 3.11+
- Node.js 20+
- Docker e Docker Compose

### Desenvolvimento Local

1. Clone o repositório:
```bash
git clone https://github.com/your-org/financial-research-agent.git
cd financial-research-agent
```

2. Configure as variáveis de ambiente:
```bash
cp .env.example .env
# Edite .env com suas API keys
```

3. Inicie os serviços de infraestrutura:
```bash
docker-compose -f docker-compose.dev.yml up -d
```

4. Instale as dependências Python:
```bash
pip install -e ".[dev]"
```

5. Execute o backend:
```bash
python main.py
```

6. Em outro terminal, instale e execute o frontend:
```bash
cd frontend
npm install
npm run dev
```

7. Acesse:
- Frontend: http://localhost:3000
- API Docs: http://localhost:8000/docs

### Produção com Docker

```bash
docker-compose up -d
```

## Uso

### API REST

#### Submeter Query
```bash
curl -X POST http://localhost:8000/research/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Qual a situação financeira da Petrobras?"}'
```

#### Obter Cotação
```bash
curl http://localhost:8000/market/quote/PETR4
```

#### Upload de Documento
```bash
curl -X POST http://localhost:8000/documents/upload \
  -F "file=@balanco.pdf" \
  -F "company=Petrobras" \
  -F "ticker=PETR4" \
  -F "document_type=quarterly_report" \
  -F "reference_date=2024-01-01"
```

## Testes

```bash
# Executar todos os testes
pytest

# Com cobertura
pytest --cov=src --cov-report=html

# Apenas testes unitários
pytest tests/unit/

# Apenas testes de integração
pytest tests/integration/
```

## Linting e Formatação

```bash
# Lint
ruff check src/

# Formatação
ruff format src/

# Type checking
mypy src/

# Segurança
bandit -r src/
```

## Configuração

Principais variáveis de ambiente:

| Variável | Descrição | Default |
|----------|-----------|---------|
| `OPENAI_API_KEY` | API key da OpenAI | - |
| `ANTHROPIC_API_KEY` | API key da Anthropic | - |
| `DATABASE_URL` | URL do PostgreSQL | - |
| `REDIS_URL` | URL do Redis | redis://localhost:6379/0 |
| `QDRANT_HOST` | Host do Qdrant | localhost |
| `LLM_PROVIDER` | Provedor de LLM (openai/anthropic) | openai |
| `LLM_MODEL` | Modelo do LLM | gpt-4-turbo-preview |

## Disclaimer

Este projeto é apenas para fins educacionais e informativos. As análises geradas não constituem recomendação de investimento. Sempre consulte um profissional qualificado antes de tomar decisões financeiras.
