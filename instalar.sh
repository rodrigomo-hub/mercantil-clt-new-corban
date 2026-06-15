#!/bin/bash

# Auto-installer: Mercantil CLT Integration
# Uso: curl -sO https://raw.githubusercontent.com/rodrigomo-hub/mercantil-clt-new-corban/main/instalar.sh && bash instalar.sh

set -e

REPO_URL="https://raw.githubusercontent.com/rodrigomo-hub/mercantil-clt-new-corban/main"
INSTALL_DIR="${INSTALL_DIR:-.}"
VENV_DIR="${VENV_DIR:./venv}"

echo "=== Mercantil CLT Integration - Auto Installer ==="
echo "Instalando em: $INSTALL_DIR"
echo "Venv: $VENV_DIR"

# Criar venv
echo "[1/4] Criando virtual environment..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# Baixar mercantil_clt.py
echo "[2/4] Baixando mercantil_clt.py..."
curl -sO "$REPO_URL/mercantil_clt.py"
chmod +x mercantil_clt.py

# Baixar requirements.txt
echo "[3/4] Baixando requirements.txt..."
curl -sO "$REPO_URL/requirements.txt"

# Instalar dependencias
echo "[4/4] Instalando dependências..."
pip install -q -r requirements.txt

echo ""
echo "=== Instalação completa! ==="
echo ""
echo "Para usar:"
echo "  source $VENV_DIR/bin/activate"
echo "  python -c \"from mercantil_clt import fluxo_completo_mercantil_clt; import json; print(json.dumps(fluxo_completo_mercantil_clt('130.702.519-60', data_nascimento='2005-04-19'), indent=2))\""
echo ""
echo "Documentação: https://github.com/rodrigomo-hub/mercantil-clt-new-corban"
