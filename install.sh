#!/usr/bin/env sh
# Instalador de um comando para Linux.
#   Local:   sh install.sh
#   Remoto:  curl -LsSf https://raw.githubusercontent.com/allannoliveira/Claude-Monitor-Usage/main/install.sh | sh
#   Opções (variáveis): SOURCE=<pasta ou git+https://...>  NO_AUTOSTART=1
set -eu

DEFAULT_REPO="git+https://github.com/allannoliveira/Claude-Monitor-Usage"
SCRIPT_DIR=$(cd "$(dirname "$0")" 2>/dev/null && pwd || echo "")
if [ -z "${SOURCE:-}" ]; then
    if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/pyproject.toml" ]; then SOURCE="$SCRIPT_DIR"; else SOURCE="$DEFAULT_REPO"; fi
fi

# 1. uv
if ! command -v uv >/dev/null 2>&1; then
    echo "Instalando uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    PATH="$HOME/.local/bin:$PATH"
fi

# 2. Boneco na pasta do usuário
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/claude-monitor"
mkdir -p "$CONFIG_DIR"
for name in boneco.gif boneco.png boneco.ico; do
    if [ -f "$SOURCE/$name" ]; then cp "$SOURCE/$name" "$CONFIG_DIR/"; echo "Ícone copiado: $CONFIG_DIR/$name"; fi
done

# 3. Instala (com PyGObject para o tray via AppIndicator, se as libs do sistema existirem)
echo "Instalando claude-monitor de $SOURCE ..."
if uv tool install --force --with PyGObject "$SOURCE" 2>/dev/null; then
    :
else
    echo "Aviso: PyGObject não compilou (faltam libs do sistema). Instalando sem ele;"
    echo "       o tray usará o backend xorg. Para AppIndicator:"
    echo "       sudo apt install libgirepository1.0-dev libcairo2-dev gir1.2-ayatanaappindicator3-0.1"
    uv tool install --force "$SOURCE"
fi
uv tool update-shell >/dev/null 2>&1 || true

# 4. Autostart (padrão freedesktop)
BIN_DIR=$(uv tool dir --bin)
if [ -z "${NO_AUTOSTART:-}" ]; then
    AUTOSTART="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
    mkdir -p "$AUTOSTART"
    cat > "$AUTOSTART/claude-monitor.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Claude Monitor
Exec=$BIN_DIR/claude-monitor-tray
X-GNOME-Autostart-enabled=true
EOF
    echo "Autostart criado em $AUTOSTART/claude-monitor.desktop"
fi

echo ""
echo "Pronto! Abra um NOVO terminal e use:"
echo "  claude-monitor            (bandeja)"
echo "  claude-monitor cli        (terminal)"
echo "  claude-monitor cli -w     (terminal ao vivo)"
