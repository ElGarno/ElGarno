#!/usr/bin/env bash
# Refresh the local mirror of all own GitHub repositories and rebuild the dashboard.
#
#   ./refresh.sh            clone/update everything, then analyse and render
#   ./refresh.sh --no-fetch skip the network, rebuild from the mirror as it is
#
# Bare clones land in ./repos (roughly 450 MB) and are reused on every later run,
# so only new commits are transferred after the first pass.
set -euo pipefail

OWNER="${GH_STATS_OWNER:-ElGarno}"
EXCLUDE="${GH_STATS_EXCLUDE:-^(obsidian)$}"   # repo names to skip entirely
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPOS="$ROOT/repos"
LIST="$(mktemp)"
trap 'rm -f "$LIST"' EXIT

FETCH=1
[ "${1:-}" = "--no-fetch" ] && FETCH=0
# GH_STATS_QUIET=1 unterdrückt Repo-Namen in der Ausgabe — für öffentliche CI-Logs,
# wo die Namen privater Repositories sonst mitlaufen würden.
QUIET="${GH_STATS_QUIET:-0}"

if [ "$FETCH" -eq 1 ]; then
  command -v gh >/dev/null 2>&1 || { echo "gh CLI nicht gefunden — https://cli.github.com" >&2; exit 1; }
  gh auth status >/dev/null 2>&1 || { echo "gh nicht angemeldet — 'gh auth login' ausführen" >&2; exit 1; }

  echo "Repository-Liste von $OWNER abrufen ..."
  gh repo list "$OWNER" --limit 500 --json name,isFork,isPrivate \
    --jq '[.[] | select(.isFork == false)] | map({(.name): .isPrivate}) | add' > "$ROOT/visibility.json"
  gh repo list "$OWNER" --limit 500 --json name,isFork \
    --jq '.[] | select(.isFork == false) | .name' | grep -Ev "$EXCLUDE" | sort > "$LIST"
  echo "  $(wc -l < "$LIST" | tr -d ' ') eigene Repositories (ohne Forks, ohne Ausnahmen)"

  mkdir -p "$REPOS"
  new=0; upd=0; fail=0
  while IFS= read -r name; do
    [ -n "$name" ] || continue
    target="$REPOS/$name.git"
    if [ -d "$target" ]; then
      if git -C "$target" fetch --quiet --prune origin '+refs/heads/*:refs/heads/*' 2>/dev/null; then
        upd=$((upd + 1))
      else
        [ "$QUIET" = "1" ] && echo "  ! fetch fehlgeschlagen" >&2 || echo "  ! fetch fehlgeschlagen: $name" >&2
        fail=$((fail + 1))
      fi
    else
      if git clone --bare --quiet "https://github.com/$OWNER/$name.git" "$target" 2>/dev/null; then
        [ "$QUIET" = "1" ] || echo "  + neu geklont: $name"
        new=$((new + 1))
      else
        [ "$QUIET" = "1" ] && echo "  ! clone fehlgeschlagen" >&2 || echo "  ! clone fehlgeschlagen: $name" >&2
        fail=$((fail + 1))
      fi
    fi
  done < "$LIST"
  echo "  $upd aktualisiert, $new neu, $fail fehlgeschlagen — $(du -sh "$REPOS" | cut -f1) im Spiegel"
else
  echo "--no-fetch: überspringe GitHub, nutze $REPOS wie er ist"
fi

[ -d "$REPOS" ] || { echo "Kein Spiegel unter $REPOS — einmal ohne --no-fetch starten." >&2; exit 1; }

echo
python3 "$ROOT/analyze.py" "$REPOS" "$ROOT/dashboard-data.json"
echo
python3 "$ROOT/build_dashboard.py" "$ROOT/dashboard-data.json" "$ROOT/commit-dashboard.html"
echo
echo "Fertig. Öffnen mit:  open \"$ROOT/commit-dashboard.html\""
