"""Serveur local minimal (stdlib uniquement) pour explorer le corpus vidéo.

L'accueil démarre directement sur une vidéo. Les actions d'exploration
passent par l'API HTTP et la politique d'orientation reste côté serveur.
"""
from __future__ import annotations

import html
import json
import random
import re
import tempfile
import threading
import uuid
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote_plus, urlparse

from . import graph_engine
from .corpus import videos_by_id


def direct_start(corpus: dict[str, Any]) -> str | None:
    """Vidéo d'arrivée déterministe, sans écran de choix ni chaîne précalculée.

    Préfère une vidéo qui peut ouvrir une transition liée. Si le corpus n'en
    contient aucune, il reste possible de montrer la première vidéo et de
    signaler l'épuisement au premier intérêt simulé.
    """
    from . import DEFAULT_START

    ids = {video["id"] for video in corpus["videos"]}
    if not ids:
        return None
    candidates = ([DEFAULT_START] if DEFAULT_START in ids else []) + sorted(ids)
    for candidate in candidates:
        try:
            step = graph_engine.next_step(corpus, candidate, "approfondir")
        except graph_engine.PathfindingError:
            continue
        if step is not None:
            return candidate
    return DEFAULT_START if DEFAULT_START in ids else min(ids)


def _video_payload(video: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": video["id"],
        "url": video["url"],
        "title": video["title"],
        "topics": sorted(topic["canonical"] for topic in video.get("topics", [])),
    }


def _session_payload(corpus: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": state["version"],
        "video": _video_payload(videos_by_id(corpus)[state["video_id"]]),
        "interest_point": state["interest_point"],
        "status": state["status"],
        "transition": state["transition"],
        "message": state["message"],
    }


def _random_root(
    corpus: dict[str, Any],
    current: str,
    shown: set[str],
    rejected_directions: set[str],
    used_roots: set[str],
    rng: random.Random,
) -> tuple[str, str] | None:
    """Choisit un sujet canonique qui ouvre au moins une vidéo encore inédite."""
    by_id = videos_by_id(corpus)
    current_topics = {topic["canonical"] for topic in by_id[current].get("topics", [])}
    blocked = current_topics | rejected_directions | used_roots
    dead_topics = set(corpus.get("dead_topics", ()))
    videos_by_topic: dict[str, list[str]] = {}
    for video in corpus["videos"]:
        video_id = video["id"]
        if video_id in shown or video_id == current:
            continue
        for topic in video.get("topics", []):
            canonical = topic["canonical"]
            if canonical not in blocked and canonical not in dead_topics:
                videos_by_topic.setdefault(canonical, []).append(video_id)

    roots = sorted(videos_by_topic)
    if not roots:
        return None
    root = rng.choice(roots)
    video_id = rng.choice(sorted(videos_by_topic[root]))
    return root, video_id


def _restart_or_finish(
    corpus: dict[str, Any],
    state: dict[str, Any],
    current: str,
    rejected_directions: set[str],
    rng: random.Random,
) -> None:
    restart = _random_root(
        corpus,
        current,
        state["shown"],
        rejected_directions,
        state["used_roots"],
        rng,
    )
    state["interest_point"] = None
    state["rejected_directions"] = set()
    state["consecutive_zaps"] = 0
    if restart is None:
        state["status"] = "exhausted"
        state["message"] = "Plus aucune vidéo inédite n'est disponible."
        state["transition"] = None
        return

    root_topic, next_video = restart
    state["video_id"] = next_video
    state["shown"].add(next_video)
    state["used_roots"].add(root_topic)
    state["status"] = "active"
    state["message"] = (
        "Tu as exploré les branches disponibles. "
        "On repart sur un autre arbre choisi au hasard."
    )
    state["transition"] = {
        "kind": "restart",
        "root_topic": root_topic,
        "topic_path": [],
    }


def _youtube_embed(url: str) -> str | None:
    """URL d'intégration YouTube ; None pour les liens extérieurs au lecteur."""
    for pattern in (
        r"youtube\.com/watch\?[^#]*?\bv=([\w-]+)",
        r"youtu\.be/([\w-]+)",
        r"youtube\.com/embed/([\w-]+)",
        r"youtube\.com/shorts/([\w-]+)",
    ):
        match = re.search(pattern, url)
        if match:
            return (
                f"https://www.youtube-nocookie.com/embed/{match.group(1)}"
                "?enablejsapi=1&mute=1&playsinline=1&rel=0"
            )
    return None


def _adaptive_video_html(video: dict[str, Any], transition: dict[str, Any] | None) -> str:
    embed = _youtube_embed(video.get("url", ""))
    if embed:
        player = (
            '<div class="lecteur"><iframe src="'
            + html.escape(embed, quote=True)
            + '" title="Lecteur vidéo" allow="autoplay; encrypted-media; picture-in-picture" '
            'allowfullscreen></iframe></div>'
        )
    else:
        player = (
            '<p class="lecteur lecteur-lien">Vidéo : <a href="'
            + html.escape(video.get("url", "#"), quote=True)
            + '">ouvrir le lecteur</a></p>'
        )
    if transition and transition.get("kind") == "restart":
        path_label = "Nouvelle racine : " + transition["root_topic"]
    else:
        path = (
            " → ".join(transition["topic_path"])
            if transition and transition.get("topic_path")
            else "Point de départ"
        )
        path_label = "Chemin de sujets : " + path
    topics = ", ".join(html.escape(topic["canonical"]) for topic in video.get("topics", []))
    return (
        f'<article class="carte active" data-video="{html.escape(video["id"], quote=True)}">'
        f'{player}<div class="legende"><h2 class="titre">{html.escape(video["title"])}</h2>'
        f'<p class="sujets">{topics}</p><p class="chemin">'
        f'{html.escape(path_label)}</p></div></article>'
    )


def adaptive_page(corpus: dict[str, Any], state: dict[str, Any]) -> str:
    """Rend une seule vidéo active et ses deux commandes de parcours."""
    video = videos_by_id(corpus)[state["video_id"]]
    video_html = _adaptive_video_html(video, state["transition"])
    zap_disabled = " disabled" if state["status"] != "active" else ""
    interest_disabled = " disabled" if state["status"] != "active" else ""
    message = html.escape(state["message"])
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Découvrir — Video Topic Explorer</title>
<style>
:root {{ color-scheme: dark; --fond:#10151d; --texte:#e9edf3; --discret:#97a1b2; --ligne:#45d0b8; --trait:#232c3a; }}
* {{ box-sizing: border-box; }}
html, body {{ min-height:100%; margin:0; }}
body {{ background:var(--fond); color:var(--texte); font:16px/1.45 system-ui,sans-serif; }}
.page {{ width:min(900px,100%); min-height:100dvh; margin:auto; display:flex; flex-direction:column; padding:0 1rem 1.25rem; }}
.barre {{ height:3.5rem; display:flex; align-items:center; border-bottom:1px solid var(--trait); color:var(--discret); font-size:.85rem; font-weight:700; }}
.video {{ flex:1; display:flex; flex-direction:column; justify-content:center; }}
.carte {{ display:flex; flex-direction:column; }}
.lecteur {{ position:relative; width:100%; aspect-ratio:16/9; background:#000; border-radius:12px; overflow:hidden; }}
.lecteur iframe {{ position:absolute; inset:0; width:100%; height:100%; border:0; }}
.lecteur-lien {{ padding:1rem; }}
.legende {{ padding:.9rem .15rem; }}
.titre {{ margin:0; font-size:1.2rem; }}
.sujets,.chemin {{ color:var(--discret); font-size:.9rem; margin:.4rem 0 0; }}
.chemin {{ color:var(--ligne); }}
.actions {{ display:flex; flex-wrap:wrap; gap:.65rem; margin-top:.25rem; }}
.action {{ border:1px solid var(--trait); border-radius:999px; padding:.65rem 1rem; background:transparent; color:var(--texte); font:inherit; font-weight:650; cursor:pointer; }}
.action.principal {{ background:var(--ligne); border-color:transparent; color:#0c2019; }}
.action:disabled {{ cursor:not-allowed; opacity:.48; }}
.message {{ min-height:1.5em; margin:.75rem 0 0; color:var(--discret); }}
.message.erreur {{ color:#ff9b9b; }}
:focus-visible {{ outline:2px solid var(--ligne); outline-offset:3px; }}
@media (min-width:720px) {{ .page {{ width:min(1100px,94vw); }} .video {{ width:min(100%,980px); margin:auto; }} .titre {{ font-size:1.45rem; }} }}
</style>
</head>
<body>
<div class="page">
<header class="barre">Video Topic Explorer</header>
<main class="video" id="parcours" data-video-id="{html.escape(video['id'], quote=True)}" data-version="{state['version']}">
{video_html}
<div class="actions" aria-label="Actions de parcours">
<button class="action principal" type="button" data-action="interest"{interest_disabled}>Simuler un visionnage long</button>
<button class="action" type="button" data-action="zap"{zap_disabled}>Zapper</button>
</div>
<p class="message" id="message" aria-live="polite">{message}</p>
</main>
</div>
<script>
(function () {{
  "use strict";
  var root = document.getElementById("parcours");
  var buttons = Array.prototype.slice.call(root.querySelectorAll("button[data-action]"));
  var interest = root.querySelector('[data-action="interest"]');
  var message = document.getElementById("message");
  var version = Number(root.dataset.version);
  var enCours = false;
  var termine = interest.disabled;

  function afficherErreur(texte) {{
    message.textContent = texte;
    message.classList.add("erreur");
  }}
  function embedUrl(url) {{
    var match = url.match(/(?:youtube\\.com\\/(?:watch\\?[^#]*?v=|embed\\/|shorts\\/)|youtu\\.be\\/)([\\w-]+)/);
    return match ? "https://www.youtube-nocookie.com/embed/" + match[1] + "?enablejsapi=1&mute=1&playsinline=1&rel=0" : null;
  }}
  function afficher(data) {{
    var video = data.video;
    if (data.status === "exhausted") {{
      root.dataset.version = String(data.version);
      version = data.version;
      termine = true;
      buttons.forEach(function (button) {{ button.disabled = true; }});
      message.classList.remove("erreur");
      message.textContent = data.message || "Plus aucune vidéo liée n'est disponible dans cette branche.";
      return;
    }}
    var card = document.createElement("article");
    card.className = "carte active";
    card.dataset.video = video.id;
    var embed = embedUrl(video.url);
    if (embed) {{
      var player = document.createElement("div");
      player.className = "lecteur";
      var iframe = document.createElement("iframe");
      iframe.src = embed;
      iframe.title = "Lecteur vidéo";
      iframe.allow = "autoplay; encrypted-media; picture-in-picture";
      iframe.allowFullscreen = true;
      player.appendChild(iframe);
      card.appendChild(player);
    }} else {{
      var link = document.createElement("a");
      link.className = "lecteur lecteur-lien";
      link.href = video.url;
      link.textContent = "Ouvrir la vidéo : " + video.title;
      card.appendChild(link);
    }}
    var legend = document.createElement("div");
    legend.className = "legende";
    var title = document.createElement("h2");
    title.className = "titre";
    title.textContent = video.title;
    var topics = document.createElement("p");
    topics.className = "sujets";
    topics.textContent = video.topics.join(", ");
    var path = document.createElement("p");
    path.className = "chemin";
    if (data.transition && data.transition.kind === "restart") {{
      path.textContent = "Nouvelle racine : " + data.transition.root_topic;
    }} else {{
      path.textContent = "Chemin de sujets : " + (data.transition ? data.transition.topic_path.join(" → ") : "Point de départ");
    }}
    legend.appendChild(title); legend.appendChild(topics); legend.appendChild(path);
    card.appendChild(legend);
    var old = root.querySelector(".carte");
    if (old) {{ old.replaceWith(card); }} else {{ root.prepend(card); }}
    root.dataset.videoId = video.id;
    root.dataset.version = String(data.version);
    version = data.version;
    message.classList.remove("erreur");
    message.textContent = data.message || "";
    termine = data.status !== "active";
    buttons.forEach(function (item) {{ item.disabled = termine; }});
  }}
  root.addEventListener("click", function (event) {{
    var button = event.target.closest("button[data-action]");
    if (!button || enCours || termine) return;
    enCours = true;
    buttons.forEach(function (item) {{ item.disabled = true; }});
    message.classList.remove("erreur");
    message.textContent = "Chargement de la prochaine vidéo…";
    fetch("/action", {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      credentials: "same-origin",
      body: JSON.stringify({{ action: button.dataset.action, version: version }})
    }}).then(function (response) {{
      return response.json().then(function (data) {{
        if (response.status === 409 && data.video) return data;
        if (!response.ok) throw new Error(data.erreur || "La prochaine vidéo n'a pas pu être chargée.");
        return data;
      }});
    }}).then(afficher).catch(function () {{
      afficherErreur("Impossible de charger la prochaine vidéo. Réessaie.");
      buttons.forEach(function (item) {{ item.disabled = termine; }});
    }}).finally(function () {{
      enCours = false;
    }});
  }});
}})();
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
<p><a href="/">← retour au parcours</a></p>
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


def make_handler(
    corpus: dict[str, Any], runs_dir: Path, rng: random.Random | None = None
) -> type[BaseHTTPRequestHandler]:
    """Fabrique un handler lié au corpus et à l'état éphémère des sessions."""
    sessions: dict[str, dict[str, Any]] = {}
    sessions_lock = threading.Lock()
    random_source = rng if rng is not None else random.Random()

    def new_session() -> tuple[str, dict[str, Any]] | None:
        start = direct_start(corpus)
        if start is None:
            return None
        session_id = uuid.uuid4().hex
        state = {
            "video_id": start,
            "interest_point": None,
            "shown": {start},
            "version": 0,
            "status": "active",
            "transition": None,
            "rejected_directions": set(),
            "used_roots": set(),
            "consecutive_zaps": 0,
            "message": "",
        }
        with sessions_lock:
            sessions[session_id] = state
        return session_id, state

    class PageHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                session_id = self._request_session_id()
                with sessions_lock:
                    state = sessions.get(session_id or "")
                cookie_header = None
                if state is None:
                    created = new_session()
                    if created is None:
                        self._send_html(503, error_page("Aucune vidéo ne se trouve dans le corpus."))
                        return
                    session_id, state = created
                    cookie_header = (
                        "parcours_session=" + session_id + "; Path=/; HttpOnly; SameSite=Lax"
                    )
                with sessions_lock:
                    doc = adaptive_page(corpus, state)
                extra_headers = [("Cache-Control", "no-store")]
                if cookie_header:
                    extra_headers.append(("Set-Cookie", cookie_header))
                self._send_html(200, doc, extra_headers=extra_headers)
            elif parsed.path == "/session":
                session_id = self._request_session_id()
                with sessions_lock:
                    state = sessions.get(session_id or "")
                    payload = _session_payload(corpus, state) if state else None
                if payload is None:
                    self._send_json(401, {"erreur": "session absente ou expirée"})
                    return
                self._send_json(200, payload)
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

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path != "/action":
                self._send_json(404, {"erreur": "page inconnue"})
                return
            session_id = self._request_session_id()
            try:
                content_length = int(self.headers.get("Content-Length", "0"))
                if content_length < 1 or content_length > 4096:
                    raise ValueError
                payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
                self._send_json(400, {"erreur": "requête JSON invalide"})
                return

            action = payload.get("action")
            version = payload.get("version")
            if action not in {"interest", "zap"}:
                self._send_json(400, {"erreur": "action inconnue (attendu : interest ou zap)"})
                return
            if not isinstance(version, int) or isinstance(version, bool):
                self._send_json(400, {"erreur": "version de session invalide"})
                return

            result_code = 200
            with sessions_lock:
                state = sessions.get(session_id or "")
                if state is None:
                    result_code = 401
                    result = {"erreur": "session absente ou expirée"}
                elif version != state["version"]:
                    result_code = 409
                    result = _session_payload(corpus, state)
                    result["erreur"] = "cette action a déjà été traitée"
                elif state["status"] != "active":
                    result_code = 409
                    result = _session_payload(corpus, state)
                    result["erreur"] = "cette session a terminé son exploration locale"
                else:
                    current = state["video_id"]
                    rejected = set(state["rejected_directions"])
                    interest_point = current if action == "interest" else None
                    consecutive_zaps = (
                        0 if action == "interest" else state["consecutive_zaps"] + 1
                    )
                    try:
                        if action == "interest":
                            rejected.clear()
                            step = graph_engine.next_step(
                                corpus, current, "approfondir", exclude=state["shown"]
                            )
                        else:
                            previous_transition = state["transition"]
                            if previous_transition and previous_transition.get("topic_path"):
                                direction = previous_transition["topic_path"][-1]
                            else:
                                natural = graph_engine.next_step(
                                    corpus,
                                    current,
                                    "approfondir",
                                    exclude=state["shown"],
                                    exclude_directions=rejected,
                                )
                                direction = natural["topic_path"][0] if natural else None
                            if direction:
                                rejected.add(direction)
                            step = graph_engine.next_step(
                                corpus,
                                current,
                                "approfondir",
                                exclude=state["shown"],
                                exclude_directions=rejected,
                                # Les zaps élargissent jusqu'au rayon Découvrir.
                                # Au-delà, le parcours reprend à une autre racine.
                                radius=min(
                                    graph_engine.MODE_RADIUS[graph_engine.Mode.APPROFONDIR]
                                    + consecutive_zaps
                                    - 1,
                                    graph_engine.MODE_RADIUS[graph_engine.Mode.DECOUVRIR],
                                ),
                            )
                    except graph_engine.PathfindingError as exc:
                        current_video = videos_by_id(corpus).get(current)
                        alive_topics = set()
                        if current_video is not None:
                            alive_topics = {
                                topic["canonical"] for topic in current_video.get("topics", [])
                            } - set(corpus.get("dead_topics", ()))
                        if not alive_topics and current_video is not None:
                            state["version"] += 1
                            _restart_or_finish(
                                corpus, state, current, rejected, random_source
                            )
                            result = _session_payload(corpus, state)
                        else:
                            result_code = 400
                            result = {"erreur": str(exc)}
                    else:
                        state["interest_point"] = interest_point
                        state["rejected_directions"] = rejected
                        state["consecutive_zaps"] = consecutive_zaps
                        state["version"] += 1
                        if step is None:
                            _restart_or_finish(
                                corpus, state, current, rejected, random_source
                            )
                        else:
                            state["video_id"] = step["to"]
                            state["shown"].add(step["to"])
                            state["transition"] = {
                                "kind": "linked",
                                "from": step["from"],
                                "to": step["to"],
                                "topic_path": list(step["topic_path"]),
                                "explanation": step["explanation"],
                            }
                            state["message"] = ""
                        result = _session_payload(corpus, state)
            self._send_json(result_code, result)

        def _request_session_id(self) -> str | None:
            cookie = SimpleCookie()
            try:
                cookie.load(self.headers.get("Cookie", ""))
            except CookieError:
                return None
            morsel = cookie.get("parcours_session")
            return morsel.value if morsel else None

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
            """Pas suivant orienté par la vidéo regardée, servi en JSON au panneau."""
            start = (query.get("from") or [""])[0]
            mode = (query.get("mode") or ["decouvrir"])[0]
            exclu = set(query.get("exclu") or [])
            try:
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
            self._send_bytes(
                code, "application/json; charset=utf-8", body,
                extra_headers=[("Cache-Control", "no-store")],
            )

        def _send_html(
            self, code: int, doc: str, *, extra_headers: list[tuple[str, str]] | None = None
        ) -> None:
            self._send_bytes(
                code, "text/html; charset=utf-8", doc.encode("utf-8"), extra_headers=extra_headers
            )

        def _send_png(self, data: bytes) -> None:
            self._send_bytes(200, "image/png", data)

        def _send_bytes(
            self,
            code: int,
            content_type: str,
            body: bytes,
            *,
            extra_headers: list[tuple[str, str]] | None = None,
        ) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            for name, value in extra_headers or []:
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: Any) -> None:
            pass

    return PageHandler


def make_server(
    corpus: dict[str, Any],
    runs_dir: Path,
    host: str = "127.0.0.1",
    port: int = 8000,
    *,
    rng: random.Random | None = None,
) -> HTTPServer:
    return HTTPServer((host, port), make_handler(corpus, Path(runs_dir), rng=rng))


def serve_forever(
    corpus: dict[str, Any], runs_dir: Path, host: str = "127.0.0.1", port: int = 8000
) -> None:
    """Lance le serveur (bloquant) : le parcours direct est sur http://host:port/."""
    httpd = make_server(corpus, Path(runs_dir), host=host, port=port)
    print(f"parcours : http://{host}:{port}/ (Ctrl-C pour arrêter)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
