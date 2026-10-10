# Claude Monitor Usage

[![CI](https://github.com/allannoliveira/Claude-Monitor-Usage/actions/workflows/ci.yml/badge.svg)](https://github.com/allannoliveira/Claude-Monitor-Usage/actions/workflows/ci.yml)

Mostra o uso e os limites do Claude Code de três formas: um widget com barrinhas dentro da barra de tarefas do Windows, um ícone animado na bandeja do sistema e um painel no terminal. Funciona no Windows e no Linux.
É um port em Python da lógica de [CodeZeno/Claude-Code-Usage-Monitor](https://github.com/CodeZeno/Claude-Code-Usage-Monitor) (Rust).

## Como funciona

| Dado | Origem |
|---|---|
| **% da sessão (5h) e % semanal**, com horário de reset | Endpoint oficial `GET https://api.anthropic.com/api/oauth/usage`, autenticado com o token OAuth do Claude Code (`~/.claude/.credentials.json`) |
| Fallback, caso o endpoint acima não exista para a sua conta | Chamada mínima (1 token, Haiku) à Messages API, lendo os headers `anthropic-ratelimit-unified-*` |
| **Tokens consumidos** (5h / hoje / 7 dias, por modelo) | Logs locais `~/.claude/projects/**/*.jsonl`, deduplicados por `message.id` |

Se o token estiver expirado, o app roda `claude -p .` para o próprio CLI renová-lo, como faz o projeto original. Para desativar isso, defina `CLAUDE_MONITOR_NO_CLI_REFRESH=1`.

## Widget na barra de tarefas (Windows)

Ao lado dos ícones da bandeja aparecem duas linhas, uma para a sessão de 5h e outra para a semanal, com o percentual usado e o tempo até o reset:

```
5h ■■■■■■■■□□ 79% · 2h
7d ■□□□□□□□□□ 11% · 4d
```

| Estilo | Visual |
|---|---|
| **Segmentos** (padrão) | 10 blocos laranja; ficam vermelhos a partir de 90% |
| **Barra contínua** | barra lisa verde (< 70%), amarela (70–89%) ou vermelha (≥ 90%) |
| **Compacto** | bolinha colorida + percentual, ocupa pouco espaço |

- **Clique esquerdo** no widget: troca para o próximo estilo.
- **Clique direito:** menu com os estilos, *Atualizar*, *Esconder widget* e *Sair*.
- O menu da bandeja também tem *Widget na barra de tarefas* (liga e desliga) e *Estilo do widget*.
- A escolha fica salva em `%APPDATA%\claude-monitor\settings.json`.
- Para não usar o widget, rode com `--no-widget`.

O widget é uma janela com transparência por pixel presa dentro da barra de tarefas (`Shell_TrayWnd`), a mesma técnica do projeto original. Ela acompanha o tema claro ou escuro e o DPI, e se reposiciona sozinha quando a área de ícones muda de tamanho ou quando o Explorer reinicia. No Linux só existe o ícone da bandeja.

## Estrutura

```
Claude-Monitor-Usage/
├── main.py                  # atalho: python main.py [tray|cli]
├── boneco.gif               # ícone (animado) da bandeja
├── install.ps1 / install.sh # instaladores de um comando
├── scripts/build_exe.py     # gera o .exe (PyInstaller)
├── tests/                   # pytest
├── .github/workflows/       # CI + release automática
└── claude_monitor/
    ├── app.py               # argparse / entry points
    ├── paths.py             # caminhos multiplataforma (credenciais, logs, ícone)
    ├── models.py            # dataclasses (UsageWindow, TokenTotals, Snapshot)
    ├── usage_api.py         # credenciais OAuth + API de uso + fallback por headers
    ├── local_logs.py        # soma de tokens dos .jsonl
    ├── service.py           # fachada get_snapshot() usada pelas UIs
    ├── formatting.py        # números, tempos, barras (sem UI)
    ├── settings.py          # preferências salvas (estilo do widget etc.)
    ├── cli.py               # modo terminal (rich)
    ├── tray.py              # modo bandeja (pystray + Pillow)
    ├── widget_render.py     # desenho dos 3 estilos do widget (Pillow)
    ├── taskbar_widget.py    # janela Win32 dentro da barra de tarefas (ctypes)
    └── win_tray.py          # fixa o ícone na barra do Windows 11
```

A lógica de monitoramento (`usage_api`, `local_logs`, `service`) não importa nada de UI.

## O ícone do boneco

- **Nome:** `boneco.gif` (animado), `boneco.png` ou `boneco.ico`, nesta ordem de preferência.
- **GIF animado:** o ícone da bandeja toca os quadros do GIF respeitando a duração de cada um. Pixel art (GIF ou imagens até 128 px) é ampliada sem suavização para não borrar. Para desligar a animação, use o menu "Animar ícone", `--no-anim` ou `CLAUDE_MONITOR_NO_ANIMATION=1`.
- **Local:** na raiz do projeto, ao lado do `main.py`. Na versão instalada, em `%APPDATA%\claude-monitor\` (Windows) ou `~/.config/claude-monitor/` (Linux).
- **Tamanho:** quadrado, de preferência **256×256 px** (o mínimo recomendado é 64×64). O app redimensiona para 64×64 com antialiasing, e o sistema reduz para 16–32 px na barra.
- **Formato:** PNG **com fundo transparente** (RGBA). Use desenhos simples e de alto contraste, porque detalhes finos somem em 16 px. Se for `.ico`, inclua as resoluções 16, 32, 48 e 256; o app usa a maior.
- **Outro caminho:** defina `CLAUDE_MONITOR_ICON=/caminho/para/imagem.png`.
- **Fallback:** se o arquivo não existir ou estiver corrompido, o app desenha um bonequinho genérico e mostra um aviso no console. Ele não fecha.
- **Barrinhas no ícone** (desligadas por padrão, porque o widget já mostra o uso): à direita do boneco aparecem duas barras verticais, a primeira para a sessão de 5h e a segunda para a semanal. Elas enchem de baixo para cima e ficam verdes abaixo de 70%, amarelas de 70% a 89% e vermelhas a partir de 90%. Para ligar ou desligar, use o menu "Barrinhas no ícone".
- **Sempre visível (Windows 11):** ao abrir, o app marca o próprio ícone como fixo na barra (`IsPromoted = 1` em `HKCU\Control Panel\NotifyIconSettings`), para ele não ficar escondido no menu **^**. Se ainda aparecer escondido, arraste o ícone da setinha para a barra uma vez. No Windows 10 e no Linux, quem controla isso é o sistema.

## Instalação com um comando

Os scripts instalam o [uv](https://docs.astral.sh/uv/) se ele faltar (o uv também baixa o Python, se precisar). Depois eles instalam o app isolado, criam os comandos `claude-monitor` e `claude-monitor-tray`, copiam o `boneco.png` para a pasta do usuário e configuram o app para iniciar com o sistema.

| | A partir desta pasta | Direto do GitHub (depois de publicar o repo) |
|---|---|---|
| **Windows** | `powershell -ExecutionPolicy Bypass -File install.ps1` | `irm https://raw.githubusercontent.com/allannoliveira/Claude-Monitor-Usage/main/install.ps1 \| iex` |
| **Linux** | `sh install.sh` | `curl -LsSf https://raw.githubusercontent.com/allannoliveira/Claude-Monitor-Usage/main/install.sh \| sh` |

- Para não iniciar com o sistema: `install.ps1 -NoAutostart` ou `NO_AUTOSTART=1 sh install.sh`.
- Para atualizar, rode o instalador de novo. Para desinstalar: `uv tool uninstall claude-monitor`. O atalho de inicialização fica em `shell:startup` (Windows) ou `~/.config/autostart/claude-monitor.desktop` (Linux).
- Sem os scripts: `uv tool install .` ou `pipx install .`.
- **Ícone na versão instalada:** `%APPDATA%\claude-monitor\boneco.png` (Windows) ou `~/.config/claude-monitor/boneco.png` (Linux).

Depois de instalar, abra um terminal novo e use `claude-monitor` (tray), `claude-monitor cli` ou `claude-monitor cli -w`.

## Instalação manual (para desenvolvimento)

**Windows (PowerShell):**
```powershell
cd E:\projetos\gestorTokensClaude
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Linux:**
```bash
cd ~/gestorTokensClaude
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

No Linux, o tray precisa de um backend gráfico:
- **GNOME / Ubuntu / Fedora (AppIndicator, recomendado):**
  `sudo apt install gir1.2-ayatanaappindicator3-0.1 libgirepository1.0-dev libcairo2-dev` e depois `pip install PyGObject` dentro do venv.
  No GNOME, também é preciso ativar a extensão "AppIndicator and KStatusNotifierItem Support".
- **Sem AppIndicator:** force o backend X11 com `PYSTRAY_BACKEND=xorg python main.py`. Nesse backend o menu é limitado.
- **Sem interface gráfica (SSH/servidor):** use o modo terminal.

É preciso já ter feito login no Claude Code (`claude`) com uma conta Pro, Max, Team ou Enterprise.

## Como rodar

### Modo Tray (padrão)
```bash
python main.py            # ou: python main.py tray
python main.py tray -i 120   # atualiza a cada 120 s (padrão 300, mínimo 60)
```
- Passe o mouse sobre o ícone para ver o tooltip (`Sessão 7% | Semanal 2%`).
- Clique com o botão direito para ver as linhas de consumo, **Atualizar** e **Sair**. No Windows, o clique esquerdo também atualiza.
- **Windows, sem janela de console:** `.venv\Scripts\pythonw.exe main.py`. Para iniciar com o Windows, crie um atalho desse comando em `shell:startup`.
- **Linux, em segundo plano:** `nohup python main.py >/dev/null 2>&1 &`.

### Modo Terminal
```bash
python main.py cli                # mostra uma vez e sai
python main.py cli --watch        # painel ao vivo, atualiza a cada 60 s (Ctrl+C sai)
python main.py cli -w -i 30       # ao vivo a cada 30 s
python main.py cli --json         # saída JSON (para scripts/integrações)
python main.py cli --no-local     # só os limites da API, sem ler os .jsonl
```

## Variáveis de ambiente

| Variável | Efeito |
|---|---|
| `CLAUDE_CONFIG_DIR` | Pasta de configuração do Claude Code (padrão `~/.claude`) |
| `CLAUDE_MONITOR_ICON` | Caminho de um ícone alternativo (`.gif`, `.png` ou `.ico`) |
| `CLAUDE_MONITOR_NO_ANIMATION` | Se definida, não anima o GIF |
| `CLAUDE_MONITOR_NO_CLI_REFRESH` | Se definida, não roda `claude -p .` para renovar o token expirado |
| `PYSTRAY_BACKEND` | Backend do tray no Linux (`appindicator`, `gtk`, `xorg`) |

## Observações

- O endpoint `/api/oauth/usage` não é documentado publicamente e pode mudar. O parser aceita o formato clássico (`five_hour`, `seven_day`, `seven_day_opus`…) e o formato novo, com o array `limits`.
- Os percentuais da API são a fonte oficial dos limites. Os tokens dos logs são uma contagem local: só incluem o que rodou nesta máquina e incluem leituras de cache, que pesam pouco no limite.

## Desenvolvimento, merges e deploy

- **Branches:** `main` é a produção (deploy) e `develop` é a integração. O trabalho acontece em `feature/*`, `fix/*` e `hotfix/*`, sempre via Pull Request.
- **CI:** cada push e cada PR rodam os testes no Windows e no Linux (Python 3.10 e 3.13).
- **Deploy:** depois do merge `develop → main`, rode `git tag vX.Y.Z && git push origin vX.Y.Z`. A release com `claude-monitor.exe` e o wheel é publicada automaticamente.
- **Executável local:** `pip install pyinstaller` e depois `python scripts/build_exe.py` (o arquivo sai em `dist/claude-monitor.exe`).
- **Testes:** `pip install -e ".[dev]"` e depois `python -m pytest -q`.

O passo a passo completo está em [CONTRIBUTING.md](CONTRIBUTING.md).
