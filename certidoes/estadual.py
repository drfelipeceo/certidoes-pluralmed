"""
Certidão Negativa Estadual — SEFAZ de cada estado.
Mapeamento dos portais oficiais de todos os 27 estados/DF.
Automação via Playwright para CE (sem captcha).
"""
from .base import ResultadoCertidao, Status, HEADERS_NAVEGADOR

# Portal e serviço de certidão de cada SEFAZ.
# URL_CERTIDAO: link direto para o serviço de emissão quando conhecido.
# URL_PORTAL:   página principal da SEFAZ do estado.
SEFAZ = {
    "AC": {
        "nome": "Acre", "orgao": "SEFAZ-AC",
        "url": "https://www.sefaznet.ac.gov.br/sefaznet/",
    },
    "AL": {
        "nome": "Alagoas", "orgao": "SEFAZ-AL",
        "url": "https://www.sefaz.al.gov.br/",
    },
    "AP": {
        "nome": "Amapá", "orgao": "SEFAZ-AP",
        "url": "https://www.sefaz.ap.gov.br/",
    },
    "AM": {
        "nome": "Amazonas", "orgao": "SEFAZ-AM",
        "url": "https://www.sefaz.am.gov.br/",
    },
    "BA": {
        "nome": "Bahia", "orgao": "SEFAZ-BA",
        "url": "https://www.sefaz.ba.gov.br/contribuinte/tributos/certidao.htm",
    },
    "CE": {
        "nome": "Ceará", "orgao": "SEFAZ-CE",
        "url": "https://cnd.sefaz.ce.gov.br/",
    },
    "DF": {
        "nome": "Distrito Federal", "orgao": "SEF-DF",
        "url": "https://ww1.receita.fazenda.df.gov.br/",
    },
    "ES": {
        "nome": "Espírito Santo", "orgao": "SEFAZ-ES",
        "url": "https://internet.sefaz.es.gov.br/agenciavirtual/certidao/",
    },
    "GO": {
        "nome": "Goiás", "orgao": "SEFAZ-GO",
        "url": "https://www.sefaz.go.gov.br/Contribuinte/certidoes.asp",
    },
    "MA": {
        "nome": "Maranhão", "orgao": "SEFAZ-MA",
        "url": "https://www.sefaz.ma.gov.br/",
    },
    "MT": {
        "nome": "Mato Grosso", "orgao": "SEFAZ-MT",
        "url": "https://www.sefaz.mt.gov.br/cnd/",
    },
    "MS": {
        "nome": "Mato Grosso do Sul", "orgao": "SEFAZ-MS",
        "url": "https://www.sefaz.ms.gov.br/",
    },
    "MG": {
        "nome": "Minas Gerais", "orgao": "SEF-MG",
        "url": "https://servicos.fazenda.mg.gov.br/cnd/",
    },
    "PA": {
        "nome": "Pará", "orgao": "SEFA-PA",
        "url": "https://cnd.sefa.pa.gov.br/cnd/",
    },
    "PB": {
        "nome": "Paraíba", "orgao": "SEFAZ-PB",
        "url": "https://www.receita.pb.gov.br/",
    },
    "PR": {
        "nome": "Paraná", "orgao": "SEFA-PR",
        "url": "https://cnd.receita.fazenda.pr.gov.br/",
    },
    "PE": {
        "nome": "Pernambuco", "orgao": "SEFAZ-PE",
        "url": "https://efisco.sefaz.pe.gov.br/",
    },
    "PI": {
        "nome": "Piauí", "orgao": "SEFAZ-PI",
        "url": "https://www.sefaz.pi.gov.br/",
    },
    "RJ": {
        "nome": "Rio de Janeiro", "orgao": "SEFAZ-RJ",
        "url": "https://www4.fazenda.rj.gov.br/consultaCND/",
    },
    "RN": {
        "nome": "Rio Grande do Norte", "orgao": "SET-RN",
        "url": "https://www.set.rn.gov.br/",
    },
    "RS": {
        "nome": "Rio Grande do Sul", "orgao": "SEFAZ-RS",
        "url": "https://receita.fazenda.rs.gov.br/inicial/certidao/",
    },
    "RO": {
        "nome": "Rondônia", "orgao": "SEFIN-RO",
        "url": "https://www.sefin.ro.gov.br/",
    },
    "RR": {
        "nome": "Roraima", "orgao": "SEFAZ-RR",
        "url": "https://www.fazenda.rr.gov.br/",
    },
    "SC": {
        "nome": "Santa Catarina", "orgao": "SEF-SC",
        "url": "https://sat.sef.sc.gov.br/tax.NET/Sat.Certidao.Web/Inicio.aspx",
    },
    "SP": {
        "nome": "São Paulo", "orgao": "SEFAZ-SP",
        "url": "https://www10.fazenda.sp.gov.br/CertidaoNegativaDeb/Pages/CertidaoNegativa.aspx",
    },
    "SE": {
        "nome": "Sergipe", "orgao": "SEFAZ-SE",
        "url": "https://www.sefaz.se.gov.br/",
    },
    "TO": {
        "nome": "Tocantins", "orgao": "SEFAZ-TO",
        "url": "https://www.sefaz.to.gov.br/",
    },
}

ESTADOS = sorted(SEFAZ.keys())

_URL_CE = "https://consultapublica.sefaz.ce.gov.br/certidaonegativa/preparar-consultar"


def _consultar_ce(cnpj14: str) -> ResultadoCertidao | None:
    """Playwright + SEFAZ-CE (sem captcha). None se falhou."""
    import re as _re
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    cnpj_fmt = f"{cnpj14[:2]}.{cnpj14[2:5]}.{cnpj14[5:8]}/{cnpj14[8:12]}-{cnpj14[12:]}"
    base = dict(
        tipo="estadual",
        nome="Certidão Negativa Estadual — Ceará",
        orgao="SEFAZ-CE",
        url=_URL_CE,
    )

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            )
            ctx = browser.new_context(
                user_agent=HEADERS_NAVEGADOR["User-Agent"],
                viewport={"width": 1280, "height": 900},
            )
            page = ctx.new_page()

            try:
                page.goto(_URL_CE, timeout=30000, wait_until="networkidle")
                page.wait_for_timeout(1500)

                # Selecionar radio CNPJ
                for sel in ['input[value="CNPJ"]', 'input[value="cnpj"]',
                            'label:has-text("CNPJ")', 'span:has-text("CNPJ")']:
                    try:
                        page.click(sel, timeout=3000)
                        break
                    except Exception:
                        continue

                page.wait_for_timeout(400)

                # Preencher campo CNPJ
                filled = False
                for sel in ['input[name*="numero"]', 'input[name*="cnpj"]', 'input[id*="cnpj"]',
                            'input[placeholder*="CNPJ"]', 'input[placeholder*="número"]',
                            'input[type="text"]']:
                    try:
                        fld = page.locator(sel).first
                        if fld.is_visible(timeout=2000):
                            fld.fill(cnpj14)
                            filled = True
                            break
                    except Exception:
                        continue

                if not filled:
                    browser.close()
                    return None

                # Submeter formulário
                for sel in ['button:has-text("Pesquisar")', 'button:has-text("Consultar")',
                            'input[value="Pesquisar"]', 'button[type="submit"]']:
                    try:
                        btn = page.locator(sel).first
                        if btn.is_visible(timeout=3000):
                            btn.click()
                            break
                    except Exception:
                        continue

                # Aguardar resultado
                try:
                    page.wait_for_selector(
                        'table, .resultado, [class*="result"], [class*="certidao"]',
                        timeout=15000,
                    )
                except PWTimeout:
                    pass

                page.wait_for_timeout(2000)
                html = page.content()
                html_lower = html.lower()

                # Extrair validade
                validade = None
                m = _re.search(r'validade[^0-9]{0,30}(\d{2}/\d{2}/\d{4})', html_lower)
                if not m:
                    m = _re.search(r'(\d{2}/\d{2}/\d{4})', html)
                if m:
                    validade = m.group(1)

                browser.close()

            except PWTimeout:
                browser.close()
                return None

        neg = ["certidão negativa", "certidao negativa", "nada consta", "sem débito",
               "sem debito", "negativa de débito", "negativa de debito"]
        pos = ["certidão positiva", "certidao positiva", "possui débito", "possui debito"]
        err = ["não encontrado", "nao encontrado", "cnpj inválido", "cnpj invalido",
               "não cadastrado", "nao cadastrado"]

        if any(k in html_lower for k in neg):
            return ResultadoCertidao(
                **base, status=Status.REGULAR, validade=validade,
                mensagem="Certidão Negativa Estadual do Ceará. Nenhum débito estadual encontrado.",
            )
        if any(k in html_lower for k in pos):
            return ResultadoCertidao(
                **base, status=Status.IRREGULAR,
                mensagem=f"Existem débitos estaduais no Ceará para o CNPJ {cnpj_fmt}.",
            )
        if any(k in html_lower for k in err):
            return ResultadoCertidao(
                **base, status=Status.ERRO,
                mensagem=f"CNPJ {cnpj_fmt} não encontrado no cadastro da SEFAZ-CE.",
            )

        return None

    except Exception:
        return None


def consultar(cnpj14: str, estado: str) -> ResultadoCertidao:
    estado = estado.upper().strip()
    info = SEFAZ.get(estado)

    if not info:
        return ResultadoCertidao(
            tipo="estadual",
            nome="Certidão Negativa Estadual",
            orgao="SEFAZ",
            status=Status.ERRO,
            mensagem=f"Estado '{estado}' não reconhecido.",
        )

    # Automação disponível para CE
    if estado == "CE":
        resultado = _consultar_ce(cnpj14)
        if resultado is not None:
            return resultado

    cnpj_fmt = f"{cnpj14[:2]}.{cnpj14[2:5]}.{cnpj14[5:8]}/{cnpj14[8:12]}-{cnpj14[12:]}"
    return ResultadoCertidao(
        tipo="estadual",
        nome=f"Certidão Negativa Estadual — {info['nome']}",
        orgao=info["orgao"],
        status=Status.NAO_SUPORTADO,
        mensagem=(
            f"Acesse o portal da {info['orgao']} e informe o CNPJ "
            f"{cnpj_fmt} para emitir a certidão estadual."
        ),
        url=info["url"],
    )
