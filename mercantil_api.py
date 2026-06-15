"""
FastAPI wrapper para Mercantil CLT Integration
Expõe a simulacao de credito como HTTP API para n8n

Deploy na VPS:
  pip install fastapi uvicorn
  uvicorn mercantil_api:app --host 0.0.0.0 --port 8003

Uso no n8n (credenciais no request):
  HTTP Request POST http://localhost:8003/simular
  Body: {
    "cpf": "130.702.519-60",
    "data_nascimento": "2005-04-19",
    "subdomain": "accred",
    "username": "ACCRE57309.master",
    "password": "Alice@1011*"
  }

Ou use variaveis de ambiente como fallback:
  NEWCORBAN_SUBDOMAIN=accred
  NEWCORBAN_USERNAME=...
  NEWCORBAN_PASSWORD=...
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
from mercantil_clt import fluxo_completo_mercantil_clt, NewCorbanConfig

app = FastAPI(title="Mercantil CLT Integration", version="1.0.0")


class SimularRequest(BaseModel):
    cpf: str
    data_nascimento: str
    telefone: str = None
    qtd_parcelas_opcoes: list = None
    # Credenciais opcionais (se não informadas, usa env vars)
    subdomain: str = None
    username: str = None
    password: str = None


class HealthResponse(BaseModel):
    status: str
    version: str


def get_config(req: SimularRequest) -> NewCorbanConfig:
    """
    Monta a config a partir do request ou env vars.
    Prioridade:
    1. Credenciais no request (req.subdomain, req.username, req.password)
    2. Variáveis de ambiente (NEWCORBAN_SUBDOMAIN, etc)
    """
    subdomain = req.subdomain or os.environ.get("NEWCORBAN_SUBDOMAIN")
    username = req.username or os.environ.get("NEWCORBAN_USERNAME")
    password = req.password or os.environ.get("NEWCORBAN_PASSWORD")

    if not subdomain or not username or not password:
        raise ValueError(
            "Credenciais New Corban ausentes. Envie no request ou configure env vars: "
            "NEWCORBAN_SUBDOMAIN, NEWCORBAN_USERNAME, NEWCORBAN_PASSWORD"
        )

    return NewCorbanConfig(
        subdomain=subdomain,
        username=username,
        password=password,
    )


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check"""
    return {"status": "ok", "version": "1.0.0"}


@app.post("/simular")
async def simular(req: SimularRequest):
    """
    Simula credito consignado CLT no Banco Mercantil
    
    Request:
      cpf: string (formato: XXX.XXX.XXX-XX ou XXXXXXXXXXX) [OBRIGATORIO]
      data_nascimento: string (formato: YYYY-MM-DD, ex: 2005-04-19) [OBRIGATORIO]
      telefone: string opcional (formato: (XX) 9XXXX-XXXX) - se omitido, gera aleatorio
      qtd_parcelas_opcoes: list opcional (ex: ["24", "36", "48"])
      subdomain: string opcional (ex: "accred") - se omitido, usa NEWCORBAN_SUBDOMAIN
      username: string opcional (ex: "ACCRE57309.master") - se omitido, usa NEWCORBAN_USERNAME
      password: string opcional - se omitido, usa NEWCORBAN_PASSWORD
    
    Response:
      resultado: "aprovado" | "reprovado" | "reprovado_elegibilidade"
      anotacao: motivo
      simulacoes: array com opcoes de parcelamento
      cliente: nome e cpf
      operacao_id: uuid da operacao
      matricula: matricula no banco
    """
    try:
        config = get_config(req)
        resultado = fluxo_completo_mercantil_clt(
            cpf=req.cpf,
            telefone=req.telefone,
            data_nascimento=req.data_nascimento,
            qtd_parcelas_opcoes=req.qtd_parcelas_opcoes,
            config=config,
        )
        return resultado
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
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
            {"POST": "/simular", "desc": "Simular credito CLT (credenciais no request ou env vars)"},
        ],
        "github": "https://github.com/rodrigomo-hub/mercantil-clt-new-corban",
        "exemplo_request": {
            "cpf": "130.702.519-60",
            "data_nascimento": "2005-04-19",
            "telefone": "(11) 98765-4321",
            "subdomain": "accred",
            "username": "ACCRE57309.master",
            "password": "Alice@1011*",
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
