"""
Integração New Corban -> Banco Mercantil (Consignado CLT)
Padrão de retorno: resultado / email / senha / simulacoes (Bankarize v3.1.0)

Fluxo:
1. Login New Corban -> JWT
2. listarUsuariosAPI -> usuarioBanco (ex: X468312)
3. session/check -> apt (token por requisicao)
4. consultarMatriculaCLT -> elegibilidade + operacao_id + idConsultaCLT
5. simularCLT -> simulacao final

NOTA: o token "apt" parece ter validade curta. Se uma chamada falhar com
erro de token/apt invalido, repetir o passo 3 (session/check) antes de
cada chamada que usa "apt".
"""

import json
import base64
import os
import urllib.parse
import requests
import random

DEFAULT_HEADERS = {
    "accept": "application/json, text/javascript, */*; q=0.01",
    "accept-language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
}


class NewCorbanConfig:
    """
    Configuracao por empresa/cliente New Corban.
    Cada cliente tem seu proprio subdomain, usuario e senha de login.
    Os dominios server/mercantil/auth seguem o padrao <subdomain>.newcorban.com.br
    e apiv2.newcorban.com.br (esse parece ser global, nao por subdomain).
    """

    def __init__(self, subdomain: str, username: str, password: str,
                 base_auth: str = "https://apiv2.newcorban.com.br",
                 base_server: str | None = None,
                 base_mercantil: str | None = None,
                 base_accred: str | None = None):
        self.subdomain = subdomain
        self.username = username
        self.password = password
        self.base_auth = base_auth
        self.base_server = base_server or f"https://server.newcorban.com.br"
        self.base_mercantil = base_mercantil or f"https://mercantil.newcorban.com.br"
        self.base_accred = base_accred or f"https://{subdomain}.newcorban.com.br"

    @property
    def headers(self) -> dict:
        return {
            **DEFAULT_HEADERS,
            "origin": self.base_accred,
            "referer": f"{self.base_accred}/",
        }

    @classmethod
    def from_env(cls, prefix: str = "NEWCORBAN") -> "NewCorbanConfig":
        """
        Carrega config de variaveis de ambiente:
        <PREFIX>_SUBDOMAIN, <PREFIX>_USERNAME, <PREFIX>_PASSWORD
        Opcionais: <PREFIX>_BASE_SERVER, <PREFIX>_BASE_MERCANTIL, <PREFIX>_BASE_ACCRED
        """
        subdomain = os.environ[f"{prefix}_SUBDOMAIN"]
        username = os.environ[f"{prefix}_USERNAME"]
        password = os.environ[f"{prefix}_PASSWORD"]
        return cls(
            subdomain=subdomain,
            username=username,
            password=password,
            base_server=os.environ.get(f"{prefix}_BASE_SERVER"),
            base_mercantil=os.environ.get(f"{prefix}_BASE_MERCANTIL"),
            base_accred=os.environ.get(f"{prefix}_BASE_ACCRED"),
        )


# Config padrao usada nos testes (Corban/accred) - mantida para compatibilidade
# com os scripts de teste individuais. Em producao, criar NewCorbanConfig por empresa.
_DEFAULT_CONFIG = NewCorbanConfig(
    subdomain="accred",
    username="ACCRE57309.master",
    password="Alice@1011*",
)


def login(config: NewCorbanConfig = _DEFAULT_CONFIG) -> str:
    """Autentica e retorna o JWT."""
    url = f"{config.base_auth}/api/v2/auth/login"
    payload = {
        "username": config.username,
        "password": config.password,
        "subdomain": config.subdomain,
    }
    headers = {**config.headers, "content-type": "application/json"}
    r = requests.post(url, json=payload, headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data["data"]["access_token"]


def get_usuario_banco(jwt: str, config: NewCorbanConfig = _DEFAULT_CONFIG) -> str:
    """Retorna o primeiro usuarioBanco nao bloqueado disponivel para Mercantil."""
    url = f"{config.base_server}/system/mercantil.php?action=listarUsuariosAPI"
    headers = {**config.headers, "authorization": f"Bearer {jwt}"}
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    usuarios = r.json()
    for u in usuarios:
        if not u.get("blocked"):
            return u["login"]
    raise RuntimeError("Nenhum usuario Mercantil disponivel (todos bloqueados)")


def get_apt(jwt: str, config: NewCorbanConfig = _DEFAULT_CONFIG) -> str:
    """Retorna o token apt (curta duracao) via session/check."""
    url = f"{config.base_server}/api/v2/session/check"
    headers = {**config.headers, "authorization": f"Bearer {jwt}", "content-type": "application/json"}
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()["apt"]


def _build_form(action: str, params: dict, apt: str) -> dict:
    """
    Monta o body x-www-form-urlencoded.
    Encoding do "params": JSON -> URL-encode -> base64
    (o URL-encode final do form e feito pelo requests automaticamente)
    """
    params_json = json.dumps(params, separators=(",", ":"), ensure_ascii=False)
    step1 = urllib.parse.quote(params_json, safe="")
    step2 = base64.b64encode(step1.encode()).decode()
    return {
        "action": action,
        "params": step2,
        "encode": "true",
        "apt": apt,
    }


def gerar_telefone_aleatorio(ddd: int = 11) -> str:
    """
    Gera um telefone aleatorio no formato (DDD) 9XXXX-XXXX
    para evitar conflito com telefones ja registrados.
    ddd: codigo de area (default 11 - Sao Paulo)
    """
    numero = f"{random.randint(90000000, 99999999)}"
    return f"({ddd}) {numero[:5]}-{numero[5:]}"


SESSION_INVALID_MARKERS = (
    "nova sessão foi identificada",
    "favor efetuar login novamente",
    "não foi possível autenticar este usuário",
    "token inválido",
    "unauthenticated",
)


def _is_session_invalid(resp_json: dict) -> bool:
    """Detecta se a resposta indica que a sessao/JWT foi invalidada (login concorrente)."""
    msg = (resp_json.get("mensagem") or resp_json.get("message") or "").lower()
    return any(m in msg for m in SESSION_INVALID_MARKERS)


def consultar_matricula_clt(jwt: str, usuario_banco: str, cpf: str, telefone: str,
                             data_nascimento: str, aderiu_seguro: bool = True,
                             matricula: str | None = None, _retry: bool = True,
                             config: NewCorbanConfig = _DEFAULT_CONFIG) -> tuple[dict, str]:
    """
    Consulta elegibilidade CLT no Mercantil.
    Retorna (resultado_json, jwt_atualizado) - jwt pode mudar se a sessao
    foi invalidada (login concorrente no front) e um novo login foi feito.
    """
    url = f"{config.base_mercantil}/?s=mercantil&f=consultarMatriculaCLT"
    apt = get_apt(jwt, config)
    params = {
        "usuarioBanco": usuario_banco,
        "cpf": cpf,
        "telefone": telefone,
        "aderiu_seguro": aderiu_seguro,
        "data_nascimento": data_nascimento,
        "matricula": matricula,
    }
    headers = {
        **config.headers,
        "authorization": f"Bearer {jwt}",
        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
    }
    body = _build_form("consultarMatriculaCLT", params, apt)
    r = requests.post(url, data=body, headers=headers, timeout=60)
    r.raise_for_status()
    result = r.json()

    if _retry and _is_session_invalid(result):
        novo_jwt = login(config)
        return consultar_matricula_clt(
            novo_jwt, usuario_banco, cpf, telefone, data_nascimento,
            aderiu_seguro, matricula, _retry=False, config=config
        )

    return result, jwt


def simular_clt(jwt: str, usuario_banco: str, cpf: str, operacao_id: str,
                 id_consulta_clt: int, valor_parcela: str | None, qtd_parcela: str | None,
                 aderiu_seguro: bool = True, _retry: bool = True,
                 config: NewCorbanConfig = _DEFAULT_CONFIG) -> tuple[dict, str]:
    """
    Roda a simulacao CLT no Mercantil.
    valor_parcela: string formato "683,07" (virgula decimal) OU None se nao houver proposta default
    qtd_parcela: string, ex "48" OU None se nao houver proposta default
    Retorna (resultado_json, jwt_atualizado).
    """
    url = f"{config.base_mercantil}/?s=mercantil&f=simularCLT"
    apt = get_apt(jwt, config)
    params = {
        "usuarioBanco": usuario_banco,
        "cpf": cpf,
        "operacao_id": operacao_id,
        "valor_parcela": valor_parcela,
        "qtd_parcela": qtd_parcela,
        "aderiu_seguro": aderiu_seguro,
        "idConsultaClt": id_consulta_clt,
    }
    headers = {
        **config.headers,
        "authorization": f"Bearer {jwt}",
        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
    }
    body = _build_form("simularCLT", params, apt)
    r = requests.post(url, data=body, headers=headers, timeout=60)
    r.raise_for_status()
    result = r.json()

    if _retry and _is_session_invalid(result):
        novo_jwt = login(config)
        return simular_clt(
            novo_jwt, usuario_banco, cpf, operacao_id, id_consulta_clt,
            valor_parcela, qtd_parcela, aderiu_seguro, _retry=False, config=config
        )

    return result, jwt


def montar_resultado_padrao(cpf: str, consulta_resp: dict, simulacoes: list,
                             motivo_reprovacao_simulacao: str | None = None) -> dict:
    """
    Monta o retorno padrao: resultado / email / senha / simulacoes
    (compatibilidade com padrao Bankarize v3.1.0).

    Possiveis valores de "resultado":
      - "aprovado": simulacoes contem ao menos uma opcao valida
      - "reprovado": elegibilidade ok mas politica de credito reprovou
                      (motivo em "anotacao")
      - "reprovado_elegibilidade": consultarMatriculaCLT ja retornou erro
                      (vinculo invalido, etc - motivo em "anotacao")
    """
    data = consulta_resp.get("data", {})
    detalhes = data.get("detalhes", {})
    cliente = detalhes.get("cliente", {})

    if consulta_resp.get("error"):
        resultado = "reprovado_elegibilidade"
        anotacao = consulta_resp.get("mensagem", "")
    elif simulacoes:
        resultado = "aprovado"
        anotacao = consulta_resp.get("mensagem", "")
    else:
        resultado = "reprovado"
        anotacao = motivo_reprovacao_simulacao or consulta_resp.get("mensagem", "")

    return {
        "resultado": resultado,
        "anotacao": anotacao,
        "email": None,   # Mercantil nao gera credenciais como Bankarize
        "senha": None,
        "simulacoes": simulacoes,
        "cliente": {
            "nome": cliente.get("nome"),
            "cpf": cpf,
        },
        "operacao_id": data.get("operacao_id"),
        "matricula": data.get("matricula"),
    }


def fluxo_completo_mercantil_clt(cpf: str, telefone: str | None = None, data_nascimento: str | None = None,
                                  qtd_parcelas_opcoes: list[str] | None = None,
                                  config: NewCorbanConfig = _DEFAULT_CONFIG) -> dict:
    """
    Executa o fluxo completo: login -> usuarioBanco -> consulta elegibilidade
    -> simulacao(oes) -> monta resultado padrao.

    cpf: "130.702.519-60"
    telefone: "(11) 98765-4321" OU None (gera um aleatorio)
    data_nascimento: "2005-04-19" (OBRIGATORIO - precisa ser real)
    qtd_parcelas_opcoes: lista de prazos para simular, ex ["24","36","48"]
                          Se None, usa apenas o valor default retornado na consulta.
    config: NewCorbanConfig do cliente/empresa. Default usa _DEFAULT_CONFIG (testes).
    """
    if telefone is None:
        telefone = gerar_telefone_aleatorio()
    
    jwt = login(config)
    usuario_banco = get_usuario_banco(jwt, config)

    consulta, jwt = consultar_matricula_clt(
        jwt, usuario_banco, cpf, telefone, data_nascimento, aderiu_seguro=True, config=config
    )

    if consulta.get("error", True):
        return montar_resultado_padrao(cpf, consulta, [])

    data = consulta["data"]
    operacao_id = data["operacao_id"]

    # idConsultaCLT vem dentro de data[<matricula>]["idConsultaCLT"]
    matricula = data["matricula"]
    id_consulta_clt = data[matricula]["idConsultaCLT"]

    proposta = data["detalhes"]["propostaEmprestimo"]

    if proposta.get("valorParcela") is not None:
        valor_parcela_default = f"{proposta['valorParcela']:.2f}".replace(".", ",")
        qtd_parcela_default = str(proposta["quantidadeParcelas"])
        prazos = qtd_parcelas_opcoes or [qtd_parcela_default]
    else:
        # sem proposta default - front envia null/null nesse caso
        valor_parcela_default = None
        prazos = [None]  # forca uma unica chamada com qtd_parcela=None

    simulacoes = []

    for qtd in prazos:
        sim, jwt = simular_clt(
            jwt, usuario_banco, cpf, operacao_id, id_consulta_clt,
            valor_parcela=valor_parcela_default,
            qtd_parcela=qtd,
            aderiu_seguro=True,
            config=config,
        )
        if not sim.get("error"):
            for tabela in sim["data"]["tabelaFlexivel"]:
                for prestacao in tabela["prestacao"]:
                    simulacoes.append({
                        "qtd_parcelas": prestacao["quantidadeParcelas"],
                        "valor_parcela": prestacao["valorParcela"],
                        "valor_liberado": prestacao["valorLiberado"],
                        "valor_financiado": prestacao["valorFinanciado"],
                        "valor_emprestimo": prestacao["valorEmprestimo"],
                        "taxa_juros_mes": prestacao["taxaJurosMes"],
                        "taxa_juros_ano": prestacao["taxaJurosAno"],
                        "taxa_cet_mes": prestacao["taxaCetMes"],
                        "taxa_cet_ano": prestacao["taxaCetAno"],
                        "valor_iof": prestacao["valorIof"],
                        "valor_seguro": prestacao.get("valorSeguro"),
                        "data_primeiro_vencimento": sim["data"]["dataPrimeiroVencimento"],
                        "data_ultimo_vencimento": prestacao["dataUltimoVencimento"],
                    })
        else:
            # reprovacao de negocio (politica de credito) - guarda o motivo
            return montar_resultado_padrao(cpf, consulta, simulacoes, motivo_reprovacao_simulacao=sim.get("mensagem"))

    return montar_resultado_padrao(cpf, consulta, simulacoes)


if __name__ == "__main__":
    # Uso simples (config padrao / testes):
    resultado = fluxo_completo_mercantil_clt(
        cpf="284.234.668-84",
        telefone="(96) 99146-5454",
        data_nascimento="1970-05-23",
        qtd_parcelas_opcoes=["48"],  # adicionar mais prazos conforme necessario
    )
    print(json.dumps(resultado, indent=2, ensure_ascii=False))

    # Uso multi-empresa (cada cliente/empresa tem seu subdomain/usuario/senha):
    #
    # config_empresa_x = NewCorbanConfig(
    #     subdomain="empresax",
    #     username="USUARIO_EMPRESA_X",
    #     password="SENHA_EMPRESA_X",
    # )
    # resultado = fluxo_completo_mercantil_clt(
    #     cpf="...", telefone="...", data_nascimento="...",
    #     config=config_empresa_x,
    # )
    #
    # Ou via variaveis de ambiente (NEWCORBAN_SUBDOMAIN, NEWCORBAN_USERNAME, NEWCORBAN_PASSWORD):
    # config_empresa_x = NewCorbanConfig.from_env()
