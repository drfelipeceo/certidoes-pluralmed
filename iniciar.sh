#!/bin/bash
# Inicia o sistema de consulta de certidões negativas
cd "$(dirname "$0")"
python3 -m streamlit run app.py --server.port 8501
