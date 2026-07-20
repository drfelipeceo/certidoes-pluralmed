"""
Sistema de Consulta de Certidões Negativas
PluralMed — uso interno
"""

import base64
import concurrent.futures
import sys
import os
import time

import streamlit as st

sys.path.insert(0, os.path.dirname(__file__))

from utils.cnpj import limpar_cnpj, formatar_cnpj, validar_cnpj
from certidoes import trabalhista, federal, fgts, estadual, municipal
from certidoes.base import Status
from certidoes.estadual import ESTADOS
from certidoes.municipal import MUNICIPIOS_LISTA

# ─── Configuração da página ───────────────────────────────────────────────────
st.set_page_config(
    page_title="Certidões Negativas",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── CSS ──────────────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
    #MainMenu, footer, header {visibility: hidden;}
    .block-container {padding-top: 1.5rem; padding-bottom: 2rem;}

    .cabecalho {
        background: linear-gradient(135deg, #0A5858 0%, #0D7272 100%);
        border-radius: 12px;
        padding: 1.3rem 2rem;
        color: #fff;
        margin-bottom: 1.8rem;
    }

    /* Cards de certidão */
    .card {
        border-radius: 10px;
        border: 1px solid #dee2e6;
        padding: 1.1rem 1.3rem;
        margin-bottom: 0.9rem;
        background: #fff;
    }
    .card-regular  {border-left: 5px solid #168821; background: #f5fff7;}
    .card-irregular{border-left: 5px solid #E52207; background: #fff5f5;}
    .card-erro     {border-left: 5px solid #FFCD07; background: #fffef0;}
    .card-link     {border-left: 5px solid #0D6E6E; background: #f0fafa;}

    .card-title {font-size: 1rem; font-weight: 700; color: #071D41; margin: 0;}
    .card-orgao {font-size: 0.78rem; color: #666; margin: 0.1rem 0 0.5rem;}
    .card-msg   {font-size: 0.88rem; color: #333; margin: 0.4rem 0 0;}

    .badge {
        display: inline-block;
        border-radius: 20px;
        padding: 0.2rem 0.75rem;
        font-size: 0.78rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: .04em;
    }
    .badge-regular   {background: #168821; color: #fff;}
    .badge-irregular {background: #E52207; color: #fff;}
    .badge-erro      {background: #FFCD07; color: #333;}
    .badge-link      {background: #0D6E6E; color: #fff;}

    .resumo-ok   {background:#d4edda; color:#155724; border-radius:10px;
                  padding:1rem 1.5rem; font-size:1.15rem; font-weight:700; text-align:center;}
    .resumo-nok  {background:#f8d7da; color:#721c24; border-radius:10px;
                  padding:1rem 1.5rem; font-size:1.15rem; font-weight:700; text-align:center;}
    .resumo-aviso{background:#fff3cd; color:#856404; border-radius:10px;
                  padding:1rem 1.5rem; font-size:1.15rem; font-weight:700; text-align:center;}

    hr.divisor {border: none; border-top: 1px solid #e0e0e0; margin: 1.5rem 0;}

    @media print {
        #MainMenu, footer, header, [data-testid="stToolbar"],
        [data-testid="stSidebar"], [data-testid="stForm"],
        button, .stDownloadButton { display: none !important; }
        .card { break-inside: avoid; }
        .cabecalho { background: #071D41 !important; -webkit-print-color-adjust: exact; }
    }
</style>
""",
    unsafe_allow_html=True,
)

# ─── Cabeçalho ────────────────────────────────────────────────────────────────
st.markdown(
    """
<div class="cabecalho">
  <div style="display:flex;align-items:center;gap:1.2rem;flex-wrap:wrap;">

    <!-- Ícone coração PluralMed -->
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 90 88" height="62" style="flex-shrink:0">
      <defs>
        <clipPath id="plmed-hc">
          <path d="M45,82 C45,82 2,57 2,30 C2,14 13,3 27,3 C36,3 43,8 45,17 C47,8 54,3 63,3 C77,3 88,14 88,30 C88,57 45,82 45,82Z"/>
        </clipPath>
      </defs>
      <path d="M45,82 C45,82 2,57 2,30 C2,14 13,3 27,3 C36,3 43,8 45,17 C47,8 54,3 63,3 C77,3 88,14 88,30 C88,57 45,82 45,82Z" fill="#00B5C5"/>
      <circle cx="27" cy="25" r="28" fill="#1A5CB8" clip-path="url(#plmed-hc)"/>
      <circle cx="63" cy="25" r="28" fill="#8FD45A" clip-path="url(#plmed-hc)"/>
    </svg>

    <!-- Nome e tagline -->
    <div style="line-height:1.15;">
      <div style="font-size:2rem;font-weight:800;color:#fff;letter-spacing:-0.02em;">PluralMed</div>
      <div style="font-size:0.58rem;color:rgba(255,255,255,0.72);letter-spacing:0.22em;font-weight:700;margin-top:0.1rem;">GESTÃO DE SAÚDE COM EXCELÊNCIA</div>
    </div>

    <!-- Divisor -->
    <div style="width:1px;background:rgba(255,255,255,0.25);height:46px;margin:0 0.6rem;flex-shrink:0;"></div>

    <!-- Título do sistema -->
    <div>
      <div style="font-size:1.35rem;font-weight:700;color:#fff;">📋 Certidões Negativas</div>
      <div style="font-size:0.82rem;color:rgba(255,255,255,0.82);margin-top:0.2rem;">Consulta automática · Trabalhista · Federal · FGTS · Estadual · Municipal</div>
    </div>

  </div>
</div>
""",
    unsafe_allow_html=True,
)

# ─── Formulário de entrada ────────────────────────────────────────────────────
with st.form("form_consulta"):
    c1, c2, c3 = st.columns([2, 1, 2])
    with c1:
        cnpj_input = st.text_input(
            "CNPJ da empresa",
            placeholder="00.000.000/0000-00",
            max_chars=18,
        )
    with c2:
        estado_sel = st.selectbox("Estado (UF)", options=ESTADOS, index=ESTADOS.index("CE"))
    with c3:
        municipio_input = st.text_input(
            "Município",
            placeholder="Ex: Fortaleza",
        )

    submitted = st.form_submit_button(
        "🔍  CONSULTAR CERTIDÕES",
        use_container_width=True,
        type="primary",
    )

# ─── Validação e execução ─────────────────────────────────────────────────────
if submitted:
    cnpj14 = limpar_cnpj(cnpj_input)
    cnpj_fmt = formatar_cnpj(cnpj14)

    if not cnpj_input.strip():
        st.error("Informe o CNPJ.")
        st.stop()
    if not validar_cnpj(cnpj14):
        st.error(f"CNPJ **{cnpj_input}** inválido. Verifique os dígitos.")
        st.stop()
    if not municipio_input.strip():
        st.error("Informe o município.")
        st.stop()

    st.markdown(f"**Empresa:** `{cnpj_fmt}` — {estado_sel} / {municipio_input}")
    st.markdown('<hr class="divisor">', unsafe_allow_html=True)

    # Executa as 5 consultas em paralelo
    progresso = st.progress(0, text="Consultando certidões…")
    resultados: dict = {}

    tarefas = {
        "trabalhista": lambda: trabalhista.consultar(cnpj14),
        "federal":     lambda: federal.consultar(cnpj14),
        "fgts":        lambda: fgts.consultar(cnpj14),
        "estadual":    lambda: estadual.consultar(cnpj14, estado_sel),
        "municipal":   lambda: municipal.consultar(cnpj14, municipio_input, estado_sel),
    }

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    futures = {k: pool.submit(fn) for k, fn in tarefas.items()}
    total = len(futures)
    done = set()
    deadline = time.time() + 180  # timeout global de 3 minutos (sequencial)

    while len(done) < total:
        for k, fut in futures.items():
            if k not in done and fut.done():
                try:
                    resultados[k] = fut.result()
                except Exception as _e:
                    from certidoes.base import ResultadoCertidao as _R
                    resultados[k] = _R(
                        tipo=k, nome=k.capitalize(), orgao="", url=None,
                        status=Status.ERRO,
                        mensagem=f"Erro inesperado: {type(_e).__name__}. Tente novamente.",
                    )
                done.add(k)
                if k == "trabalhista":
                    from certidoes.ocr import release as _rel
                    _rel()
                import gc
                gc.collect()
                progresso.progress(len(done) / total, text=f"Consultando… ({len(done)}/{total})")
        if len(done) < total:
            if time.time() > deadline:
                for k in tarefas:
                    if k not in done:
                        from certidoes.base import ResultadoCertidao as _R
                        resultados[k] = _R(
                            tipo=k, nome=k.capitalize(), orgao="",
                            url=None, status=Status.ERRO,
                            mensagem="Timeout: consulta demorou demais. Tente novamente.",
                        )
                        done.add(k)
                break
            time.sleep(0.5)

    pool.shutdown(wait=False, cancel_futures=True)  # não bloqueia em threads travadas

    progresso.empty()

    # ─── Resumo ──────────────────────────────────────────────────────────────
    from certidoes.base import Status as _S
    irregulares  = [r for r in resultados.values() if r.status == _S.IRREGULAR]
    regulares    = [r for r in resultados.values() if r.status == _S.REGULAR]
    erros        = [r for r in resultados.values() if r.status == _S.ERRO]
    manuais      = [r for r in resultados.values() if r.status in (_S.NAO_SUPORTADO,)]

    if irregulares:
        nomes = ", ".join(r.nome.split("(")[0].strip() for r in irregulares)
        st.markdown(
            f'<div class="resumo-nok">❌ {len(irregulares)} certidão(ões) IRREGULAR(ES): {nomes}</div>',
            unsafe_allow_html=True,
        )
    elif not erros and not manuais:
        # Todas as 5 verificadas e regulares
        st.markdown(
            '<div class="resumo-ok">✅ Todas as 5 certidões verificadas e regulares — empresa em dia!</div>',
            unsafe_allow_html=True,
        )
    elif regulares and not irregulares and not erros:
        # Algumas verificadas (regulares) e outras precisam de verificação manual
        nomes_ok = " · ".join(r.tipo.capitalize() for r in regulares)
        st.markdown(
            f'<div class="resumo-aviso">⚠️ {len(regulares)} verificada(s) automaticamente ({nomes_ok}). '
            f"{len(manuais) + len(erros)} certidão(ões) precisam de verificação manual (links abaixo).</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="resumo-aviso">⚠️ Verifique cada certidão individualmente (veja os cards abaixo).</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<hr class="divisor">', unsafe_allow_html=True)

    # ─── Cards individuais ────────────────────────────────────────────────────
    ORDEM = ["trabalhista", "federal", "fgts", "estadual", "municipal"]

    pdfs_disponiveis: list[tuple[str, bytes]] = []

    for chave in ORDEM:
        res = resultados[chave]

        if res.status == Status.REGULAR:
            cls_card, cls_badge, badge_txt = "card-regular", "badge-regular", "Regular"
        elif res.status == Status.IRREGULAR:
            cls_card, cls_badge, badge_txt = "card-irregular", "badge-irregular", "Irregular"
        elif res.status == Status.NAO_SUPORTADO:
            cls_card, cls_badge, badge_txt = "card-link", "badge-link", "Acesso Manual"
        else:
            cls_card, cls_badge, badge_txt = "card-erro", "badge-erro", "Verificar"

        st.markdown(
            f"""
<div class="card {cls_card}">
  <div style="display:flex; justify-content:space-between; align-items:flex-start;">
    <div>
      <p class="card-title">{res.emoji} {res.nome}</p>
      <p class="card-orgao">{res.orgao}</p>
    </div>
    <span class="badge {cls_badge}">{badge_txt}</span>
  </div>
  <p class="card-msg">{res.mensagem}</p>
  {f'<p class="card-msg"><small>Validade: {res.validade}</small></p>' if res.validade else ""}
</div>
""",
            unsafe_allow_html=True,
        )

        # Botões de ação
        col_a, col_b, _ = st.columns([1.5, 1.5, 5])
        with col_a:
            if res.tem_pdf:
                st.download_button(
                    label="⬇️ Baixar PDF",
                    data=res.pdf_bytes,
                    file_name=f"certidao_{res.tipo}_{cnpj14}.pdf",
                    mime="application/pdf",
                    key=f"dl_{res.tipo}",
                )
                pdfs_disponiveis.append((res.tipo, res.pdf_bytes))
            elif res.url:
                st.link_button("🔗 Abrir Portal", url=res.url, key=f"link_{res.tipo}")
        with col_b:
            if res.url and not res.tem_pdf:
                st.write("")  # espaço

    # ─── Botão: baixar todas as certidões em ZIP + imprimir ──────────────────
    if pdfs_disponiveis:
        import zipfile, io
        st.markdown('<hr class="divisor">', unsafe_allow_html=True)

        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for tipo, dados in pdfs_disponiveis:
                zf.writestr(f"certidao_{tipo}_{cnpj14}.pdf", dados)
        zip_buf.seek(0)

        col_zip, col_print, _ = st.columns([2, 1.5, 4])
        with col_zip:
            st.download_button(
                label=f"📦  Baixar {len(pdfs_disponiveis)} certidão(ões) em ZIP",
                data=zip_buf.getvalue(),
                file_name=f"certidoes_{cnpj14}.zip",
                mime="application/zip",
            )
        with col_print:
            st.markdown(
                '<button onclick="window.print()" style="'
                "background:#0D6E6E;color:#fff;border:none;border-radius:6px;"
                "padding:0.45rem 1rem;font-size:0.9rem;cursor:pointer;width:100%;"
                '">🖨️ Imprimir página</button>',
                unsafe_allow_html=True,
            )

    # ─── Links rápidos para os portais não automatizados ──────────────────────
    portais_manuais = [r for r in resultados.values() if r.status in (Status.ERRO, Status.NAO_SUPORTADO) and r.url]
    if portais_manuais:
        with st.expander("🔗 Portais que precisam de acesso manual"):
            for r in portais_manuais:
                st.markdown(f"**{r.nome}** — [{r.url}]({r.url})")

    # ─── Exportar relatório texto ─────────────────────────────────────────────
    st.markdown('<hr class="divisor">', unsafe_allow_html=True)
    from datetime import datetime

    linhas = [
        "RELATÓRIO DE CERTIDÕES NEGATIVAS",
        "=" * 40,
        f"CNPJ: {cnpj_fmt}",
        f"Estado: {estado_sel}  |  Município: {municipio_input}",
        f"Data/hora: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "",
    ]
    for chave in ORDEM:
        r = resultados[chave]
        linhas.append(f"[{r.label}] {r.nome}")
        linhas.append(f"  Órgão: {r.orgao}")
        linhas.append(f"  {r.mensagem}")
        if r.url:
            linhas.append(f"  Portal: {r.url}")
        linhas.append("")

    relatorio = "\n".join(linhas)
    st.download_button(
        label="📄  Exportar relatório (.txt)",
        data=relatorio.encode("utf-8"),
        file_name=f"relatorio_certidoes_{cnpj14}.txt",
        mime="text/plain",
    )
