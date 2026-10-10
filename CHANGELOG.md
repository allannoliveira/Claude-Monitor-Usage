# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/); versões seguem [SemVer](https://semver.org/lang/pt-BR/).

## [Não lançado]

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
