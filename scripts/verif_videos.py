"""Vérifie que les vidéos YouTube d'un corpus existent encore et sont jouables.

Deux niveaux, du moins coûteux au plus coûteux :
1. oEmbed public (existence) : 200 = la vidéo existe, 400/404 = supprimée ;
2. page watch publique (jouabilité) : playabilityStatus OK, ou UNPLAYABLE /
   ERROR (supprimée, privée, flux terminé figé), LOGIN_REQUIRED (âge/région).

Limite connue : l'autorisation d'intégration (réglage côté auteur) n'est pas
exposée ; une vidéo « OK » ici peut refuser l'iframe.

Réservé aux corpus réels (data/corpus_real.json, data/corpus_elargi.json) ;
les corpus de démo (corpus_demo, corpus_arbre) utilisent des IDs fictifs.

Usage :  python3 scripts/verif_videos.py data/corpus_real.json [autres...]
Sortie : 0 = tout va bien, 1 = au moins une vidéo morte, 2 = vérification
incomplète (limite de débit YouTube — réessayer plus tard).
"""

from __future__ import annotations

import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)
COOKIES = "CONSENT=YES+cb.20210328-17-p0.en+FX+419; SOCS=CAI"
PAUSE_S = 2.0  # politesse : une page watch toutes les 2 secondes


def youtube_id(url: str) -> str | None:
    """ID YouTube d'une URL watch/youtu.be/embed/shorts, sinon None."""
    for pattern in (
        r"watch\?[^#]*?\bv=([\w-]+)",
        r"youtu\.be/([\w-]+)",
        r"embed/([\w-]+)",
        r"shorts/([\w-]+)",
    ):
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def _open(request: urllib.request.Request, *, retries: int = 1) -> bytes:
    """Ouvre une requête ; retente une fois ; tolère un magasin de certificats absent."""
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        except urllib.error.URLError as err:
            if "CERTIFICATE" not in str(err):
                raise
            contexte = ssl.create_default_context()
            contexte.check_hostname = False
            contexte.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(request, timeout=30, context=contexte) as response:
                return response.read()
        except urllib.error.HTTPError as err:
            if err.code != 429 or attempt == retries:
                raise
            time.sleep(10 * (attempt + 1))
    raise RuntimeError("inatteignable")


def existe_oembed(video_id: str) -> bool:
    """True si l'oEmbed public répond 200 (la vidéo existe)."""
    url = (
        "https://www.youtube.com/oembed?url="
        + urllib.parse.quote(f"https://www.youtube.com/watch?v={video_id}", safe="")
        + "&format=json"
    )
    try:
        _open(urllib.request.Request(url, headers={"User-Agent": UA}))
        return True
    except urllib.error.HTTPError as err:
        if err.code in (400, 404):
            return False
        raise


def playability(video_id: str) -> tuple[str, str]:
    """(statut, raison) de la page watch : OK, UNPLAYABLE, ERROR, ou absent."""
    request = urllib.request.Request(
        f"https://www.youtube.com/watch?v={video_id}",
        headers={
            "User-Agent": UA,
            "Accept-Language": "en-US,en;q=0.9",
            "Cookie": COOKIES,
        },
    )
    try:
        page = _open(request).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as err:
        if err.code == 429:
            return "LIMITE_DEBIT", "HTTP 429 : réessayer plus tard"
        return "ERREUR_REQUETE", f"HTTP {err.code}"
    match = re.search(r"ytInitialPlayerResponse\s*=\s*(\{.*?\});", page, re.DOTALL)
    if not match:
        return "SANS_REPONSE", "page watch sans ytInitialPlayerResponse"
    status = json.loads(match.group(1)).get("playabilityStatus", {})
    return status.get("status", "?"), status.get("reason", "")


def verif_video(video: dict) -> dict:
    """Vérifie une vidéo : oEmbed puis page watch, avec pause de politesse."""
    vid = youtube_id(video.get("url", ""))
    if vid is None:
        return {"id": video["id"], "status": "HORS_YOUTUBE", "reason": "", "title": video["title"]}
    try:
        if not existe_oembed(vid):
            return {"id": vid, "status": "INEXISTANTE", "reason": "oEmbed 400", "title": video["title"]}
        status, reason = playability(vid)
    except Exception as err:  # noqa: BLE001
        status, reason = "INDETERMINEE", str(err)[:80]
    time.sleep(PAUSE_S)
    return {"id": vid, "status": status, "reason": reason, "title": video["title"]}


def main(argv: list[str]) -> int:
    corpus_paths = [Path(a) for a in argv[1:]] or [
        Path(__file__).resolve().parent.parent / "data" / name
        for name in ("corpus_real.json", "corpus_elargi.json")
    ]
    mortes, indeterminees = 0, 0
    for path in corpus_paths:
        corpus = json.loads(path.read_text(encoding="utf-8"))
        results = [verif_video(video) for video in corpus["videos"]]
        ok = [r for r in results if r["status"] == "OK"]
        mortes += sum(r["status"] in ("INEXISTANTE", "UNPLAYABLE", "ERROR") for r in results)
        indeterminees += sum(
            r["status"] not in ("OK", "HORS_YOUTUBE", "INEXISTANTE", "UNPLAYABLE", "ERROR")
            for r in results
        )
        ratees = [r for r in results if r["status"] != "OK" and r["status"] != "HORS_YOUTUBE"]
        print(f"{path} : {len(ok)} jouables, {len(ratees)} en échec ou indéterminées")
        for r in ratees:
            print(f"  {r['id']} [{r['status']}] {r['reason']} — {r['title'][:60]}")
    if mortes:
        return 1
    if indeterminees:
        print("vérification incomplète : relancer plus tard (limite de débit YouTube)")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
