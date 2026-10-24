"""Serveur local minimal (stdlib uniquement) pour le parcours sensible à la rétention.

Sert le panneau piloté par le visionnage (carte de départ embarquée, mesure
de durée par carte, sélecteur de sujets et commande de sortie de branche),
les points d'accès JSON du pas suivant (/etape, durée de la carte quittée,
rayon dérivé côté serveur) et de la sortie dirigée (/sortie), la page
du parcours complet via le moteur pur avec un run.json par parcours lancé,
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
from .session import RAYON_PASSER_VITE, rayon_depuis_duree

_RAYON_INVALIDE = object()
"""Sentinelle : le paramètre rayon est présent mais n'est pas un entier."""


def _parse_rayon(query: dict[str, list[str]]) -> int | None | object:
    """Extrait le rayon d'une query : absent → None (le moteur répondra), présent
    mais non entier → _RAYON_INVALIDE (le point d'accès répond 400 explicite)."""
    raw = (query.get("rayon") or [None])[0]
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return _RAYON_INVALIDE


def panel_start(corpus: dict[str, Any]) -> str | None:
    """Départ du panneau : la vidéo par défaut si présente, sinon la première
    vidéo (triée par id) qui donne un premier pas — l'index reste utile sur tout corpus figé."""
    from . import DEFAULT_START

    ids = [video["id"] for video in corpus["videos"]]
    candidates = ([DEFAULT_START] if DEFAULT_START in ids else []) + sorted(ids)
    for candidate in candidates:
        try:
            # Seule la carte de départ est embarquée : chaque carte suivante
            # arrive via /etape au départ de la précédente, la première carte
            # oriente donc le premier pas via sa durée (spec #27, stories 2-5).
            graph_engine.next_step(corpus, candidate, radius=RAYON_PASSER_VITE)
            return candidate
        except graph_engine.PathfindingError:
            continue
    return None


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
var panneau = document.getElementById("panneau");
var selecteur = document.getElementById("sujet");
var message = document.getElementById("message");
var carteActive = null;
var activation = null;
var enCours = false;
var terminee = false;

function cartes() { return Array.prototype.slice.call(panneau.querySelectorAll(".carte[data-video]")); }

function exclus() {
  return cartes().map(function (c) { return c.dataset.video; }).join("&exclu=");
}

function ajouterCarte(data) {
  var section = document.createElement("section");
  section.className = "carte";
  section.dataset.video = data.video.id;
  var chemin = document.createElement("p");
  chemin.className = "chemin";
  chemin.textContent = data.topic_path.join(" → ");
  var titre = document.createElement("h2");
  titre.className = "titre";
  titre.textContent = data.video.title;
  var sujets = document.createElement("p");
  sujets.className = "sujets";
  sujets.textContent = data.video.topics.join(", ");
  var lien = document.createElement("a");
  lien.className = "lien";
  lien.href = data.video.url;
  lien.textContent = "voir la vidéo";
  section.appendChild(chemin); section.appendChild(titre);
  section.appendChild(sujets); section.appendChild(lien);
  panneau.appendChild(section);
  observer.observe(section);
}

/* la fin honnête est explicite : plus aucune candidate ne reste */
function arreterHonnetement() {
  terminee = true;
  var fin = document.createElement("section");
  fin.className = "carte";
  var p = document.createElement("p");
  p.className = "chemin";
  p.textContent = "fin honnête : plus aucune candidate ne reste";
  fin.appendChild(p);
  panneau.appendChild(fin);
}

/* rétention applicative : la durée de visionnage d'une carte se mesure
   entre son activation et son départ ; la demande part au moment exact
   où la carte courante est quittée, avec sa durée — le serveur dérive
   le rayon (rester longtemps = rayon 1, passer vite = rayon 3) */
function demanderPas(url) {
  enCours = true;
  fetch(url)
    .then(function (reponse) {
      if (reponse.status === 404) { arreterHonnetement(); return null; }
      if (!reponse.ok) { return reponse.json().then(function (data) { throw new Error(data.erreur); }); }
      return reponse.json();
    })
    .then(function (data) { if (data) { ajouterCarte(data); } })
    .catch(function (erreur) { message.textContent = erreur.message; })
    .finally(function () { enCours = false; });
}

function pasSuivant(depuis, duree) {
  if (enCours || terminee) { return; }
  demanderPas("/etape?from=" + encodeURIComponent(depuis) + "&duree=" + duree + "&exclu=" + exclus());
}

/* sortie de branche dirigée : navigation explicite, distincte de la
   rétention — elle ne juge jamais la carte en cours, la durée en cours
   est abandonnée, jamais envoyée : ni zap ni like */
function changerDeBranche() {
  if (enCours || terminee) { return; }
  var sujet = selecteur.value;
  carteActive = null;
  activation = null;
  demanderPas("/sortie?sujet=" + encodeURIComponent(sujet) + "&exclu=" + exclus());
}

var observer = new IntersectionObserver(function (entries) {
  entries.forEach(function (entry) {
    if (entry.intersectionRatio >= 0.6) { activer(entry.target); }
    else if (entry.target === carteActive) { quitter(entry.target); }
  });
}, { threshold: [0.6] });

/* chaque carte oriente le pas suivant, entre son activation et son départ */
function activer(carte) {
  carteActive = carte;
  activation = Date.now();
}

function quitter(carte) {
  var duree = Date.now() - activation;
  carteActive = null;
  pasSuivant(carte.dataset.video, duree);
}

document.getElementById("changer-branche").addEventListener("click", changerDeBranche);
cartes().forEach(function (c) { observer.observe(c); });
"""


def index_page(corpus: dict[str, Any], start: str | None = None) -> str:
    """Panneau du parcours sensible à la rétention : le feed piloté par le visionnage.

    La page embarque uniquement la carte de départ (plus le sélecteur) ;
    chaque carte suivante arrive via GET /etape?from=…&duree=…&exclu=… au
    départ de la carte précédente, à partir de la première — la durée de
    visionnage de la première carte oriente donc le premier pas. La durée
    se mesure entre l'activation et le départ de chaque carte, et le rayon
    est dérivé côté serveur (GLOSSARY, « Rétention applicative »). Le
    sélecteur des sujets canoniques du corpus figé et la commande « changer
    de branche » portent la sortie dirigée (navigation explicite : elle ne
    juge jamais la carte en cours). Aucune référence aux modes dans la page
    servie (spec #27, ticket #34).
    """
    topics = sorted({t["canonical"] for v in corpus["videos"] for t in v.get("topics", [])})
    topic_options = "\n".join(
        f'<option value="{html.escape(t)}">{html.escape(t)}</option>' for t in topics
    )
    if start is not None:
        cards = card_html(videos_by_id(corpus)[start], "point de départ")
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
.sortie button {{ margin-left: 0.5rem; }}
.panneau {{ flex: 1; overflow-y: auto; scroll-snap-type: y mandatory; background: #faf7f2; }}
.carte {{ min-height: 92%; scroll-snap-align: start; max-width: 560px; margin: 0 auto; padding: 1.5rem 1rem; border-top: 1px solid #e0d8cc; }}
.chemin {{ color: #a0642a; font-size: 0.9rem; margin: 0 0 0.5rem; }}
.titre {{ margin: 0 0 0.5rem; }}
.sujets {{ color: #555; font-size: 0.9rem; }}
.lien {{ display: inline-block; margin-top: 0.75rem; }}
.conseil {{ color: #777; font-size: 0.85rem; margin: 0.5rem 0 0; }}
.message {{ color: #a33; font-size: 0.85rem; margin: 0.25rem 0 0; }}
</style>
</head>
<body>
<header class="entete">
<h1>Video Topic Explorer</h1>
<form class="sortie" onsubmit="return false;">
<label>Sujet
<select name="sujet" id="sujet">
{topic_options}
</select>
</label>
<button type="button" id="changer-branche">Changer de branche</button>
</form>
<p class="conseil">Le temps de visionnage pilote le parcours : rester longtemps approfondit, passer vite éloigne. Changer de branche ne juge jamais la carte en cours.</p>
<p class="message" id="message"></p>
</header>
<main class="panneau" id="panneau">
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


def parcours_page(corpus: dict[str, Any], run: graph_engine.Run, start: str, rayon: int) -> str:
    """Rend la page du parcours avec le lien vers le graphe surligné à la demande."""
    from .render import build_html

    graph_href = f"/graphe.png?start={quote_plus(start)}&rayon={rayon}"
    return build_html(corpus, run.to_dict(), graph_href)


def graph_png(corpus: dict[str, Any], start: str, rayon: int | None) -> bytes:
    """Rend le graphe statique ; sous-graphe du parcours surligné si start/rayon fournis.

    Un start/rayon invalide ou isolé rend le graphe complet, sans surlignage :
    c'est exactement ce que suggère le message « affichez le graphe du corpus ».
    """
    from .render import render_graph

    run = None
    if start and rayon is not None:
        try:
            run = graph_engine.parcours(corpus, start, rayon).to_dict()
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
                self._send_html(200, index_page(corpus, panel_start(corpus)))
            elif parsed.path == "/etape":
                self._handle_etape(parse_qs(parsed.query))
            elif parsed.path == "/sortie":
                self._handle_sortie(parse_qs(parsed.query))
            elif parsed.path == "/parcours":
                self._handle_parcours(parse_qs(parsed.query))
            elif parsed.path == "/graphe.png":
                query = parse_qs(parsed.query)
                start = (query.get("start") or [""])[0]
                rayon = _parse_rayon(query)
                if rayon is _RAYON_INVALIDE:
                    rayon = None  # rayon illisible : graphe complet, sans surlignage
                self._send_png(graph_png(corpus, start, rayon))
            else:
                self._send_html(404, "<html><body><p>page inconnue</p></body></html>")

        def _handle_parcours(self, query: dict[str, list[str]]) -> None:
            start = (query.get("start") or [""])[0]
            rayon = _parse_rayon(query)
            if rayon == _RAYON_INVALIDE:
                self._send_html(400, error_page(
                    "rayon invalide : le parcours complet prend un rayon explicite "
                    "(un nombre entier >= 1, ex. rayon=3)"
                ))
                return
            try:
                run = graph_engine.parcours(corpus, start, rayon)
            except graph_engine.PathfindingError as exc:
                self._send_html(400, error_page(str(exc)))
                return
            # Un run.json par parcours lancé depuis la page, au même format que la CLI.
            graph_engine.save_run(run, Path(runs_dir) / f"{start}-r{run.radius}.json")
            self._send_html(200, parcours_page(corpus, run, start, run.radius))

        def _handle_etape(self, query: dict[str, list[str]]) -> None:
            """Pas suivant orienté par la carte quittée, servi en JSON au panneau.

            La durée de visionnage de la carte quittée pilote le rayon côté
            serveur (rétention applicative, mapping binaire) : sans durée,
            la requête est invalide — jamais de repli silencieux sur un
            autre rayon.
            """
            start = (query.get("from") or [""])[0]
            exclu = set(query.get("exclu") or [])
            duree = (query.get("duree") or [None])[0]
            if duree is None:
                self._send_json(400, {"erreur": "durée requise : le rayon du pas suivant se dérive de la durée de visionnage de la carte quittée (millisecondes entières)"})
                return
            try:
                rayon = rayon_depuis_duree(int(duree))
            except ValueError:
                self._send_json(400, {"erreur": f"durée invalide : {duree!r} (attendu : des millisecondes entières)"})
                return
            try:
                step = graph_engine.next_step(corpus, start, radius=rayon, exclude=exclu)
            except graph_engine.PathfindingError as exc:
                self._send_json(400, {"erreur": str(exc)})
                return
            if step is None:
                self._send_json(404, {"erreur": "plus aucune vidéo atteignable depuis " + start + " (exclusions ou topologie)"})
                return
            self._send_step(step)

        def _handle_sortie(self, query: dict[str, list[str]]) -> None:
            """Sortie de branche dirigée par sujet, servie en JSON au panneau.

            Point d'accès distinct du pas suivant (navigation explicite,
            jamais un jugement de la carte en cours, spec #27) : le premier
            pas depuis un sujet canonique réel du corpus figé, hors
            déjà-vues. Sujet mort ou inconnu → 400 explicite ; aucune
            candidate restante → 404 fin honnête.
            """
            sujet = (query.get("sujet") or [""])[0]
            exclu = set(query.get("exclu") or [])
            try:
                step = graph_engine.first_step(corpus, sujet, exclude=exclu)
            except graph_engine.PathfindingError as exc:
                self._send_json(400, {"erreur": str(exc)})
                return
            if step is None:
                self._send_json(404, {"erreur": "plus aucune vidéo candidate pour le sujet " + sujet + " (exclusions ou topologie)"})
                return
            self._send_step(step)

        def _send_step(self, step: dict[str, Any]) -> None:
            """Contrat JSON commun du pas : départ, arrivée, vidéo, chemin de sujets."""
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
