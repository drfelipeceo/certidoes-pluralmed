"""Singleton compartilhado do ddddocr — carregado sob demanda, liberável entre tarefas."""
import io
_ocr = None
_ocr_beta = None
_OCR_OK = None


def get_ocr():
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


def release():
    """Libera os modelos da memória e força GC — chame após trabalhista terminar."""
    global _ocr, _ocr_beta, _OCR_OK
    _ocr = None
    _ocr_beta = None
    _OCR_OK = None
    import gc
    gc.collect()


def classificar(imagem_bytes: bytes) -> str:
    """OCR na imagem: testa padrão, beta e binarizado; retorna o mais longo."""
    from PIL import Image
    if not get_ocr():
        return ""
    r1 = "".join(c for c in _ocr.classification(imagem_bytes) if c.isascii() and c.isalnum())
    r2 = "".join(c for c in _ocr_beta.classification(imagem_bytes) if c.isascii() and c.isalnum())
    img = Image.open(io.BytesIO(imagem_bytes)).convert("L")
    buf = io.BytesIO()
    img.point(lambda x: 0 if x < 180 else 255, "L").save(buf, format="PNG")
    r3 = "".join(c for c in _ocr.classification(buf.getvalue()) if c.isascii() and c.isalnum())
    opts = [r for r in [r1, r2, r3] if r]
    return max(opts, key=len) if opts else ""
