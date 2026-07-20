"""
Certidão de Débitos Relativos a Créditos Tributários Federais e à Dívida Ativa da União
Receita Federal / PGFN.

Portal protegido por hCaptcha. Fluxo semi-automático:
1. Chrome visível abre com CNPJ pré-preenchido.
2. App clica em "Emitir Certidão" → hCaptcha aparece.
3. Usuário resolve o captcha na janela do Chrome.
4. Playwright detecta o resultado e fecha o Chrome automaticamente.
"""
import re
import os
from .base import ResultadoCertidao, Status, HEADERS_NAVEGADOR

URL_PORTAL = "https://servicos.receitafederal.gov.br/servico/certidoes/#/home/cnpj"
_CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

_STEALTH = """
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
    Object.defineProperty(navigator, 'languages', {get: () => ['pt-BR','pt','en-US','en']});
    window.chrome = {runtime: {}};
"""

# Banner azul sobreposto à página para orientar o usuário
_BANNER = """
    window.addEventListener('DOMContentLoaded', function() {
        var b = document.createElement('div');
        b.id = 'claude-rf-banner';
        b.style.cssText = [
            'position:fixed','top:0','left:0','right:0','z-index:2147483647',
            'background:#071D41','color:#fff','text-align:center',
            'padding:14px 20px','font-size:15px','font-family:Arial,sans-serif',
            'box-shadow:0 2px 8px rgba(0,0,0,.4)'
        ].join(';');
        b.innerHTML = '🔐 <b>Certidão Federal (RF/PGFN)</b> — Resolva o captcha e clique em <b>Emitir Certidão</b>. A janela fechará automaticamente.';
        document.body.prepend(b);
    });
"""

_TIMEOUT_CAPTCHA = 180  # segundos que o usuário tem para resolver o captcha

def _tem_display() -> bool:
    """Retorna True se há um display disponível para abrir Chrome headed."""
    import sys, os
    if sys.platform == "darwin":
        return True  # macOS sempre tem display
    # Linux: verifica DISPLAY ou WAYLAND_DISPLAY
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def consultar(cnpj14: str) -> ResultadoCertidao:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    base = dict(
        tipo="federal",
        nome="Certidão de Débitos Federais (RF/PGFN)",
        orgao="Receita Federal / PGFN",
        url=URL_PORTAL,
    )
    cnpj_fmt = f"{cnpj14[:2]}.{cnpj14[2:5]}.{cnpj14[5:8]}/{cnpj14[8:12]}-{cnpj14[12:]}"

    # Em servidor headless (Railway/cloud): sem display → link direto
    if not _tem_display():
        return ResultadoCertidao(
            **base,
            status=Status.NAO_SUPORTADO,
            mensagem=(
                f"Certidão Federal exige captcha visual. "
                f"Acesse o portal → informe o CNPJ {cnpj_fmt} → clique Emitir Certidão."
            ),
        )

    chrome_path = _CHROME_PATH if os.path.exists(_CHROME_PATH) else None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False,
                executable_path=chrome_path,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
            ctx = browser.new_context(
                user_agent=HEADERS_NAVEGADOR["User-Agent"],
                viewport={"width": 1280, "height": 900},
            )
            page = ctx.new_page()
            page.add_init_script(_STEALTH)
            page.add_init_script(_BANNER)

            # Capturar resposta da API após o captcha ser resolvido
            api_resp = {"body": None, "status": None}

            def on_response(resp):
                if "Emissao/verificar" in resp.url:
                    try:
                        api_resp["status"] = resp.status
                        api_resp["body"] = resp.text()
                    except Exception:
                        pass

            page.on("response", on_response)

            try:
                page.goto(URL_PORTAL, timeout=30000, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)

                # Aceitar cookies se necessário
                try:
                    btn = page.locator('button:has-text("Aceitar")')
                    if btn.is_visible(timeout=2000):
                        btn.click()
                        page.wait_for_timeout(500)
                except Exception:
                    pass

                # Preencher CNPJ
                campo = page.locator('input[placeholder="Informe o CNPJ"]')
                campo.wait_for(state="visible", timeout=10000)
                campo.fill(cnpj_fmt)
                page.wait_for_timeout(500)

                # Clicar em Emitir Certidão → abre o hCaptcha para o usuário resolver
                page.locator('button[type="submit"]').click()

                # Aguardar o usuário resolver o captcha (até _TIMEOUT_CAPTCHA segundos)
                for _ in range(_TIMEOUT_CAPTCHA):
                    page.wait_for_timeout(1000)

                    # API retornou 200 → captcha resolvido e certidão emitida
                    if api_resp["status"] == 200:
                        break

                    # Verificar também por conteúdo na página (modal de certidão válida)
                    html_lower = page.content().lower()
                    if any(k in html_lower for k in [
                        "certid", "negativa", "positiva", "efeitos de negativa",
                        "válida encontrada", "valida encontrada",
                    ]):
                        break

                # Aguardar Angular renderizar o resultado completo
                page.wait_for_timeout(3000)

                # Se há modal "Certidão Válida Encontrada", clicar em Consultar Certidão
                try:
                    html_lower = page.content().lower()
                    if "válida encontrada" in html_lower or "valida encontrada" in html_lower:
                        page.locator('button:has-text("Consultar Certidão")').first.click()
                        page.wait_for_timeout(4000)
                except Exception:
                    pass

                html_final = page.content().lower()
                browser.close()

                status, mensagem, validade, numero = _parse_resultado(html_final, cnpj_fmt)
                return ResultadoCertidao(
                    **base, status=status, mensagem=mensagem,
                    validade=validade, numero=numero,
                )

            except PWTimeout:
                browser.close()
                return ResultadoCertidao(
                    **base, status=Status.NAO_SUPORTADO,
                    mensagem=f"Timeout ao carregar o portal RF. Acesse o link → CNPJ {cnpj_fmt}.",
                )

    except Exception as exc:
        return ResultadoCertidao(
            **base, status=Status.NAO_SUPORTADO,
            mensagem=f"Erro ao abrir o portal RF ({type(exc).__name__}). Acesse o link → CNPJ {cnpj_fmt}.",
        )


def _parse_resultado(html: str, cnpj_fmt: str) -> tuple:
    validade = None
    m = re.search(r'datavalidade["\s:]+(\d{4}-\d{2}-\d{2})', html)
    if m:
        d = m.group(1)
        validade = f"{d[8:10]}/{d[5:7]}/{d[:4]}"
    if not validade:
        m = re.search(r'validade[^0-9]{0,30}(\d{2}/\d{2}/\d{4})', html)
        if m:
            validade = m.group(1)

    numero = None
    m2 = re.search(r'numerocontrole["\s:]+([0-9a-f.\-]{10,})', html)
    if m2:
        numero = m2.group(1).upper()

    if "efeitos de negativa" in html:
        return (
            Status.REGULAR,
            f"Certidão Positiva com Efeitos de Negativa (RF/PGFN). Validade: {validade or 'N/A'}.",
            validade, numero,
        )
    if "certid" in html and "negativa" in html and "positiva" not in html:
        return (
            Status.REGULAR,
            f"Certidão Negativa Federal — sem débitos (RF/PGFN). Validade: {validade or 'N/A'}.",
            validade, numero,
        )
    if "certid" in html and "positiva" in html and "efeitos" not in html:
        return (
            Status.IRREGULAR,
            f"Certidão Positiva (RF/PGFN) — existem débitos federais. CNPJ: {cnpj_fmt}.",
            validade, numero,
        )

    # Captcha não resolvido ou timeout → fallback para link
    return (
        Status.NAO_SUPORTADO,
        f"Captcha não resolvido ou timeout. Acesse o portal → CNPJ {cnpj_fmt} → Emitir Certidão.",
        None, None,
    )
