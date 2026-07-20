"""
Certidão de Débitos Relativos a Créditos Tributários Federais e à Dívida Ativa da União
Receita Federal / PGFN.

Fluxo automatizado via HTTP puro:
- O token hCaptcha é enviado no header "X-Captcha-Token" (descoberto no bundle Angular).
- Se TWOCAPTCHA_KEY estiver configurado: resolve hCaptcha via 2captcha (~$0,003/consulta).
- Sem chave: abre Chrome headed (apenas no Mac/desktop com display).
- Sem display e sem chave: retorna link para acesso manual.
"""
import re
import os
import sys
import time
import requests as _requests

from .base import ResultadoCertidao, Status, HEADERS_NAVEGADOR

URL_PORTAL    = "https://servicos.receitafederal.gov.br/servico/certidoes/#/home/cnpj"
API_VERIFICAR = "https://servicos.receitafederal.gov.br/servico/certidoes/api/Emissao/verificar"
HCAPTCHA_SITEKEY = "4a65992d-58fc-4812-8b87-789f7e7c4c4b"

_CHROME_PATH  = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
_TIMEOUT_CAPTCHA = 180  # segundos para o usuário resolver o captcha no Chrome headed

_STEALTH = """
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
    Object.defineProperty(navigator, 'languages', {get: () => ['pt-BR','pt','en-US','en']});
    window.chrome = {runtime: {}};
"""

_BANNER = """
    window.addEventListener('DOMContentLoaded', function() {
        var b = document.createElement('div');
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


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _tem_display() -> bool:
    if sys.platform == "darwin":
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def _solve_hcaptcha_2captcha(api_key: str) -> str:
    """Resolve hCaptcha via 2captcha. Retorna o token pronto para uso."""
    # 1. Submeter tarefa
    r = _requests.post(
        "https://2captcha.com/in.php",
        data={
            "key": api_key,
            "method": "hcaptcha",
            "sitekey": HCAPTCHA_SITEKEY,
            "pageurl": URL_PORTAL,
            "json": 1,
        },
        timeout=30,
    )
    r.raise_for_status()
    resp = r.json()
    if resp.get("status") != 1:
        raise RuntimeError(f"2captcha erro ao submeter: {resp.get('request')}")

    task_id = resp["request"]

    # 2. Aguardar resultado (até ~120s)
    for _ in range(40):
        time.sleep(3)
        r = _requests.get(
            "https://2captcha.com/res.php",
            params={"key": api_key, "action": "get", "id": task_id, "json": 1},
            timeout=30,
        )
        r.raise_for_status()
        resp = r.json()
        if resp.get("status") == 1:
            return resp["request"]
        if resp.get("request") not in ("CAPCHA_NOT_READY", "CAPTCHA_NOT_READY"):
            raise RuntimeError(f"2captcha erro: {resp.get('request')}")

    raise RuntimeError("Timeout aguardando 2captcha (>120s)")


def _chamar_api_rf(cnpj14: str, token: str) -> dict:
    """Chama a API da RF com o token hCaptcha no header X-Captcha-Token."""
    headers = {
        "User-Agent": HEADERS_NAVEGADOR["User-Agent"],
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "X-Captcha-Token": token,
        "Origin": "https://servicos.receitafederal.gov.br",
        "Referer": URL_PORTAL,
    }
    payload = {
        "ni": cnpj14,
        "tipoContribuinte": "PJ",
        "tipoContribuinteEnum": "CNPJ",
    }
    r = _requests.post(API_VERIFICAR, headers=headers, json=payload, timeout=30)
    return {"status": r.status_code, "body": r.text}


# ─── Fluxo headed (fallback sem 2captcha, apenas com display) ─────────────────

def _consultar_headed(cnpj14: str, cnpj_fmt: str, base: dict) -> ResultadoCertidao:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

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

            api_resp = {"body": None, "status": None}

            def on_response(resp):
                if "Emissao/verificar" in resp.url:
                    try:
                        api_resp["status"] = resp.status
                        api_resp["body"] = resp.text()
                    except Exception:
                        pass

            page.on("response", on_response)

            page.goto(URL_PORTAL, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)

            try:
                btn = page.locator('button:has-text("Aceitar")')
                if btn.is_visible(timeout=2000):
                    btn.click()
                    page.wait_for_timeout(500)
            except Exception:
                pass

            campo = page.locator('input[placeholder="Informe o CNPJ"]')
            campo.wait_for(state="visible", timeout=10000)
            campo.fill(cnpj_fmt)
            page.wait_for_timeout(500)
            page.locator('button[type="submit"]').click()

            for _ in range(_TIMEOUT_CAPTCHA):
                page.wait_for_timeout(1000)
                if api_resp["status"] == 200:
                    break
                html_lower = page.content().lower()
                if any(k in html_lower for k in ["certid", "negativa", "positiva", "efeitos de negativa"]):
                    break

            page.wait_for_timeout(3000)

            try:
                html_lower = page.content().lower()
                if "válida encontrada" in html_lower or "valida encontrada" in html_lower:
                    page.locator('button:has-text("Consultar Certidão")').first.click()
                    page.wait_for_timeout(4000)
            except Exception:
                pass

            html_final = page.content().lower()
            browser.close()

    except PWTimeout:
        return ResultadoCertidao(
            **base, status=Status.NAO_SUPORTADO,
            mensagem=f"Timeout ao carregar o portal RF. Acesse o link → CNPJ {cnpj_fmt}.",
        )

    return ResultadoCertidao(
        **base,
        **dict(zip(("status", "mensagem", "validade", "numero"), _parse_resultado(html_final, cnpj_fmt))),
    )


# ─── Entrada principal ────────────────────────────────────────────────────────

def consultar(cnpj14: str) -> ResultadoCertidao:
    base = dict(
        tipo="federal",
        nome="Certidão de Débitos Federais (RF/PGFN)",
        orgao="Receita Federal / PGFN",
        url=URL_PORTAL,
    )
    cnpj_fmt = f"{cnpj14[:2]}.{cnpj14[2:5]}.{cnpj14[5:8]}/{cnpj14[8:12]}-{cnpj14[12:]}"

    # ── Caminho 1: 2captcha configurado → 100% automático (cloud ou local) ──
    api_key = os.environ.get("TWOCAPTCHA_KEY", "").strip()
    if api_key:
        try:
            token = _solve_hcaptcha_2captcha(api_key)
            resp = _chamar_api_rf(cnpj14, token)
            if resp["status"] == 200:
                status, mensagem, validade, numero = _parse_resultado(
                    resp["body"].lower(), cnpj_fmt
                )
                return ResultadoCertidao(
                    **base, status=status, mensagem=mensagem,
                    validade=validade, numero=numero,
                )
        except Exception as exc:
            # 2captcha falhou → tentar próximo caminho
            _err = str(exc)
        else:
            _err = f"API RF retornou {resp['status']}: {resp['body'][:80]}"

    # ── Caminho 2: sem 2captcha mas há display → Chrome headed (só local/Mac) ──
    if _tem_display():
        return _consultar_headed(cnpj14, cnpj_fmt, base)

    # ── Caminho 3: cloud sem 2captcha → link manual ──
    return ResultadoCertidao(
        **base,
        status=Status.NAO_SUPORTADO,
        mensagem=(
            f"Configure TWOCAPTCHA_KEY para automação completa. "
            f"Acesse o portal → CNPJ {cnpj_fmt} → Emitir Certidão."
        ),
    )


# ─── Parse do resultado ───────────────────────────────────────────────────────

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
        return (Status.REGULAR,
                f"Certidão Positiva com Efeitos de Negativa. Validade: {validade or 'N/A'}.",
                validade, numero)
    if "certid" in html and "negativa" in html and "positiva" not in html:
        return (Status.REGULAR,
                f"Certidão Negativa Federal — sem débitos. Validade: {validade or 'N/A'}.",
                validade, numero)
    if "certid" in html and "positiva" in html and "efeitos" not in html:
        return (Status.IRREGULAR,
                f"Certidão Positiva — existem débitos federais. CNPJ: {cnpj_fmt}.",
                validade, numero)

    return (Status.NAO_SUPORTADO,
            f"Captcha não resolvido ou timeout. Acesse o portal → CNPJ {cnpj_fmt}.",
            None, None)
