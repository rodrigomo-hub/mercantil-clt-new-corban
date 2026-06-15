"""
FastAPI wrapper para Mercantil CLT Integration
Exponhe a simulacao de credito como HTTP API para n8n

Deploy na VPS:
  pip install fastapi uvicorn
  NEWCORBAN_SUBDOMAIN=... NEWCORBAN_USERNAME=... NEWCORBAN_PASSWORD=... \\
    uvicorn mercantil_api:app --host 0.0.0.0 --port 8003

Uso no n8n:
  HTTP Request POST http://localhost:8003/simular
  Body: {
    "cpf": "130.702.519-60",
    "data_nascimento": "2005-04-19",
    "telefone": "(opcional)"
  }
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
from mercantil_clt import fluxo_completo_mercantil_clt, NewCorbanConfig

app = FastAPI(title="Mercantil CLT Integration", version="1.0.0")

# Carrega config do New Corban via env vars
try:
    config = NewCorbanConfig.from_env()
except KeyError as e:
    raise RuntimeError(
        f"Variavel de ambiente ausente: {e}. "
        "Configure NEWCORBAN_SUBDOMAIN, NEWCORBAN_USERNAME, NEWCORBAN_PASSWORD"
    )


class SimularRequest(BaseModel):
    cpf: str
    data_nascimento: str
    telefone: str = None
    qtd_parcelas_opcoes: list = None


class HealthResponse(BaseModel):
    status: str
    version: str


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check"""
    return {"status": "ok", "version": "1.0.0"}


@app.post("/simular")
async def simular(req: SimularRequest):
    """
    Simula credito consignado CLT no Banco Mercantil
    
    Request:
      cpf: string (formato: XXX.XXX.XXX-XX ou XXXXXXXXXXX)
      data_nascimento: string (formato: YYYY-MM-DD, ex: 2005-04-19)
      telefone: string opcional (formato: (XX) 9XXXX-XXXX) - se omitido, gera aleatorio
      qtd_parcelas_opcoes: list opcional (ex: ["24", "36", "48"])
    
    Response:
      resultado: "aprovado" | "reprovado" | "reprovado_elegibilidade"
      anotacao: motivo
      simulacoes: array com opcoes de parcelamento
      cliente: nome e cpf
      operacao_id: uuid da operacao
      matricula: matricula no banco
    """
    try:
        resultado = fluxo_completo_mercantil_clt(
            cpf=req.cpf,
            telefone=req.telefone,
            data_nascimento=req.data_nascimento,
            qtd_parcelas_opcoes=req.qtd_parcelas_opcoes,
            config=config,
        )
        return resultado
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    """Info do servico"""
    return {
        "nome": "Mercantil CLT Integration API",
        "versao": "1.0.0",
        "endpoints": [
            {"GET": "/health", "desc": "Health check"},
            {"POST": "/simular", "desc": "Simular credito CLT"},
        ],
        "github": "https://github.com/rodrigomo-hub/mercantil-clt-integration",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
