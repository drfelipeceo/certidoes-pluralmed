"""
Certidão Negativa de Débitos Trabalhistas (CNDT) — TST
Usa requests (HTTP direto) com OCR ddddocr para resolver o captcha de imagem.
Tenta até MAX_TENTATIVAS vezes antes de desistir.
"""
import re
import io
import warnings
import requests
from urllib3.exceptions import InsecureRequestWarning

_ocr = None
_ocr_beta = None
_OCR_OK = None


def _get_ocr():
    global _ocr, _ocr_beta, _OCR_OK
    if _OCR_OK is None:
        try:
            import ddddocr
            _ocr = ddddocr.DdddOcr(show_ad=False)
            _ocr_beta = ddddocr.DdddOcr(beta=True, show_ad=False)
            _OCR_OK = True
        except ImportError:
            _OCR_OK = False
    return _OCR_OK

from .base import ResultadoCertidao, Status, HEADERS_NAVEGADOR

warnings.filterwarnings("ignore", category=InsecureRequestWarning)

URL_BASE = "https://cndt-certidao.tst.jus.br"
URL_PORTAL = "https://www.tst.jus.br/certidao"
MAX_TENTATIVAS = 8


def _resolver_captcha(imagem_bytes: bytes) -> str:
    """OCR na imagem do captcha. Filtra apenas ASCII alfanumérico."""
    if not _get_ocr():
        return ""
    from PIL import Image, ImageFilter, ImageEnhance
    # Tenta modo padrão e beta, usa o que der mais caracteres
    raw1 = "".join(c for c in _ocr.classification(imagem_bytes) if c.isascii() and c.isalnum())
    raw2 = "".join(c for c in _ocr_beta.classification(imagem_bytes) if c.isascii() and c.isalnum())
    # Pré-processamento: binarização threshold=180
    img = Image.open(io.BytesIO(imagem_bytes)).convert("L")
    binary = img.point(lambda x: 0 if x < 180 else 255, "L")
    buf = io.BytesIO()
    binary.save(buf, format="PNG")
    raw3 = "".join(c for c in _ocr.classification(buf.getvalue()) if c.isascii() and c.isalnum())
    # Escolhe o resultado com mais caracteres (geralmente mais completo)
    candidatos = [r for r in [raw1, raw2, raw3] if r]
    if not candidatos:
        return ""
    return max(candidatos, key=len)


def _iniciar_sessao() -> tuple[requests.Session, str, str]:
    """Cria sessão, navega até o formulário e retorna (session, view_state, form_id)."""
    session = requests.Session()
    session.headers.update(HEADERS_NAVEGADOR)

    r1 = session.get(f"{URL_BASE}/inicio.faces", verify=False, timeout=20)
    vs1 = re.search(r'name="javax\.faces\.ViewState"[^>]*value="([^"]+)"', r1.text)
    form_id = re.search(r'<form[^>]+id="([^"]+)"', r1.text)
    if not vs1 or not form_id:
        raise ValueError("Não encontrou ViewState ou form_id na página inicial")
    vs1 = vs1.group(1)
    form_id = form_id.group(1)

    r2 = session.post(
        f"{URL_BASE}/inicio.faces",
        data={
            form_id: form_id,
            f"{form_id}:j_id_jsp_992698495_3": "Emitir Certidão",
            "javax.faces.ViewState": vs1,
        },
        headers={
            "Referer": f"{URL_BASE}/inicio.faces",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        verify=False,
        timeout=25,
    )
    vs2 = re.search(r'name="javax\.faces\.ViewState"[^>]*value="([^"]+)"', r2.text)
    if not vs2:
        raise ValueError("Não encontrou ViewState no formulário de CNPJ")
    vs2 = vs2.group(1)

    pfd = re.search(r'name="gerarCertidaoForm:podeFazerDownload"[^>]*value="([^"]+)"', r2.text)
    pfd_val = pfd.group(1) if pfd else "true"

    return session, vs2, pfd_val


def _tentativa(session: requests.Session, cnpj14: str, vs: str, pfd_val: str) -> dict | None:
    """
    Pega captcha, OCRiza, submete formulário.
    Retorna {'status': ..., 'pdf': bytes|None} ou None se captcha inválido.
    """
    # Pega captcha via API
    r_api = session.get(
        f"{URL_BASE}/api",
        headers={"Referer": f"{URL_BASE}/gerarCertidao.faces"},
        verify=False,
        timeout=10,
    )
    data = r_api.json()
    token = data.get("tokenDesafio", "")
    signed = data.get("imagem", [])
    img_bytes = bytes([b & 0xFF for b in signed])

    captcha = _resolver_captcha(img_bytes)
    if not captcha:
        return None

    # Submete formulário
    form_data = {
        "gerarCertidaoForm": "gerarCertidaoForm",
        "gerarCertidaoForm:podeFazerDownload": pfd_val,
        "gerarCertidaoForm:cpfCnpj": cnpj14,
        "resposta": captcha,
        "tokenDesafio": token,
        "gerarCertidaoForm:btnEmitirCertidao": "Emitir Certidão",
        "javax.faces.ViewState": vs,
    }
    r3 = session.post(
        f"{URL_BASE}/gerarCertidao.faces",
        data=form_data,
        headers={
            "Referer": f"{URL_BASE}/gerarCertidao.faces",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        verify=False,
        timeout=30,
    )

    ct = r3.headers.get("content-type", "")
    if "pdf" in ct.lower():
        return {"status": "pdf", "pdf": r3.content}

    html = r3.text.lower()

    # Captcha errado → tenta de novo
    if any(k in html for k in ["código de validação inválido", "resposta incorreta", "captcha inválido"]):
        return None

    # Analisa resultado
    if any(k in html for k in ["irregular", "devedor", "executado", "inadimplente"]):
        return {"status": "irregular", "pdf": None}

    if any(k in html for k in ["negativa", "inexistência", "não consta"]):
        return {"status": "regular", "pdf": None}

    # Conteúdo ambíguo (pode ter avançado mas não identificamos)
    return {"status": "ambiguo", "pdf": None, "html": r3.text[:2000]}


def consultar(cnpj14: str) -> ResultadoCertidao:
    base = dict(
        tipo="trabalhista",
        nome="Certidão Negativa de Débitos Trabalhistas",
        orgao="TST",
        url=URL_PORTAL,
    )

    if not _get_ocr():
        return ResultadoCertidao(
            **base,
            status=Status.ERRO,
            mensagem="Biblioteca ddddocr não instalada. Execute: pip install ddddocr",
        )

    try:
        session, vs, pfd_val = _iniciar_sessao()
    except Exception as e:
        return ResultadoCertidao(
            **base,
            status=Status.ERRO,
            mensagem=f"Erro ao acessar o portal do TST: {type(e).__name__}. Acesse {URL_PORTAL} manualmente.",
        )

    for tentativa in range(MAX_TENTATIVAS):
        try:
            resultado = _tentativa(session, cnpj14, vs, pfd_val)
        except Exception:
            resultado = None

        if resultado is None:
            # Captcha errado, reinicia sessão a cada 3 tentativas
            if tentativa > 0 and tentativa % 3 == 0:
                try:
                    session, vs, pfd_val = _iniciar_sessao()
                except Exception:
                    break
            continue

        if resultado["status"] == "pdf":
            return ResultadoCertidao(
                **base,
                status=Status.REGULAR,
                mensagem="Certidão Negativa emitida com sucesso.",
                pdf_bytes=resultado["pdf"],
            )

        if resultado["status"] == "regular":
            return ResultadoCertidao(
                **base,
                status=Status.REGULAR,
                mensagem="Nenhum débito trabalhista encontrado.",
            )

        if resultado["status"] == "irregular":
            return ResultadoCertidao(
                **base,
                status=Status.IRREGULAR,
                mensagem="Débitos trabalhistas encontrados. Acesse o portal do TST para detalhes.",
            )

        # Ambíguo: para tentativas extras, continua
        if resultado["status"] == "ambiguo":
            html = resultado.get("html", "").lower()
            if "negativa" in html or "regular" in html:
                return ResultadoCertidao(
                    **base,
                    status=Status.REGULAR,
                    mensagem="Situação trabalhista regular.",
                )
            break  # Não conseguiu identificar — encerra

    return ResultadoCertidao(
        **base,
        status=Status.ERRO,
        mensagem=(
            f"Não foi possível resolver o captcha após {MAX_TENTATIVAS} tentativas. "
            f"Acesse {URL_PORTAL} manualmente para verificar."
        ),
    )
