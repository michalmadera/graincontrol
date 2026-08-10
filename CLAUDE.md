# GrainControl — instrukcje dla Claude Code

## GitHub / konto gh

W tym projekcie **zawsze używaj konta GitHub `michalmadera`**.

Przed jakimkolwiek użyciem `gh` oraz przed operacjami sieciowymi gita
(`pull`, `push`, `fetch`, `clone`) od razu przełącz aktywne konto:

```bash
gh auth switch -u michalmadera
```

Kontekst:

- `origin` = https://github.com/michalmadera/graincontrol.git — repozytorium
  **prywatne**, właściciel `michalmadera`.
- Git korzysta z helpera `gh auth git-credential`, który używa **aktywnego**
  konta gh. Domyślnie aktywne bywa `trogon-eye`, które nie ma dostępu do tego
  repo — wtedy GitHub zwraca 404, a git komunikat
  `remote: Repository not found`.
- Jednorazowa alternatywa bez zmiany aktywnego konta:
  `GH_TOKEN=$(gh auth token --user michalmadera) git pull`
