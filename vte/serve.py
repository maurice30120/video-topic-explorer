"""Serveur local minimal (stdlib uniquement) pour la page de parcours.

Sert la page de sélection (départ vidéo ou sujet, mode Approfondir/Découvrir),
lance les parcours via le moteur pur, écrit un run.json par parcours lancé,
affiche les motifs d'erreur (parcours partiel, départ isolé) et sert le
graphe statique surligné à la demande. Pas de framework, pas de réseau externe.
"""
from __future__ import annotations

import html
import json
import tempfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote_plus, urlparse

from . import graph_engine
from .corpus import videos_by_id

SEUIL_MS = 5000


def rayon_depuis_duree(duree_ms: int) -> int:
    """Rétention applicative → rayon du pas suivant (mapping binaire, spec #27).

    Rester longtemps (durée ≥ SEUIL_MS) c'est aimer : le pas reste dans le
    voisinage immédiat (rayon 1). Passer vite (durée < SEUIL_MS) c'est ne pas
    aimer : le pas s'éloigne (rayon 3). Pas de bande intermédiaire.
    """
    return 1 if duree_ms >= SEUIL_MS else 3


def panel_start(corpus: dict[str, Any]) -> tuple[str | None, graph_engine.Run | None]:
    """Départ du panneau : la vidéo par défaut si présente, sinon la première
    vidéo (triée par id) qui donne un parcours — l'index reste utile sur tout corpus figé."""
    from . import DEFAULT_START

    ids = [video["id"] for video in corpus["videos"]]
    candidates = ([DEFAULT_START] if DEFAULT_START in ids else []) + sorted(ids)
    for candidate in candidates:
        try:
            return candidate, graph_engine.parcours(corpus, candidate, "decouvrir")
        except graph_engine.PathfindingError:
            continue
    return None, None


def card_html(video: dict[str, Any], chemin: str) -> str:
    """Carte du panneau : la vidéo, ses sujets, et le chemin de sujets qui y a mené."""
    sujets = ", ".join(html.escape(t["canonical"]) for t in video.get("topics", []))
    return (
        f'<section class="carte" data-video="{html.escape(video["id"])}">'
        f'<p class="chemin">{html.escape(chemin)}</p>'
        f'<h2 class="titre">{html.escape(video["title"])}</h2>'
        f'<p class="sujets">{sujets}</p>'
        f'<a class="lien" href="{html.escape(video["url"])}">voir la vidéo</a>'
        "</section>"
    )


_PANEL_JS = """
var SEUIL_MS = 5000;
var panneau = document.getElementById("panneau");
var mode = panneau.dataset.mode;
var pivot = null;
var timerPivot = null;
var enCours = false;
var terminee = false;

function cartes() { return Array.prototype.slice.call(panneau.querySelectorAll(".carte")); }

/* rétention applicative : rester SEUIL_MS sur une carte en fait le pivot */
function marquerPivot(carte) {
  pivot = carte.dataset.video;
  var ancien = panneau.querySelector(".pivot-badge");
  if (ancien) { ancien.remove(); }
  var badge = document.createElement("p");
  badge.className = "pivot-badge";
  badge.textContent = "orientation : " + carte.querySelector(".titre").textContent;
  carte.appendChild(badge);
}

function ajouterCarte(data) {
  var section = document.createElement("section");
  section.className = "carte";
  section.dataset.video = data.video.id;
  var chemin = document.createElement("p");
  chemin.className = "chemin";
  chemin.textContent = data.topic_path.join(" \u2192 ");
  var titre = document.createElement("h2");
  titre.className = "titre";
  titre.textContent = data.video.title;
  var sujets = document.createElement("p");
  sujets.className = "sujets";
  sujets.textContent = data.video.topics.join(", ");
  var lien = document.createElement("a");
  lien.className = "lien";
  lien.href = data.video.url;
  lien.textContent = "voir la vid\u00e9o";
  section.appendChild(chemin); section.appendChild(titre);
  section.appendChild(sujets); section.appendChild(lien);
  panneau.appendChild(section);
  observer.observe(section);
}

/* la suite est demandée depuis le pivot (la vidéo réellement regardée),
   jamais depuis l'ordre linéaire des cartes déjà défilées vite */
function etendre() {
  if (enCours || terminee) { return; }
  var liste = cartes();
  var derniere = liste[liste.length - 1];
  var depuis = pivot || derniere.dataset.video;
  var exclus = liste.map(function (c) { return c.dataset.video; }).join("&exclu=");
  enCours = true;
  fetch("/etape?from=" + encodeURIComponent(depuis) + "&mode=" + mode + "&exclu=" + exclus)
    .then(function (reponse) {
      if (reponse.status === 404) { terminee = true; return null; }
      if (!reponse.ok) { return null; }
      return reponse.json();
    })
    .then(function (data) { if (data) { ajouterCarte(data); } })
    .finally(function () { enCours = false; });
}

var observer = new IntersectionObserver(function (entries) {
  entries.forEach(function (entry) {
    if (entry.intersectionRatio >= 0.6) { activer(entry.target); }
  });
}, { threshold: [0.6] });

function activer(carte) {
  if (timerPivot) { clearTimeout(timerPivot); }
  timerPivot = setTimeout(function () { marquerPivot(carte); }, SEUIL_MS);
  var liste = cartes();
  if (carte === liste[liste.length - 1]) { etendre(); }
}

cartes().forEach(function (c) { observer.observe(c); });
"""


def index_page(corpus: dict[str, Any], start: str | None = None, run: graph_engine.Run | None = None) -> str:
    """Sélection départ/mode + panneau scroll à rétention.

    Le panneau embarque la chaîne initiale du moteur (chemins de sujets affichés
    sur chaque transition) ; la suite est demandée à /etape depuis la vidéo
    réellement regardée : rester sur une carte en fait le pivot, le scroll
    suit la branche du pivot (GLOSSARY, « Rétention applicative »).
    """
    videos = sorted(corpus["videos"], key=lambda v: v["id"])
    topics = sorted({t["canonical"] for v in corpus["videos"] for t in v.get("topics", [])})
    video_options = "\n".join(
        f'<option value="{html.escape(v["id"])}">'
        f"{html.escape(v['title'])} ({html.escape(v['id'])})</option>"
        for v in videos
    )
    topic_options = "\n".join(
        f'<option value="{html.escape(t)}">{html.escape(t)}</option>' for t in topics
    )
    if run is not None:
        by_id = {v["id"]: v for v in corpus["videos"]}
        cards = "\n".join(
            card_html(by_id[vid], "point de départ" if i == 0 else run.transitions[i - 1]["explanation"])
            for i, vid in enumerate(run.videos)
        )
    else:
        cards = '<section class="carte"><p class="chemin">aucun parcours possible depuis ce corpus</p></section>'
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Video Topic Explorer — parcours</title>
<style>
html, body {{ height: 100%; margin: 0; }}
body {{ font-family: sans-serif; display: flex; flex-direction: column; }}
.entete {{ padding: 0.75rem 2rem; }}
.entete h1 {{ font-size: 1.1rem; margin: 0 0 0.5rem; }}
label {{ display: block; margin: 0.25rem 0; }}
.panneau {{ flex: 1; overflow-y: auto; scroll-snap-type: y mandatory; background: #faf7f2; }}
.carte {{ min-height: 92%; scroll-snap-align: start; max-width: 560px; margin: 0 auto; padding: 1.5rem 1rem; border-top: 1px solid #e0d8cc; }}
.chemin {{ color: #a0642a; font-size: 0.9rem; margin: 0 0 0.5rem; }}
.titre {{ margin: 0 0 0.5rem; }}
.sujets {{ color: #555; font-size: 0.9rem; }}
.lien {{ display: inline-block; margin-top: 0.75rem; }}
.pivot-badge {{ color: #1a7f37; font-weight: bold; margin: 0.75rem 0 0; }}
.conseil {{ color: #777; font-size: 0.85rem; margin: 0.5rem 0 0; }}
</style>
</head>
<body>
<header class="entete">
<h1>Video Topic Explorer</h1>
<form action="/parcours" method="get">
<label>Point de départ
<select name="start">
<optgroup label="Vidéos">
{video_options}
</optgroup>
<optgroup label="Sujets">
{topic_options}
</optgroup>
</select>
</label>
<label>Mode
<input type="radio" name="mode" value="approfondir" checked> Approfondir
<input type="radio" name="mode" value="decouvrir"> Découvrir
</label>
<button type="submit">Lancer le parcours</button>
</form>
<p class="conseil">Panneau ci-dessous : restez sur une vidéo pour en faire le pivot — la suite suivra sa branche.</p>
</header>
<main class="panneau" id="panneau" data-mode="decouvrir">
{cards}
</main>
<script>
{_PANEL_JS}
</script>
</body>
</html>
"""


def error_page(message: str) -> str:
    """Page d'erreur explicite : motif du moteur + retour à la sélection."""
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Parcours impossible</title>
<style>
body {{ font-family: sans-serif; margin: 2rem; }}
.reason {{ color: #a33; }}
</style>
</head>
<body>
<h1>Parcours impossible</h1>
<p class="reason">{html.escape(message)}</p>
<p><a href="/graphe.png">afficher le graphe du corpus</a> pour visualiser la topologie</p>
<p><a href="/">← nouvelle sélection</a></p>
</body>
</html>
"""


def parcours_page(corpus: dict[str, Any], run: graph_engine.Run, start: str, mode: str) -> str:
    """Rend la page du parcours avec le lien vers le graphe surligné à la demande."""
    from .render import build_html

    graph_href = f"/graphe.png?start={quote_plus(start)}&mode={quote_plus(mode)}"
    return build_html(corpus, run.to_dict(), graph_href)


def graph_png(corpus: dict[str, Any], start: str, mode: str) -> bytes:
    """Rend le graphe statique ; sous-graphe du parcours surligné si start/mode fournis.

    Un start/mode invalide ou isolé rend le graphe complet, sans surlignage :
    c'est exactement ce que suggère le message « affichez le graphe du corpus ».
    """
    from .render import render_graph

    run = None
    if start and mode:
        try:
            run = graph_engine.parcours(corpus, start, mode).to_dict()
        except graph_engine.PathfindingError:
            run = None
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "graphe.png"
        render_graph(corpus, run, out)
        return out.read_bytes()


def make_handler(corpus: dict[str, Any], runs_dir: Path) -> type[BaseHTTPRequestHandler]:
    """Fabrique une classe handler fermée sur le corpus figé et le répertoire des runs."""

    class PageHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                start, run = panel_start(corpus)
                self._send_html(200, index_page(corpus, start, run))
            elif parsed.path == "/etape":
                self._handle_etape(parse_qs(parsed.query))
            elif parsed.path == "/parcours":
                self._handle_parcours(parse_qs(parsed.query))
            elif parsed.path == "/graphe.png":
                query = parse_qs(parsed.query)
                start = (query.get("start") or [""])[0]
                mode = (query.get("mode") or [""])[0]
                self._send_png(graph_png(corpus, start, mode))
            else:
                self._send_html(404, "<html><body><p>page inconnue</p></body></html>")

        def _handle_parcours(self, query: dict[str, list[str]]) -> None:
            start = (query.get("start") or [""])[0]
            mode = (query.get("mode") or [""])[0]
            try:
                run = graph_engine.parcours(corpus, start, mode)
            except graph_engine.PathfindingError as exc:
                self._send_html(400, error_page(str(exc)))
                return
            # Un run.json par parcours lancé depuis la page, au même format que la CLI.
            graph_engine.save_run(run, Path(runs_dir) / f"{start}-{mode}.json")
            self._send_html(200, parcours_page(corpus, run, start, mode))

        def _handle_etape(self, query: dict[str, list[str]]) -> None:
            """Pas suivant orienté par la carte quittée, servi en JSON au panneau.

            Phase d'expand : la durée de visionnage de la carte quittée pilote
            le rayon côté serveur (rétention applicative) ; l'ancien paramètre
            de mode reste accepté.
            """
            start = (query.get("from") or [""])[0]
            mode = (query.get("mode") or ["decouvrir"])[0]
            exclu = set(query.get("exclu") or [])
            duree = (query.get("duree") or [None])[0]
            if duree is not None:
                try:
                    rayon = rayon_depuis_duree(int(duree))
                except ValueError:
                    self._send_json(400, {"erreur": f"durée invalide : {duree!r} (attendu : des millisecondes entières)"})
                    return
            try:
                if duree is not None:
                    step = graph_engine.next_step(corpus, start, radius=rayon, exclude=exclu)
                else:
                    step = graph_engine.next_step(corpus, start, mode, exclude=exclu)
            except graph_engine.PathfindingError as exc:
                self._send_json(400, {"erreur": str(exc)})
                return
            if step is None:
                self._send_json(404, {"erreur": "plus aucune vidéo atteignable depuis " + start + " (exclusions ou topologie)"})
                return
            video = videos_by_id(corpus)[step["to"]]
            self._send_json(200, {
                "from": step["from"],
                "to": step["to"],
                "video": {
                    "id": video["id"],
                    "url": video["url"],
                    "title": video["title"],
                    "topics": sorted(t["canonical"] for t in video.get("topics", [])),
                },
                "topic_path": step["topic_path"],
                "explanation": step["explanation"],
            })

        def _send_json(self, code: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self._send_bytes(code, "application/json; charset=utf-8", body)

        def _send_html(self, code: int, doc: str) -> None:
            self._send_bytes(code, "text/html; charset=utf-8", doc.encode("utf-8"))

        def _send_png(self, data: bytes) -> None:
            self._send_bytes(200, "image/png", data)

        def _send_bytes(self, code: int, content_type: str, body: bytes) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: Any) -> None:
            pass

    return PageHandler


def make_server(
    corpus: dict[str, Any], runs_dir: Path, host: str = "127.0.0.1", port: int = 8000
) -> HTTPServer:
    return HTTPServer((host, port), make_handler(corpus, Path(runs_dir)))


def serve_forever(
    corpus: dict[str, Any], runs_dir: Path, host: str = "127.0.0.1", port: int = 8000
) -> None:
    """Lance le serveur (bloquant) : la page de sélection est sur http://host:port/."""
    httpd = make_server(corpus, Path(runs_dir), host=host, port=port)
    print(f"page : http://{host}:{port}/ (Ctrl-C pour arrêter)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
