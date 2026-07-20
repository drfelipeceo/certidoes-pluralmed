"""
Certificado de Regularidade do FGTS (CRF) — Caixa Econômica Federal
Portal JSF sem captcha. Playwright com stealth para evitar detecção de bot.
"""
import re
import sys
from .base import ResultadoCertidao, Status, HEADERS_NAVEGADOR

URL_PORTAL = "https://consulta-crf.caixa.gov.br/consultacrf/pages/consultaEmpregador.jsf"

# macOS: Chrome real (bypassa ShieldSquare via TLS fingerprint)
# Linux/cloud: Chrome instalado via apt no Dockerfile (mesmo efeito)
_CHROME_PATH_MAC = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
_CHROME_PATH_LINUX = "/usr/bin/google-chrome-stable"

_STEALTH = """
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
    Object.defineProperty(navigator, 'languages', {get: () => ['pt-BR','pt','en-US','en']});
    window.chrome = {runtime: {}};
"""


def consultar(cnpj14: str) -> ResultadoCertidao:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    base = dict(
        tipo="fgts",
        nome="Certificado de Regularidade do FGTS (CRF)",
        orgao="Caixa Econômica Federal",
        url=URL_PORTAL,
    )
    cnpj_fmt = f"{cnpj14[:2]}.{cnpj14[2:5]}.{cnpj14[5:8]}/{cnpj14[8:12]}-{cnpj14[12:]}"

    try:
        import os
        if sys.platform == "darwin":
            chrome_path = _CHROME_PATH_MAC if os.path.exists(_CHROME_PATH_MAC) else None
        else:
            chrome_path = _CHROME_PATH_LINUX if os.path.exists(_CHROME_PATH_LINUX) else None

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                executable_path=chrome_path,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            )
            ctx = browser.new_context(
                user_agent=HEADERS_NAVEGADOR["User-Agent"],
                viewport={"width": 1280, "height": 900},
            )
            page = ctx.new_page()
            page.add_init_script(_STEALTH)

            try:
                page.goto(URL_PORTAL, timeout=30000, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)

                # Detectar bloqueio anti-bot
                if any(k in page.url for k in ["perfdrive.com", "validate", "shieldsquare"]):
                    browser.close()
                    return ResultadoCertidao(
                        **base, status=Status.NAO_SUPORTADO,
                        mensagem=f"Portal bloqueou automação. Acesse o link e informe o CNPJ {cnpj_fmt}.",
                    )

                # Preencher CNPJ — JSF usa input[name="mainForm:txtInscricao1"]
                campo = page.locator('input[name="mainForm:txtInscricao1"]')
                campo.wait_for(state="visible", timeout=10000)
                campo.fill(cnpj14)

                # Clicar Consultar — JSF usa input[type="button"] não <button>
                page.locator('input[name="mainForm:btnConsultar"]').click()
                page.wait_for_timeout(6000)

                # Verificar bloqueio pós-submit
                if any(k in page.url for k in ["perfdrive.com", "validate", "shieldsquare"]):
                    browser.close()
                    return ResultadoCertidao(
                        **base, status=Status.NAO_SUPORTADO,
                        mensagem=f"Portal bloqueou automação. Acesse o link e informe o CNPJ {cnpj_fmt}.",
                    )

                html = page.content()
                html_lower = html.lower()

                # Se está na página de resultado, navegar ao CRF para pegar validade e número
                if "regular no fgts" in html_lower or "situação de regularidade" in html_lower:
                    validade, numero = None, None
                    try:
                        crf = page.locator('a:has-text("Certificado de Regularidade do FGTS - CRF")')
                        if crf.is_visible(timeout=2000):
                            crf.click()
                            page.wait_for_timeout(4000)
                            html2 = page.content().lower()
                            # Datas separadas por " a " (ignora markup HTML entre "validade" e as datas)
                            m = re.search(r'(\d{2}/\d{2}/\d{4})\s+a\s+(\d{2}/\d{2}/\d{4})', html2)
                            if m:
                                validade = f"{m.group(1)} a {m.group(2)}"
                            # Número: sequência longa de dígitos (≥15 chars)
                            m2 = re.search(r'(\d{15,})', html2)
                            if m2:
                                numero = m2.group(1)
                    except Exception:
                        pass

                    browser.close()
                    return ResultadoCertidao(
                        **base, status=Status.REGULAR,
                        validade=validade, numero=numero,
                        mensagem=(
                            f"Empresa REGULAR no FGTS. "
                            f"CRF n° {numero or 'N/A'} | Validade: {validade or 'N/A'}"
                        ),
                    )

                if any(k in html_lower for k in ["irregular", "não regular", "inadimplente"]):
                    browser.close()
                    return ResultadoCertidao(
                        **base, status=Status.IRREGULAR,
                        mensagem=f"Irregularidade no FGTS para o CNPJ {cnpj_fmt}.",
                    )

                browser.close()
                return ResultadoCertidao(
                    **base, status=Status.ERRO,
                    mensagem=f"Não foi possível determinar a situação FGTS para {cnpj_fmt}.",
                )

            except PWTimeout:
                browser.close()
                return ResultadoCertidao(
                    **base, status=Status.NAO_SUPORTADO,
                    mensagem=f"Timeout ao consultar FGTS. Acesse o link e informe o CNPJ {cnpj_fmt}.",
                )

    except Exception as exc:
        return ResultadoCertidao(
            **base, status=Status.ERRO,
            mensagem=f"Erro ao consultar FGTS ({type(exc).__name__}). Acesse o link para consulta manual.",
        )
