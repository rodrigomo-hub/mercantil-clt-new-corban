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
    
    Response (simplificado para o vendedor):
      resultado: "pre_aprovado" | "reprovado"
      cliente: {nome, cpf}
      anotacao: detalhes da oferta (prazo, valor, taxa) ou motivo da reprovação
    """
    try:
        config = get_config(req)
        resultado_completo = fluxo_completo_mercantil_clt(
            cpf=req.cpf,
            telefone=req.telefone,
            data_nascimento=req.data_nascimento,
            qtd_parcelas_opcoes=req.qtd_parcelas_opcoes,
            config=config,
        )
        
        # Simplificar para exibir ao vendedor - TUDO na anotacao + campos separados
        if resultado_completo["resultado"] == "aprovado" and resultado_completo["simulacoes"]:
            # Pega a melhor opção (primeira = maior prazo, menor parcela)
            melhor_opcao = resultado_completo["simulacoes"][0]
            nome_cliente = resultado_completo["cliente"]["nome"]
            cpf_cliente = resultado_completo["cliente"]["cpf"]
            anotacao = (
                f"✓ PRÉ-APROVADO NO BANCO MERCANTIL\n"
                f"Cliente: {nome_cliente}\n"
                f"CPF: {cpf_cliente}\n"
                f"Prazo: {melhor_opcao['qtd_parcelas']}x\n"
                f"Parcela: R$ {melhor_opcao['valor_parcela']:.2f}\n"
                f"Valor Liberado: R$ {melhor_opcao['valor_liberado']:.2f}\n"
                f"Taxa: {melhor_opcao['taxa_juros_mes']:.2f}% a.m."
            )
            return {
                "resultado": "pre_aprovado",
                "anotacao": anotacao,
                "cliente_nome": nome_cliente,
                "cliente_cpf": cpf_cliente,
                "prazo": f"{melhor_opcao['qtd_parcelas']}x",
                "valor_parcela": f"R$ {melhor_opcao['valor_parcela']:.2f}",
                "valor_liberado": f"R$ {melhor_opcao['valor_liberado']:.2f}",
                "taxa_juros_mes": f"{melhor_opcao['taxa_juros_mes']:.2f}% a.m.",
                "valor_parcela_numero": melhor_opcao['valor_parcela'],
                "valor_liberado_numero": melhor_opcao['valor_liberado'],
                "taxa_numero": melhor_opcao['taxa_juros_mes'],
            }
        else:
            nome_cliente = resultado_completo["cliente"]["nome"]
            cpf_cliente = resultado_completo["cliente"]["cpf"]
            motivo = resultado_completo["anotacao"]
            anotacao = (
                f"✗ REPROVADO NO BANCO MERCANTIL\n"
                f"Cliente: {nome_cliente}\n"
                f"CPF: {cpf_cliente}\n"
                f"Motivo: {motivo}"
            )
            return {
                "resultado": "reprovado",
                "anotacao": anotacao,
                "cliente_nome": nome_cliente,
                "cliente_cpf": cpf_cliente,
                "motivo": motivo,
            }
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
            {"POST": "/simular", "desc": "Simular credito CLT (retorno simplificado para vendedor)"},
        ],
        "github": "https://github.com/rodrigomo-hub/mercantil-clt-new-corban",
        "exemplo_request": {
            "cpf": "130.702.519-60",
            "data_nascimento": "2005-04-19",
            "subdomain": "accred",
            "username": "ACCRE57309.master",
            "password": "Alice@1011*",
        },
        "exemplo_resposta_aprovado": {
            "resultado": "pre_aprovado",
            "anotacao": "✓ PRÉ-APROVADO NO BANCO MERCANTIL\nCliente: VITOR MATEUS GODOIS DE SOUZA\nCPF: 130.702.519-60\nPrazo: 24x\nParcela: R$ 519.75\nValor Liberado: R$ 6342.82\nTaxa: 4.66% a.m.",
            "cliente_nome": "VITOR MATEUS GODOIS DE SOUZA",
            "cliente_cpf": "130.702.519-60",
            "prazo": "24x",
            "valor_parcela": "R$ 519.75",
            "valor_liberado": "R$ 6342.82",
            "taxa_juros_mes": "4.66% a.m.",
            "valor_parcela_numero": 519.75,
            "valor_liberado_numero": 6342.82,
            "taxa_numero": 4.66
        },
        "exemplo_resposta_reprovado": {
            "resultado": "reprovado",
            "anotacao": "✗ REPROVADO NO BANCO MERCANTIL\nCliente: NOME CLIENTE\nCPF: XXX.XXX.XXX-XX\nMotivo: Simulação não atendida pela política de crédito no momento.",
            "cliente_nome": "NOME CLIENTE",
            "cliente_cpf": "XXX.XXX.XXX-XX",
            "motivo": "Simulação não atendida pela política de crédito no momento."
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
