# Mercantil CLT Integration

Automação de simulação de crédito consignado CLT via **Banco Mercantil** (plataforma New Corban).

## Instalação Rápida

```bash
curl -sO https://raw.githubusercontent.com/rodrigomo-hub/mercantil-clt-integration/main/instalar.sh && bash instalar.sh
```

## Uso

### Python Direto

```python
from mercantil_clt import fluxo_completo_mercantil_clt
import json

# Uso simples (config padrão - testes)
resultado = fluxo_completo_mercantil_clt(
    cpf='130.702.519-60',
    data_nascimento='2005-04-19',  # OBRIGATORIO - precisa ser real
    # telefone opcional - se omitido, gera um aleatorio
)
print(json.dumps(resultado, indent=2))
```

### Retorno Padrão

```json
{
  "resultado": "aprovado|reprovado|reprovado_elegibilidade",
  "anotacao": "<motivo>",
  "email": null,
  "senha": null,
  "simulacoes": [
    {
      "qtd_parcelas": 24,
      "valor_parcela": 519.75,
      "valor_liberado": 6342.82,
      "valor_financiado": 6824.73,
      "valor_emprestimo": 6607.1,
      "taxa_juros_mes": 4.66,
      "taxa_juros_ano": 72.73,
      "taxa_cet_mes": 5.37,
      "taxa_cet_ano": 87.33,
      "valor_iof": 217.63,
      "valor_seguro": 264.28,
      "data_primeiro_vencimento": "2026-09-04T00:00:00",
      "data_ultimo_vencimento": "2028-08-04T00:00:00"
    }
  ],
  "cliente": {
    "nome": "NOME DO CLIENTE",
    "cpf": "130.702.519-60"
  },
  "operacao_id": "uuid",
  "matricula": "..."
}
```

## Configuração Multi-Empresa

Cada cliente/empresa tem seu próprio `subdomain`, `username` e `password` no New Corban:

```python
from mercantil_clt import fluxo_completo_mercantil_clt, NewCorbanConfig

config_empresa_x = NewCorbanConfig(
    subdomain="empresax",
    username="USUARIO_EMPRESA_X",
    password="SENHA_EMPRESA_X",
)

resultado = fluxo_completo_mercantil_clt(
    cpf='130.702.519-60',
    data_nascimento='2005-04-19',
    config=config_empresa_x,
)
```

### Via Variáveis de Ambiente

```bash
export NEWCORBAN_SUBDOMAIN="empresax"
export NEWCORBAN_USERNAME="USUARIO_EMPRESA_X"
export NEWCORBAN_PASSWORD="SENHA_EMPRESA_X"
```

```python
from mercantil_clt import fluxo_completo_mercantil_clt, NewCorbanConfig

config = NewCorbanConfig.from_env()
resultado = fluxo_completo_mercantil_clt(
    cpf='130.702.519-60',
    data_nascimento='2005-04-19',
    config=config,
)
```

## Fluxo Técnico

1. **Login New Corban** → JWT (24h)
2. **Listar usuários Mercantil** → pega primeiro não-bloqueado
3. **Session Check** → apt token (one-shot, busca antes de cada chamada)
4. **Consultar Matrícula CLT** → elegibilidade + operacao_id
5. **Simular CLT** → simulação final com prazos e taxas

## Tratamento de Erros

- **`resultado: "aprovado"`** → Simulação válida com opcões de parcelamento
- **`resultado: "reprovado"`** → Política de crédito reprovou (motivo em `anotacao`)
- **`resultado: "reprovado_elegibilidade"`** → Erro na elegibilidade (vínculo CTPS, idade, etc)

## Detalhes Importantes

- **Data de nascimento**: OBRIGATÓRIO e deve ser real/plausível
- **Telefone**: Opcional — se omitido, gera um aleatório (evita conflito com registros existentes)
- **Token apt**: Curta duração, buscado automaticamente antes de cada chamada
- **Login concorrente**: Se alguém acessar o front com o mesmo usuário New Corban, o JWT é invalidado. O módulo detecta isso e faz novo login automaticamente.
- **Rate limit**: Se o usuário Mercantil for bloqueado (muitas chamadas rápidas), tenta o próximo disponível na lista.

## Integração com n8n

### Opção 1: Execute Node (Python)

```python
const mercantil = require('child_process').execSync(`python -c "
from mercantil_clt import fluxo_completo_mercantil_clt
import json
resultado = fluxo_completo_mercantil_clt('${cpf}', data_nascimento='${data_nasc}')
print(json.dumps(resultado))
"`, {encoding: 'utf-8'})
return JSON.parse(mercantil)
```

### Opção 2: FastAPI Wrapper (recomendado)

Crie `mercantil_api.py` na VPS:

```python
from fastapi import FastAPI
from mercantil_clt import fluxo_completo_mercantil_clt, NewCorbanConfig
import os

app = FastAPI()

config = NewCorbanConfig.from_env()

@app.post("/simular_mercantil")
async def simular(cpf: str, data_nascimento: str, telefone: str = None):
    return fluxo_completo_mercantil_clt(cpf, telefone, data_nascimento, config=config)
```

```bash
pip install fastapi uvicorn
uvicorn mercantil_api.py --host 0.0.0.0 --port 8003
```

N8n: HTTP Request `POST http://localhost:8003/simular_mercantil`

## Changelog

### v1.0.0
- Mapeamento completo do fluxo Mercantil CLT
- Auto-geração de telefone aleatório
- Tratamento de sessão concorrente e rate-limit
- Config multi-empresa
- Auto-installer

## Suporte

- Issues: https://github.com/rodrigomo-hub/mercantil-clt-integration/issues
- Contato: Rodrigo (Corban)

## License

Proprietary - Corban
