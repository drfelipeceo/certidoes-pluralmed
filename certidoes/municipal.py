"""
Certidão Negativa Municipal (ISS / Tributos Municipais).

Automação implementada para municípios do Ceará:
  - Fortaleza   : Playwright + ddddocr (captcha de imagem próprio)
  - Caucaia     : HTTP GET simples (PHP, sem captcha)
  - SpeedGov    : Playwright (Sobral, Juazeiro do Norte, Maracanaú, Maranguape, Iguatu, Crato, Itapipoca)

Para municípios sem automação, exibe link direto ao portal.
"""
import io
import re
import unicodedata
import warnings

import requests
from urllib3.exceptions import InsecureRequestWarning

from .base import ResultadoCertidao, Status, HEADERS_NAVEGADOR

warnings.filterwarnings("ignore", category=InsecureRequestWarning)

# ─── Mapeamento de municípios ─────────────────────────────────────────────────
# Chave: "MUNICIPIO_UF" (normalizado: sem acentos, maiúsculo)
# automacao: "fortaleza" | "caucaia" | "speedgov" | None (só link)
MUNICIPIOS: dict[str, dict] = {
    # ── Ceará ──────────────────────────────────────────────────────────────
    "FORTALEZA_CE": {
        "nome": "Fortaleza", "orgao": "SEFIN-FOR",
        "url": "https://grpfordam.sefin.fortaleza.ce.gov.br/grpfor/pagesPublic/certidoes/emitirCertidao.seam",
        "automacao": "fortaleza",
    },
    "CAUCAIA_CE": {
        "nome": "Caucaia", "orgao": "SEFIN-Caucaia",
        "url": "https://servicos.sefin.caucaia.ce.gov.br/resultado_cnd_tributo.php",
        "automacao": "caucaia",
    },
    "SOBRAL_CE": {
        "nome": "Sobral", "orgao": "SEMF-Sobral",
        "url": "https://servicos2.speedgov.com.br/sobral/pages/certidao_contribuinte",
        "automacao": "speedgov",
    },
    "JUAZEIRO DO NORTE_CE": {
        "nome": "Juazeiro do Norte", "orgao": "SEMF-Juazeiro",
        "url": "https://servicos2.speedgov.com.br/juazeirodonorte/pages/certidao_contribuinte",
        "automacao": "speedgov",
    },
    "MARACANAU_CE": {
        "nome": "Maracanaú", "orgao": "SEMF-Maracanaú",
        "url": "https://servicos2.speedgov.com.br/maracanau/pages/certidao_contribuinte",
        "automacao": "speedgov",
    },
    "MARANGUAPE_CE": {
        "nome": "Maranguape", "orgao": "SEMF-Maranguape",
        "url": "https://servicos2.speedgov.com.br/maranguape/pages/certidao_contribuinte",
        "automacao": "speedgov",
    },
    "IGUATU_CE": {
        "nome": "Iguatu", "orgao": "SEMF-Iguatu",
        "url": "https://servicos2.speedgov.com.br/iguatu/pages/certidao_contribuinte",
        "automacao": "speedgov",
    },
    "CRATO_CE": {
        "nome": "Crato", "orgao": "SEMF-Crato",
        "url": "https://servicos2.speedgov.com.br/crato/pages/certidao_contribuinte",
        "automacao": "speedgov",
    },
    "ITAPIPOCA_CE": {
        "nome": "Itapipoca", "orgao": "SEMF-Itapipoca",
        "url": "https://servicos2.speedgov.com.br/itapipoca/pages/certidao_contribuinte",
        "automacao": "speedgov",
    },
    # ── Capitais e outros municípios (somente link) ─────────────────────────
    "SAO PAULO_SP": {
        "nome": "São Paulo", "orgao": "SF-SP",
        "url": "https://nfpaulistana.prefeitura.sp.gov.br/contribuintes/CND_contribuintes.aspx",
    },
    "RIO DE JANEIRO_RJ": {
        "nome": "Rio de Janeiro", "orgao": "SMF-RJ",
        "url": "https://carioca.rio/servicos/certidao-negativa-de-tributos-municipais/",
    },
    "BELO HORIZONTE_MG": {
        "nome": "Belo Horizonte", "orgao": "SMAR-BH",
        "url": "https://bhiss.pbh.gov.br/bhiss-web/certidao",
    },
    "PORTO ALEGRE_RS": {
        "nome": "Porto Alegre", "orgao": "SMF-POA",
        "url": "https://issonline.procempa.com.br/issonline/",
    },
    "CURITIBA_PR": {
        "nome": "Curitiba", "orgao": "SMF-CWB",
        "url": "https://cnd.curitiba.pr.gov.br/",
    },
    "MANAUS_AM": {
        "nome": "Manaus", "orgao": "SEMEF-MAO",
        "url": "https://semef.manaus.am.gov.br/",
    },
    "SALVADOR_BA": {
        "nome": "Salvador", "orgao": "SEFAZ-SSA",
        "url": "https://sistemas.sefaz.salvador.ba.gov.br/certidao/",
    },
    "RECIFE_PE": {
        "nome": "Recife", "orgao": "SF-REC",
        "url": "https://issqn.recife.pe.gov.br/certidoes/",
    },
    "BRASILIA_DF": {
        "nome": "Brasília", "orgao": "SEF-DF",
        "url": "https://ww1.receita.fazenda.df.gov.br/",
    },
    "GOIANIA_GO": {
        "nome": "Goiânia", "orgao": "SEFIN-GYN",
        "url": "https://atendimento.goiania.go.gov.br/",
    },
    "BELEM_PA": {
        "nome": "Belém", "orgao": "SEFIN-BEL",
        "url": "https://sefin.belem.pa.gov.br/",
    },
    "SAO LUIS_MA": {
        "nome": "São Luís", "orgao": "SEMC-SLZ",
        "url": "https://semcsc.saoluis.ma.gov.br/",
    },
    "MACEIO_AL": {
        "nome": "Maceió", "orgao": "SEFAZ-MCZ",
        "url": "https://servicos.maceio.al.gov.br/",
    },
    "NATAL_RN": {
        "nome": "Natal", "orgao": "SMF-NAT",
        "url": "https://natal.rn.gov.br/semf/",
    },
    "JOAO PESSOA_PB": {
        "nome": "João Pessoa", "orgao": "SEFIN-JPA",
        "url": "https://www.joaopessoa.pb.gov.br/",
    },
    "TERESINA_PI": {
        "nome": "Teresina", "orgao": "SEMF-THE",
        "url": "https://semf.teresina.pi.gov.br/",
    },
    "CAMPO GRANDE_MS": {
        "nome": "Campo Grande", "orgao": "SEFIN-CGR",
        "url": "https://www.campogrande.ms.gov.br/sefin/",
    },
    "CUIABA_MT": {
        "nome": "Cuiabá", "orgao": "SMFA-CGB",
        "url": "https://www.cuiaba.mt.gov.br/smfa/",
    },
    "PORTO VELHO_RO": {
        "nome": "Porto Velho", "orgao": "SEMFAZ-PVH",
        "url": "https://semfaz.portovelho.ro.gov.br/",
    },
    "MACAPA_AP": {
        "nome": "Macapá", "orgao": "SEFAZ-MCP",
        "url": "https://www.macapa.ap.gov.br/",
    },
    "BOA VISTA_RR": {
        "nome": "Boa Vista", "orgao": "SMAD-BVB",
        "url": "https://www.boavista.rr.gov.br/",
    },
    "RIO BRANCO_AC": {
        "nome": "Rio Branco", "orgao": "SMF-RBR",
        "url": "https://www.riobranco.ac.gov.br/",
    },
    "PALMAS_TO": {
        "nome": "Palmas", "orgao": "SEFIN-PMC",
        "url": "https://sefin.palmas.to.gov.br/",
    },
    "ARACAJU_SE": {
        "nome": "Aracaju", "orgao": "SEMAT-AJU",
        "url": "https://www.aracaju.se.gov.br/servicos_municipais/",
    },
    "VITORIA_ES": {
        "nome": "Vitória", "orgao": "SEFIN-VIX",
        "url": "https://sistemas.vitoria.es.gov.br/",
    },
    "FLORIANOPOLIS_SC": {
        "nome": "Florianópolis", "orgao": "SEF-FLN",
        "url": "https://e-gov.betha.com.br/e-nota-contribuinte-web/certidoes.faces",
    },
    "CAMPINAS_SP": {
        "nome": "Campinas", "orgao": "SMF-CPQ",
        "url": "https://nfpaulistana.prefeitura.sp.gov.br/contribuintes/CND_contribuintes.aspx",
    },
    "GUARULHOS_SP": {
        "nome": "Guarulhos", "orgao": "SF-GRU",
        "url": "https://servicos.guarulhos.sp.gov.br/",
    },
    "SANTOS_SP": {
        "nome": "Santos", "orgao": "SF-STS",
        "url": "https://www.santos.sp.gov.br/",
    },
    "RIBEIRAO PRETO_SP": {
        "nome": "Ribeirão Preto", "orgao": "SF-RPO",
        "url": "https://www.ribeiraopreto.sp.gov.br/",
    },
    "SOROCABA_SP": {
        "nome": "Sorocaba", "orgao": "SF-SOC",
        "url": "https://www.sorocaba.sp.gov.br/",
    },
    "UBERLANDIA_MG": {
        "nome": "Uberlândia", "orgao": "SMF-UDI",
        "url": "https://www.uberlandia.mg.gov.br/",
    },
    "CONTAGEM_MG": {
        "nome": "Contagem", "orgao": "SMF-CTG",
        "url": "https://www.contagem.mg.gov.br/",
    },
    "NITEROI_RJ": {
        "nome": "Niterói", "orgao": "SMF-NIR",
        "url": "https://smaonline.niteroi.rj.gov.br/",
    },
    "JOINVILLE_SC": {
        "nome": "Joinville", "orgao": "SEFAZ-JVL",
        "url": "https://sefaz.joinville.sc.gov.br/",
    },
    "LONDRINA_PR": {
        "nome": "Londrina", "orgao": "SMFA-LDB",
        "url": "https://smfa.londrina.pr.gov.br/",
    },
    "MARINGA_PR": {
        "nome": "Maringá", "orgao": "SF-MGF",
        "url": "https://www.maringa.pr.gov.br/fazenda/",
    },
    "CAXIAS DO SUL_RS": {
        "nome": "Caxias do Sul", "orgao": "SMF-CXS",
        "url": "https://smf.caxias.rs.gov.br/",
    },
    "PELOTAS_RS": {
        "nome": "Pelotas", "orgao": "SMF-PEL",
        "url": "https://smf.pelotas.rs.gov.br/",
    },
}


# ─── Funções de automação ─────────────────────────────────────────────────────

def _neg_keywords(html: str) -> bool:
    return any(k in html for k in [
        "certidão negativa", "certidao negativa", "nada consta", "não consta débito",
        "nao consta debito", "isento de débito", "isento de debito", "negativa de débito",
        "negativa de debito", "sem pendências", "sem pendencias",
    ])


def _pos_keywords(html: str) -> bool:
    return any(k in html for k in [
        "certidão positiva", "certidao positiva", "possui débito", "possui debito",
        "há débitos", "ha debitos", "irregular", "inadimplente",
    ])


def _consultar_caucaia(cnpj14: str, info: dict) -> ResultadoCertidao | None:
    """Caucaia: GET PHP simples, sem captcha."""
    url = f"https://servicos.sefin.caucaia.ce.gov.br/resultado_cnd_tributo.php?ps=tipo&CPFouCNPJ={cnpj14}"
    cnpj_fmt = f"{cnpj14[:2]}.{cnpj14[2:5]}.{cnpj14[5:8]}/{cnpj14[8:12]}-{cnpj14[12:]}"
    base = dict(tipo="municipal", nome="Certidão Negativa Municipal — Caucaia",
                orgao="SEFIN-Caucaia", url=info["url"])
    try:
        resp = requests.get(url, headers=HEADERS_NAVEGADOR, verify=False, timeout=20)
        html = resp.text.lower()
        if _neg_keywords(html):
            return ResultadoCertidao(**base, status=Status.REGULAR,
                                     mensagem="Certidão Negativa Municipal de Caucaia emitida com sucesso.")
        if _pos_keywords(html):
            return ResultadoCertidao(**base, status=Status.IRREGULAR,
                                     mensagem=f"Existem débitos municipais em Caucaia para o CNPJ {cnpj_fmt}.")
        return None
    except Exception:
        return None


def _consultar_speedgov(cnpj14: str, info: dict) -> ResultadoCertidao | None:
    """Portais SpeedGov (sem captcha). Tenta com CNPJ via certidao_contribuinte."""
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    cidade = info["nome"]
    cnpj_fmt = f"{cnpj14[:2]}.{cnpj14[2:5]}.{cnpj14[5:8]}/{cnpj14[8:12]}-{cnpj14[12:]}"
    base = dict(tipo="municipal", nome=f"Certidão Negativa Municipal — {cidade}",
                orgao=info["orgao"], url=info["url"])

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(user_agent=HEADERS_NAVEGADOR["User-Agent"],
                                      viewport={"width": 1280, "height": 720})
            page = ctx.new_page()

            try:
                page.goto(info["url"], timeout=30000, wait_until="domcontentloaded")
                page.wait_for_timeout(2000)

                # Preencher CNPJ (SpeedGov usa campo CPF/CNPJ unificado)
                filled = False
                for sel in ['input[name*="cpf"]', 'input[name*="cnpj"]', 'input[id*="cpf"]',
                            'input[placeholder*="CPF"]', 'input[placeholder*="CNPJ"]',
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

                # Submeter
                for sel in ['button:has-text("Emitir")', 'button:has-text("Consultar")',
                            'button:has-text("Gerar")', 'button[type="submit"]', 'input[type="submit"]']:
                    try:
                        btn = page.locator(sel).first
                        if btn.is_visible(timeout=3000):
                            btn.click()
                            break
                    except Exception:
                        continue

                page.wait_for_timeout(5000)
                html = page.content()
                html_lower = html.lower()
                browser.close()

            except PWTimeout:
                browser.close()
                return None

        # Requer Inscrição Econômica ou CNPJ não encontrado nesse fluxo
        if any(k in html_lower for k in ["inscrição econômica", "inscricao economica",
                                          "não encontrado", "nao encontrado",
                                          "não localizado", "nao localizado"]):
            return None  # Cai no fallback de link

        if _neg_keywords(html_lower):
            return ResultadoCertidao(**base, status=Status.REGULAR,
                                     mensagem=f"Certidão Negativa Municipal de {cidade} emitida com sucesso.")
        if _pos_keywords(html_lower):
            return ResultadoCertidao(**base, status=Status.IRREGULAR,
                                     mensagem=f"Existem débitos municipais em {cidade} para o CNPJ {cnpj_fmt}.")
        return None

    except Exception:
        return None


def _consultar_fortaleza(cnpj14: str, info: dict) -> ResultadoCertidao | None:
    """Fortaleza: JSF Seam + captcha de imagem (ddddocr). Até 5 tentativas."""
    import base64 as _b64
    import ddddocr
    from PIL import Image
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    URL = info["url"]
    cnpj_fmt = f"{cnpj14[:2]}.{cnpj14[2:5]}.{cnpj14[5:8]}/{cnpj14[8:12]}-{cnpj14[12:]}"
    base = dict(tipo="municipal", nome="Certidão Negativa Municipal — Fortaleza",
                orgao="SEFIN-FOR", url=URL)

    _ocr = ddddocr.DdddOcr(show_ad=False)
    _ocr_beta = ddddocr.DdddOcr(beta=True, show_ad=False)

    def _ocr_captcha(img_bytes: bytes) -> str:
        r1 = "".join(c for c in _ocr.classification(img_bytes) if c.isascii() and c.isalnum())
        r2 = "".join(c for c in _ocr_beta.classification(img_bytes) if c.isascii() and c.isalnum())
        img = Image.open(io.BytesIO(img_bytes)).convert("L")
        buf = io.BytesIO()
        img.point(lambda x: 0 if x < 180 else 255, "L").save(buf, format="PNG")
        r3 = "".join(c for c in _ocr.classification(buf.getvalue()) if c.isascii() and c.isalnum())
        opts = [r for r in [r1, r2, r3] if r]
        return max(opts, key=len) if opts else ""

    for _tentativa in range(5):
        captcha_bytes: bytes | None = None

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                ctx = browser.new_context(user_agent=HEADERS_NAVEGADOR["User-Agent"],
                                          viewport={"width": 1280, "height": 900})
                page = ctx.new_page()

                def _capturar(resp):
                    nonlocal captcha_bytes
                    if "captcha" in resp.url.lower():
                        try:
                            captcha_bytes = resp.body()
                        except Exception:
                            pass

                page.on("response", _capturar)

                try:
                    page.goto(URL, timeout=30000, wait_until="domcontentloaded")
                    page.wait_for_timeout(2500)

                    # Selecionar tipo de certidão (dropdown) — preferir "Todos" ou "Tributos"
                    try:
                        sel_el = page.locator("select").first
                        if sel_el.is_visible(timeout=3000):
                            opts = page.eval_on_selector(
                                "select",
                                "el => Array.from(el.options).map(o => ({v:o.value,t:o.text.toLowerCase()}))"
                            )
                            chosen = None
                            for o in opts:
                                if any(k in o["t"] for k in ["tributo", "todos", "municipal", "geral"]):
                                    chosen = o["v"]
                                    break
                            if not chosen and opts:
                                chosen = opts[-1]["v"]
                            if chosen:
                                sel_el.select_option(chosen)
                                page.wait_for_timeout(500)
                    except Exception:
                        pass

                    # Selecionar Pessoa Jurídica
                    for sel in ['input[value="J"]', 'input[value="JURIDICA"]', 'input[value="juridica"]',
                                'label:has-text("Jurídica")', 'label:has-text("Juridica")']:
                        try:
                            page.click(sel, timeout=2000)
                            break
                        except Exception:
                            continue

                    page.wait_for_timeout(400)

                    # Preencher CNPJ
                    for sel in ['input[name*="cpfCnpj"]', 'input[name*="cpf"]', 'input[name*="cnpj"]',
                                'input[id*="cpf"]', 'input[id*="cnpj"]', 'input[type="text"]']:
                        try:
                            fld = page.locator(sel).last
                            if fld.is_visible(timeout=2000):
                                fld.fill(cnpj14)
                                break
                        except Exception:
                            continue

                    # Aguardar captcha carregar
                    page.wait_for_timeout(2000)

                    # Tentar obter bytes do captcha via fetch JS se não veio pelo interceptor
                    if not captcha_bytes:
                        try:
                            src = page.eval_on_selector('img[src*="captcha"]', 'el => el.src')
                            b64 = page.evaluate(f"""
                            async () => {{
                                const r = await fetch({repr(src)});
                                const b = await r.blob();
                                return new Promise(res => {{
                                    const fr = new FileReader();
                                    fr.onloadend = () => res(fr.result.split(',')[1]);
                                    fr.readAsDataURL(b);
                                }});
                            }}
                            """)
                            captcha_bytes = _b64.b64decode(b64)
                        except Exception:
                            pass

                    if not captcha_bytes:
                        browser.close()
                        continue

                    captcha_resp = _ocr_captcha(captcha_bytes)
                    if not captcha_resp:
                        browser.close()
                        continue

                    # Preencher resposta do captcha
                    for sel in ['input[name*="captcha"]', 'input[id*="captcha"]',
                                'input[placeholder*="aptcha"]', 'input[placeholder*="ódigo"]']:
                        try:
                            fld = page.locator(sel).first
                            if fld.is_visible(timeout=2000):
                                fld.fill(captcha_resp)
                                break
                        except Exception:
                            continue

                    # Submeter
                    for sel in ['button:has-text("Emitir")', 'button:has-text("Gerar")',
                                'input[value="Emitir"]', 'button[type="submit"]']:
                        try:
                            btn = page.locator(sel).first
                            if btn.is_visible(timeout=3000):
                                btn.click()
                                break
                        except Exception:
                            continue

                    page.wait_for_timeout(6000)
                    html = page.content()
                    html_lower = html.lower()
                    browser.close()

                except PWTimeout:
                    browser.close()
                    continue

            # Captcha errado → tentar novamente
            if any(k in html_lower for k in ["código inválido", "codigo invalido",
                                              "captcha inválido", "resposta incorreta",
                                              "tente novamente"]):
                continue

            if _neg_keywords(html_lower):
                return ResultadoCertidao(**base, status=Status.REGULAR,
                                         mensagem="Certidão Negativa Municipal de Fortaleza emitida com sucesso.")
            if _pos_keywords(html_lower):
                return ResultadoCertidao(**base, status=Status.IRREGULAR,
                                         mensagem=f"Existem débitos municipais em Fortaleza para o CNPJ {cnpj_fmt}.")

            return None

        except Exception:
            continue

    return None  # Todas as tentativas falharam


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto.upper().strip()


# ─── Função pública ───────────────────────────────────────────────────────────

def consultar(cnpj14: str, municipio: str, estado: str) -> ResultadoCertidao:
    chave = f"{_normalizar(municipio)}_{estado.upper().strip()}"
    info = MUNICIPIOS.get(chave)
    cnpj_fmt = f"{cnpj14[:2]}.{cnpj14[2:5]}.{cnpj14[5:8]}/{cnpj14[8:12]}-{cnpj14[12:]}"

    if info:
        automacao = info.get("automacao")

        # Tentar automação
        resultado = None
        if automacao == "fortaleza":
            resultado = _consultar_fortaleza(cnpj14, info)
        elif automacao == "caucaia":
            resultado = _consultar_caucaia(cnpj14, info)
        elif automacao == "speedgov":
            resultado = _consultar_speedgov(cnpj14, info)

        if resultado is not None:
            return resultado

        # Fallback: link
        return ResultadoCertidao(
            tipo="municipal",
            nome=f"Certidão Negativa Municipal — {info['nome']}",
            orgao=info["orgao"],
            status=Status.NAO_SUPORTADO,
            mensagem=(
                f"Acesse o portal da {info['orgao']} e informe o CNPJ {cnpj_fmt} "
                "para emitir a certidão municipal."
            ),
            url=info["url"],
        )

    return ResultadoCertidao(
        tipo="municipal",
        nome=f"Certidão Negativa Municipal — {municipio}",
        orgao="Prefeitura Municipal",
        status=Status.NAO_SUPORTADO,
        mensagem=(
            f"Município não mapeado. Acesse o site da Prefeitura de {municipio} "
            f"e solicite a Certidão Negativa de Tributos Municipais para o CNPJ {cnpj_fmt}."
        ),
        url=f"https://www.google.com/search?q=certidao+negativa+{_normalizar(municipio).replace(' ', '+')}+{estado}+prefeitura",
    )


MUNICIPIOS_LISTA = sorted({v["nome"] for v in MUNICIPIOS.values()})
