# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/); versões seguem [SemVer](https://semver.org/lang/pt-BR/).

## [Não lançado]

## [1.1.0] - 2026-10-09

### Adicionado
- **Discipulinho**, personagem com emoções dentro do widget, colado à esquerda das barras: dormindo (0–10%), feliz, focado lendo a Bíblia, bravo (75–95%) e chorando (≥ 95%), todos animados.
- Arte própria por humor em `<config>/personagem/<humor>.gif|png`.
- Menu da bandeja: *Personagem com emoções* e *Animar personagem*.
- Animações no README (demonstração na barra, humores e estilos), geradas por `scripts/make_docs_gifs.py`.

### Alterado
- O personagem saiu do ícone separado da bandeja: com o widget ligado, a bandeja mostra um ícone genérico.
- O ícone do `.exe` passa a ser o personagem.

### Removido
- Suporte a `boneco.gif/.png/.ico` e à variável `CLAUDE_MONITOR_ICON` (substituídos pela pasta `personagem/`).

## [1.0.0] - 2026-10-09

### Adicionado
- Consulta dos limites oficiais (`/api/oauth/usage`), com fallback pelos headers `anthropic-ratelimit-unified-*`.
- Contagem de tokens a partir dos logs locais do Claude Code (5h, hoje e 7 dias, por modelo).
- Modo bandeja (pystray), com ícone genérico. Aceita um personagem próprio (`boneco.gif`/`.png`/`.ico`, GIF animado) colocado na pasta de configuração.
- Widget dentro da barra de tarefas do Windows, com 3 estilos (Segmentos, Barra contínua, Compacto).
- Fixação automática do ícone na barra do Windows 11.
- Modo terminal (rich): painel único, `--watch` e `--json`.
- Instaladores de um comando (`install.ps1` / `install.sh`), com início automático junto com o sistema.
- CI (Windows + Linux) e release automática por tag.

[Não lançado]: https://github.com/allannoliveira/Claude-Monitor-Usage/compare/v1.1.0...develop
[1.1.0]: https://github.com/allannoliveira/Claude-Monitor-Usage/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/allannoliveira/Claude-Monitor-Usage/releases/tag/v1.0.0
