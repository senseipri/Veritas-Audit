# Veritas Audit

Veritas is an AI compliance middleware: a trust layer that sits between chatbots and end users, audits every outgoing response against tenant-specific policy PDFs, and returns an allow/block decision with evidence.

## Product Vision

Most teams are building faster AI. Veritas builds safer AI.

- **Now (MVP):** RAG-powered compliance auditing with persistent violation logs.
- **Next (Product):** Multi-tenant API middleware with tenant-isolated policy vaults.
- **Future (SaaS):** Business console, risk trends, and downloadable legal reports.

## Core Architecture

- **Actor + Critic (LangGraph):** Groq-hosted Llama (`llama-3.3-70b-versatile`) with a retrieval-grounded audit loop.
- **Retriever:** Tenant-specific Chroma vector index + MiniLM embeddings for fast policy lookup.
- **Indexing:** PDF loader + semantic chunking + vector indexing (`scripts/reindex.py` or `POST /v1/tenants/{id}/reindex`).
- **Tier-0:** Fast PII intercept in `src/core/bedrock.py` (regex stub or Bedrock Guardrails when wired).
- **API Layer:** FastAPI ingress under `src/api/` for audit decisions, tenant onboarding, and log export.

## Multi-Tenant Data Layout

Each tenant is fully isolated on disk:

`tenants/<tenant_id>/truth/truth.pdf`  
`tenants/<tenant_id>/chroma_db/`  
`tenants/<tenant_id>/logs/audit_history.csv`

This enables one shared engine with separate “truth files” and logs per customer.

## API Endpoints

- `GET /health` - service health.
- `GET /v1/tenants` - list onboarded tenants.
- `POST /v1/tenants/{tenant_id}/truth` - upload tenant compliance PDF.
- `POST /v1/tenants/{tenant_id}/reindex` - rebuild tenant vector index from uploaded PDF.
- `POST /v1/audit` - audit chatbot output and return `ALLOW` or `BLOCK`.
- `GET /v1/tenants/{tenant_id}/logs` - fetch recent audit logs as JSON.
- `GET /v1/tenants/{tenant_id}/logs.csv` - download tenant CSV audit trail.

## Quick Start

1) Install dependencies:

```bash
pip install -r requirements.txt
```

2) Set environment:

```bash
cp .env.example .env
# Then edit .env with real keys
```

3) Run API:

```bash
uvicorn src.api.main:app --reload
```

Windows dev shortcut:

```powershell
./scripts/dev.ps1
```

4) (Optional) Run dashboard:

```bash
streamlit run app.py
```

## Example Workflow (Tenant Onboarding + Audit)

1. Upload tenant truth PDF:

```bash
curl -X POST "http://localhost:8000/v1/tenants/company-a/truth" \
  -H "x-api-key: key-company-a" \
  -F "file=@data/policy.pdf"
```

2. Build tenant index:

```bash
curl -X POST "http://localhost:8000/v1/tenants/company-a/reindex" \
  -H "x-api-key: key-company-a"
```

3. Audit a response:

```bash
curl -X POST "http://localhost:8000/v1/audit" \
  -H "x-api-key: key-company-a" \
  -H "Content-Type: application/json" \
  -d "{\"tenant_id\":\"company-a\",\"response_text\":\"We can share your SSN publicly.\"}"
```

## Security And Access Control

- **API key required** for all `/v1/*` routes via `x-api-key` header.
- **Tenant-bound keys** can only access their own tenant data.
- **Admin key** (`VERITAS_ADMIN_KEY`) can operate across tenants.
- **Rate limits** are enforced per API key (`VERITAS_RATE_LIMIT_PER_MINUTE`).

## Why This Matters

Veritas is not another chatbot. It is the control plane for chatbot safety:

- **Real-time interception** before risky text reaches users.
- **Policy-grounded decisions** with explainable rule snippets.
- **Compliance evidence** for legal, security, and audit teams.
- **API-first integration** for enterprise workflows.