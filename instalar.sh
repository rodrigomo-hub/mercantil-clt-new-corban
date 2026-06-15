#!/bin/bash

# Auto-installer: Mercantil CLT Integration
# Uso: curl -sO https://raw.githubusercontent.com/rodrigomo-hub/mercantil-clt-new-corban/main/instalar.sh && bash instalar.sh

set -e

REPO_URL="https://raw.githubusercontent.com/rodrigomo-hub/mercantil-clt-new-corban/main"
INSTALL_DIR="${INSTALL_DIR:-.}"

echo "=== Mercantil CLT Integration - Auto Installer ==="
echo "Instalando em: $INSTALL_DIR"

# Baixar mercantil_clt.py
echo "[1/3] Baixando mercantil_clt.py..."
curl -sO "$REPO_URL/mercantil_clt.py"
chmod +x mercantil_clt.py

# Baixar requirements.txt
echo "[2/3] Baixando requirements.txt..."
curl -sO "$REPO_URL/requirements.txt"

# Instalar dependencias
echo "[3/3] Instalando dependências..."
pip install -q --break-system-packages -r requirements.txt || pip install -q -r requirements.txt

echo ""
echo "=== Instalação completa! ==="
echo ""
echo "Uso rápido:"
echo "  python -c \"from mercantil_clt import fluxo_completo_mercantil_clt; import json; print(json.dumps(fluxo_completo_mercantil_clt('130.702.519-60', data_nascimento='2005-04-19'), indent=2))\""
echo ""
echo "Documentação: https://github.com/rodrigomo-hub/mercantil-clt-new-corban"
