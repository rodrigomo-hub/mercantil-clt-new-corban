#!/bin/bash

# Auto-installer: Mercantil CLT Integration
# Uso: curl -sO https://raw.githubusercontent.com/rodrigomo-hub/mercantil-clt-new-corban/main/instalar.sh && bash instalar.sh

set -e

REPO_URL="https://raw.githubusercontent.com/rodrigomo-hub/mercantil-clt-new-corban/main"
INSTALL_DIR="${INSTALL_DIR:-/opt/mercantil-clt}"
VENV_DIR="$INSTALL_DIR/venv"
SERVICE_NAME="mercantil-clt"

echo "=== Mercantil CLT Integration - Auto Installer ==="
echo "Instalando em: $INSTALL_DIR"
echo "Venv: $VENV_DIR"

# Criar diretório de instalação
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# Criar venv
echo "[1/6] Criando virtual environment..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# Baixar mercantil_clt.py
echo "[2/6] Baixando mercantil_clt.py..."
curl -sO "$REPO_URL/mercantil_clt.py"
chmod +x mercantil_clt.py

# Baixar requirements.txt
echo "[3/6] Baixando requirements.txt..."
curl -sO "$REPO_URL/requirements.txt"

# Instalar dependencias
echo "[4/6] Instalando dependências..."
pip install -q -r requirements.txt

# Baixar mercantil_api.py
echo "[5/6] Baixando mercantil_api.py..."
curl -sO "$REPO_URL/mercantil_api.py"

# Criar systemd service
echo "[6/6] Criando systemd service..."
sudo tee /etc/systemd/system/$SERVICE_NAME.service > /dev/null << EOF
[Unit]
Description=Mercantil CLT Integration API
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$VENV_DIR/bin"
ExecStart=$VENV_DIR/bin/uvicorn mercantil_api:app --host 0.0.0.0 --port 8003
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Recarregar systemd, habilitar e iniciar o serviço
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME
sudo systemctl start $SERVICE_NAME

echo ""
echo "=== Instalação completa! ==="
echo ""
echo "Serviço: $SERVICE_NAME"
echo "Status:"
sudo systemctl status $SERVICE_NAME
echo ""
echo "A API está rodando em: http://0.0.0.0:8003"
echo "Health check: curl http://localhost:8003/health"
echo ""
echo "Comandos úteis:"
echo "  sudo systemctl status $SERVICE_NAME     # Ver status"
echo "  sudo systemctl restart $SERVICE_NAME    # Reiniciar"
echo "  sudo systemctl stop $SERVICE_NAME       # Parar"
echo "  sudo journalctl -u $SERVICE_NAME -f     # Ver logs em tempo real"
echo ""
echo "Documentação: https://github.com/rodrigomo-hub/mercantil-clt-new-corban"
