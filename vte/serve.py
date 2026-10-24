"""Serveur local minimal (stdlib uniquement) pour la page de parcours.

Sert la page de sélection (départ vidéo ou sujet, mode Approfondir/Découvrir),
lance les parcours via le moteur pur, écrit un run.json par parcours lancé,
affiche les motifs d'erreur (parcours partiel, départ isolé) et sert le
graphe statique surligné à la demande. Pas de framework, pas de réseau externe.
"""
from __future__ import annotations

import html
import tempfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote_plus, urlparse

from . import graph_engine


def index_page(corpus: dict[str, Any]) -> str:
    """Page de sélection du point de départ (vidéo ou sujet) et du mode."""
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
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Video Topic Explorer — parcours</title>
<style>
body {{ font-family: sans-serif; margin: 2rem; }}
label {{ display: block; margin: 0.5rem 0; }}
</style>
</head>
<body>
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
    from .render import render_graph_png

    run = None
    if start and mode:
        try:
            run = graph_engine.parcours(corpus, start, mode).to_dict()
        except graph_engine.PathfindingError:
            run = None
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "graphe.png"
        render_graph_png(corpus, run, out)
        return out.read_bytes()


def make_handler(corpus: dict[str, Any], runs_dir: Path) -> type[BaseHTTPRequestHandler]:
    """Fabrique une classe handler fermée sur le corpus figé et le répertoire des runs."""

    class PageHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._send_html(200, index_page(corpus))
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
