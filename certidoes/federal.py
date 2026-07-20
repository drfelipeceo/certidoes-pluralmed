"""
Certidão de Débitos Relativos a Créditos Tributários Federais e à Dívida Ativa da União
Receita Federal / PGFN — portal protegido por hCaptcha visual.
Retorna link direto; verificação manual pelo usuário.
"""
from .base import ResultadoCertidao, Status

URL_PORTAL = "https://servicos.receitafederal.gov.br/servico/certidoes/#/home/cnpj"


def consultar(cnpj14: str) -> ResultadoCertidao:
    cnpj_fmt = f"{cnpj14[:2]}.{cnpj14[2:5]}.{cnpj14[5:8]}/{cnpj14[8:12]}-{cnpj14[12:]}"
    return ResultadoCertidao(
        tipo="federal",
        nome="Certidão de Débitos Federais (RF/PGFN)",
        orgao="Receita Federal / PGFN",
        url=URL_PORTAL,
        status=Status.NAO_SUPORTADO,
        mensagem=(
            f"Acesse o portal → informe o CNPJ {cnpj_fmt} → clique Emitir Certidão."
        ),
    )
