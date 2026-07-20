from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Status(Enum):
    REGULAR = "regular"
    IRREGULAR = "irregular"
    ERRO = "erro"
    NAO_SUPORTADO = "nao_suportado"


STATUS_LABELS = {
    Status.REGULAR: "REGULAR",
    Status.IRREGULAR: "IRREGULAR",
    Status.ERRO: "Verificar Manualmente",
    Status.NAO_SUPORTADO: "Acesso Manual Necessário",
}

STATUS_EMOJI = {
    Status.REGULAR: "✅",
    Status.IRREGULAR: "❌",
    Status.ERRO: "⚠️",
    Status.NAO_SUPORTADO: "🔗",
}


@dataclass
class ResultadoCertidao:
    tipo: str
    nome: str
    orgao: str
    status: Status
    mensagem: str
    url: Optional[str] = None
    pdf_bytes: Optional[bytes] = None
    validade: Optional[str] = None
    numero: Optional[str] = None
    data_consulta: datetime = field(default_factory=datetime.now)

    @property
    def label(self) -> str:
        return STATUS_LABELS.get(self.status, "—")

    @property
    def emoji(self) -> str:
        return STATUS_EMOJI.get(self.status, "❓")

    @property
    def is_regular(self) -> bool:
        return self.status == Status.REGULAR

    @property
    def tem_pdf(self) -> bool:
        return self.pdf_bytes is not None and len(self.pdf_bytes) > 0


HEADERS_NAVEGADOR = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}
