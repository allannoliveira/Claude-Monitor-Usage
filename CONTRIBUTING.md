# Fluxo de desenvolvimento, merges e deploy

## Branches

| Branch | Papel | Recebe merge de |
|---|---|---|
| `main` | **Produção / deploy.** Cada versão publicada sai daqui, com uma tag `vX.Y.Z`. | `develop` (release) ou `hotfix/*` |
| `develop` | **Integração.** É onde as funcionalidades se juntam e são testadas. | `feature/*`, `fix/*` |
| `feature/<nome>` | Nova funcionalidade | — (sai de `develop`) |
| `fix/<nome>` | Correção sem urgência | — (sai de `develop`) |
| `hotfix/<nome>` | Correção urgente em produção | — (sai de `main`) |

Ninguém faz commit direto em `main` ou `develop`. Toda mudança entra por **Pull Request**, e o CI (`.github/workflows/ci.yml`) precisa passar no Windows e no Linux.

## Dia a dia (feature → develop)

```bash
git checkout develop && git pull
git checkout -b feature/meu-recurso
# ... código + testes ...
python -m pytest -q
git commit -am "feat: descreve o recurso"
git push -u origin feature/meu-recurso
# abra o PR no GitHub: feature/meu-recurso → develop
```

## Deploy (develop → main → Release)

1. Na `develop`, atualize a versão em `claude_monitor/__init__.py` (`__version__ = "1.1.0"`) e o `CHANGELOG.md`.
2. Abra um PR **develop → main** e faça o merge depois que o CI passar.
3. Crie a tag na `main`:
   ```bash
   git checkout main && git pull
   git tag v1.1.0
   git push origin v1.1.0
   ```
4. O workflow `release.yml` confere se a tag é igual à `__version__` e roda os testes. Depois ele gera `claude-monitor.exe`, o wheel e o sdist, e publica a **GitHub Release**.
5. Quem usa o instalador de um comando pega a versão nova rodando o instalador de novo.

## Hotfix (main → main + develop)

```bash
git checkout main && git pull
git checkout -b hotfix/corrige-x
# ... correção + bump de patch (1.1.0 -> 1.1.1) ...
# PR hotfix/corrige-x → main, merge, tag v1.1.1
# depois: PR main → develop (ou merge local) para a develop não perder a correção
```

## Versionamento

O projeto usa [SemVer](https://semver.org/lang/pt-BR/): `MAJOR.MINOR.PATCH`.
- **PATCH:** correção.
- **MINOR:** funcionalidade nova compatível.
- **MAJOR:** mudança incompatível.

## Mensagens de commit

O projeto usa [Conventional Commits](https://www.conventionalcommits.org/pt-br/): `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `ci:`, `chore:`.

## Proteção de branches (configurar uma vez no GitHub)

Em *Settings → Branches → Add rule*, crie uma regra para `main` e outra para `develop` com:
- **Require a pull request before merging**
- **Require status checks to pass:** os jobs `Testes (...)` do CI
- **Do not allow bypassing** (opcional)
