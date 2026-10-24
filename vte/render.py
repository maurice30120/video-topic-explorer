"""Rendus : page HTML minimale et graphe statique (PNG/SVG) avec sous-graphe surligné."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

from .graph_engine import Mode, build_graph


def build_html(corpus: dict[str, Any], run: dict[str, Any], graph_href: str | None = None) -> str:
    """Construit la page HTML du parcours et la renvoie en chaîne."""
    by_id = {video["id"]: video for video in corpus["videos"]}
    topic_videos: dict[str, list[str]] = {}
    for video in corpus["videos"]:
        for topic in video.get("topics", []):
            topic_videos.setdefault(topic["canonical"], []).append(video["id"])

    items = []
    for index, video_id in enumerate(run["videos"]):
        video = by_id[video_id]
        transition = next((t for t in run["transitions"] if t["to"] == video_id), None)
        path_html = ""
        if transition:
            chain_html = " → ".join(
                f'<a href="#topic-{html.escape(t)}" title="voir les vidéos portant ce sujet">{html.escape(t)}</a>'
                for t in transition["topic_path"]
            )
            path_html = f"<p class='transition'>chemin de sujets : {chain_html}</p>"
        items.append(
            "<li>"
            f"<a href='{html.escape(video.get('url', '#'))}'>{html.escape(video['title'])}</a> "
            f"<span class='vid'>({html.escape(video_id)})</span>"
            f"{path_html}"
            "</li>"
        )

    reason_html = ""
    if not run["complete"] and run.get("reason"):
        reason_html = f"<p class='reason'>{html.escape(run['reason'])}</p>"

    graph_html = ""
    if graph_href:
        graph_html = (
            '<p class="graph-link"><a href="' + html.escape(graph_href) + '">'
            "afficher le graphe du corpus avec le sous-graphe du parcours surligné</a></p>"
        )

    topic_anchors = "\n".join(
        f'<div id="topic-{html.escape(t)}"><strong>{html.escape(t)}</strong> : '
        + ", ".join(topic_videos.get(t, []))
        + "</div>"
        for t in sorted(topic_videos)
    )

    doc = f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Parcours — {html.escape(run['start'])} ({html.escape(run['mode'])})</title>
<style>
body {{ font-family: sans-serif; margin: 2rem; }}
.transition {{ color: #555; margin-left: 1rem; }}
.vid {{ color: #888; font-size: 0.85em; }}
.reason {{ color: #a33; }}
.graph-link {{ margin: 1rem 0; }}
ol li {{ margin: 0.75rem 0; }}
#topics {{ margin-top: 2rem; border-top: 1px solid #ccc; padding-top: 1rem; }}
</style>
</head>
<body>
<h1>Parcours depuis {html.escape(run['start'])}</h1>
<p>mode : <strong>{html.escape(run['mode'])}</strong> — rayon : {run['radius']} hop(s)</p>
<ol>
{chr(10).join(items)}
</ol>
{reason_html}
{graph_html}
<div id="topics">
<h2>Sujets du corpus et leurs vidéos</h2>
{topic_anchors}
</div>
</body>
</html>
"""
    return doc


def render_html(
    corpus: dict[str, Any], run: dict[str, Any], out: Path, graph_href: str | None = None
) -> None:
    """Sauvegarde la page HTML du parcours (voir build_html pour la chaîne)."""
    doc = build_html(corpus, run, graph_href)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc, encoding="utf-8")


def render_graph(corpus: dict[str, Any], run: dict[str, Any] | None, out: Path) -> None:
    """Rend le graphe statique du corpus, en PNG ou SVG selon l'extension du fichier demandé.

    Un seul moteur de rendu dessine les deux formats : même layout (spring_layout
    seedé), même surlignage du sous-graphe du parcours.
    """
    fmt = out.suffix.lower().lstrip(".")
    if fmt not in {"png", "svg"}:
        raise ValueError(f"format de graphe non supporté : {out.suffix!r} (choisir .png ou .svg)")

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import networkx as nx

    graph = build_graph(corpus)
    highlighted: set[str] = set()
    if run:
        highlighted = {f"video:{v}" for v in run["videos"]}
        for transition in run.get("transitions", []):
            for topic in transition.get("topic_path", []):
                highlighted.add(f"topic:{topic}")

    pos = nx.spring_layout(graph, seed=42)
    plt.figure(figsize=(14, 10))
    normal_nodes = [n for n in graph if n not in highlighted]
    nx.draw_networkx_edges(graph, pos, alpha=0.2)
    nx.draw_networkx_nodes(
        graph, pos, nodelist=[n for n in normal_nodes if n.startswith("video:")],
        node_shape="s", node_color="#9ecae1", node_size=120,
    )
    nx.draw_networkx_nodes(
        graph, pos, nodelist=[n for n in normal_nodes if n.startswith("topic:")],
        node_shape="o", node_color="#fdd0a2", node_size=160,
    )
    nx.draw_networkx_nodes(
        graph, pos, nodelist=[n for n in highlighted if n.startswith("video:")],
        node_shape="s", node_color="#2171b5", node_size=260,
    )
    nx.draw_networkx_nodes(
        graph, pos, nodelist=[n for n in highlighted if n.startswith("topic:")],
        node_shape="o", node_color="#e6550d", node_size=360,
    )
    labels = {n: graph.nodes[n].get("label", n.removeprefix("topic:")) for n in graph if n in highlighted}
    nx.draw_networkx_labels(graph, pos, labels=labels, font_size=7)
    plt.axis("off")
    plt.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out, dpi=150)
    plt.close()

# ------------------------------------------------------------------ feed vertical

DEFAULT_FEED_MODE = Mode.DECOUVRIR
"""Mode actif au chargement du feed (le mode du parcours publié par défaut)."""


def _as_mode(value: str | Mode) -> Mode:
    """Convertit une valeur en Mode ; erreur française explicite si le mode est inconnu."""
    try:
        return Mode(value)
    except ValueError:
        supported = ", ".join(member.value for member in Mode)
        raise ValueError(
            f"mode de parcours inconnu : {value!r} (modes supportés : {supported})"
        ) from None


class _ModeLabels(dict):
    """Labels visibles indexés par Mode : un mode inconnu lève une erreur
    française explicite (pas de KeyError brut), par membre comme par valeur."""

    def __getitem__(self, key):
        return super().__getitem__(_as_mode(key))

    def __missing__(self, mode):
        raise ValueError(f"aucun label défini pour le mode de parcours {mode.value!r}")


MODE_LABELS = _ModeLabels({Mode.DECOUVRIR: "Découvrir", Mode.APPROFONDIR: "Approfondir"})
MODE_SWITCH_LABELS = _ModeLabels({
    Mode.DECOUVRIR: "Basculer en Approfondir",
    Mode.APPROFONDIR: "Basculer en Découvrir",
})
_FEED_MODES = tuple(Mode)


def _embed_url(url: str) -> str | None:
    """URL d'intégration (youtube-nocookie) d'une vidéo YouTube, sinon None."""
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


def _player_html(video: dict[str, Any]) -> str:
    """Lecteur intégré de la vidéo (iframe), ou lien de repli si hors YouTube."""
    embed = _embed_url(video.get("url", ""))
    if embed is None:
        return (
            f'<p class="lecteur lecteur-lien">Vidéo hors YouTube : '
            f'<a href="{html.escape(video.get("url", "#"), quote=True)}">'
            f"{html.escape(video['title'])}</a></p>"
        )
    return (
        '<div class="lecteur">'
        f'<iframe src="{html.escape(embed, quote=True)}" '
        'title="lecteur intégré" allow="autoplay; encrypted-media; picture-in-picture" '
        "allowfullscreen loading=\"lazy\"></iframe>"
        "</div>"
    )


def _stations_html(topic_path: list[str]) -> str:
    """Ligne de sujets de la transition : une pastille par sujet, reliées."""
    stations = "".join(
        f'<span class="station"><span class="pastille"></span>'
        f'<span class="nom">{html.escape(topic)}</span></span>'
        for topic in topic_path
    )
    return f'<div class="ligne-sujets">{stations}</div>'


def _card_html(
    by_id: dict[str, dict],
    video_id: str,
    transition: dict[str, Any] | None,
    departure: bool,
) -> str:
    video = by_id[video_id]
    channel_html = ""
    if video.get("channel"):
        channel_html = f'<p class="chaine">{html.escape(video["channel"])}</p>'
    if transition and transition.get("topic_path"):
        path_attr = html.escape("|".join(transition["topic_path"]), quote=True)
        path_html = (
            f'<div class="chemin" data-sujets="{path_attr}">'
            + _stations_html(transition["topic_path"])
            + "</div>"
        )
    elif departure:
        path_html = (
            '<div class="chemin"><div class="ligne-sujets">'
            '<span class="station depart"><span class="pastille"></span>'
            '<span class="nom">Départ</span></span></div></div>'
            '<p class="indice">Un appui sur la vidéo active le son.</p>'
        )
    else:
        path_html = ""
    return (
        f'<article class="carte{" depart" if departure else ""}" '
        f'data-video="{html.escape(video_id, quote=True)}">'
        f"{_player_html(video)}"
        '<div class="legende">'
        f'<h2 class="titre">{html.escape(video["title"])}</h2>'
        f"{channel_html}"
        f"{path_html}"
        "</div>"
        "</article>"
    )


def _end_card_html(run: dict[str, Any], mode: str) -> str:
    """Carte de fin : raison d'arrêt du moteur, rejouer, basculer de mode."""
    if run["complete"]:
        reason = f"Parcours complet : {len(run['videos'])} vidéos."
    else:
        reason = run.get("reason") or "Parcours interrompu."
    other_mode = next(member.value for member in Mode if member.value != mode)
    switch_html = (
        f'<button class="action basculer" data-mode-vers="{other_mode}" type="button">'
        f"{MODE_SWITCH_LABELS[mode]}</button>"
    )
    return (
        '<article class="carte fin">'
        '<div class="fin-contenu">'
        '<h2 class="titre">Fin du parcours</h2>'
        f'<p class="raison">{html.escape(reason)}</p>'
        '<div class="actions">'
        '<button class="action rejouer" type="button">Revoir le parcours</button>'
        f"{switch_html}"
        "</div>"
        "</div>"
        "</article>"
    )


def _parcours_html(
    by_id: dict[str, dict],
    run: dict[str, Any],
    mode: str,
    active: bool,
) -> str:
    cards = []
    for index, video_id in enumerate(run["videos"]):
        transition = next((t for t in run["transitions"] if t["to"] == video_id), None)
        cards.append(_card_html(by_id, video_id, transition, index == 0))
    cards.append(_end_card_html(run, mode))
    return (
        f'<section class="parcours" data-mode="{html.escape(mode, quote=True)}"'
        + ("" if active else " hidden")
        + ">"
        + "".join(cards)
        + "</section>"
    )


_FEED_CSS = """
:root {
  --encre: #10151d;
  --trait: #232c3a;
  --texte: #e9edf3;
  --discret: #97a1b2;
  --ligne: #45d0b8;
  --ligne-ambre: #e8a33d;
  --sur-ligne: #0c2019;
}
* { box-sizing: border-box; }
html, body { height: 100%; }
body {
  margin: 0;
  display: grid;
  place-items: center;
  background: var(--encre);
  color: var(--texte);
  font-family: "Overpass", "Avenir Next", "Segoe UI", system-ui, sans-serif;
  line-height: 1.45;
}
body[data-mode="approfondir"] { --ligne: var(--ligne-ambre); --sur-ligne: #241a0b; }

.page {
  width: min(480px, 100%);
  height: 100dvh;
  display: flex;
  flex-direction: column;
  --hauteur-barre: 56px;
}

.barre {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  height: var(--hauteur-barre);
  padding: 0 1rem;
  border-bottom: 1px solid var(--trait);
  background: rgba(16, 21, 29, 0.94);
}
.marque { margin: 0; font-size: 0.78rem; font-weight: 800; color: var(--discret); }
.modes {
  display: flex;
  gap: 0.2rem;
  margin-left: auto;
  padding: 0.18rem;
  border: 1px solid var(--trait);
  border-radius: 999px;
}
.mode {
  border: 0;
  padding: 0.32rem 0.85rem;
  border-radius: 999px;
  font: inherit;
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--discret);
  background: transparent;
  cursor: pointer;
}
.mode[aria-pressed="true"] { background: var(--ligne); color: var(--sur-ligne); }
.graphe { font-size: 0.78rem; color: var(--discret); text-decoration: none; }
.graphe:hover { color: var(--texte); }

.feed {
  flex: 1;
  overflow-y: auto;
  overscroll-behavior: contain;
  scroll-snap-type: y mandatory;
  scroll-behavior: smooth;
}
.carte {
  min-height: calc(100dvh - var(--hauteur-barre, 56px));
  scroll-snap-align: start;
  scroll-snap-stop: always;
  display: flex;
  flex-direction: column;
  padding: 0 1rem;
  padding-bottom: calc(1rem + env(safe-area-inset-bottom));
}
.lecteur {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  margin-top: 1rem;
  border-radius: 10px;
  overflow: hidden;
  background: #000;
}
.lecteur iframe { position: absolute; inset: 0; width: 100%; height: 100%; border: 0; }
.lecteur::after { content: ""; position: absolute; inset: 0; }
.lecteur-lien { margin-top: 1rem; padding: 1rem; color: var(--discret); }
.legende { padding: 0.85rem 0.2rem 0; }
.titre { margin: 0; font-size: 1.12rem; font-weight: 800; line-height: 1.28; }
.chaine { margin: 0.2rem 0 0; font-size: 0.82rem; color: var(--discret); }

.chemin { margin-top: 0.75rem; overflow-x: auto; }
.ligne-sujets { display: flex; width: max-content; min-width: 100%; }
.station {
  position: relative;
  flex: 1;
  min-width: 4.6rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.28rem;
}
.station:not(:last-child)::after {
  content: "";
  position: absolute;
  top: 5px;
  left: calc(50% + 9px);
  width: calc(100% - 18px);
  height: 2px;
  background: var(--ligne);
  opacity: 0.55;
}
.pastille {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--ligne);
  box-shadow: 0 0 0 4px rgba(255, 255, 255, 0.05);
}
.station.depart .pastille {
  width: 10px;
  height: 10px;
  background: transparent;
  border: 2px solid var(--ligne);
  box-shadow: none;
}
.station .nom {
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--discret);
  white-space: nowrap;
}
.indice { margin: 0.9rem 0 0; font-size: 0.75rem; color: var(--discret); }

.carte.fin { justify-content: center; }
.fin-contenu { max-width: 26rem; padding: 0 0.4rem; }
.carte.fin .titre { font-size: 1.5rem; }
.raison { margin: 0.4rem 0 0; color: var(--discret); }
.actions { display: flex; flex-wrap: wrap; gap: 0.55rem; margin-top: 1.3rem; }
.action {
  font: inherit;
  font-size: 0.9rem;
  font-weight: 600;
  padding: 0.55rem 1.05rem;
  border-radius: 999px;
  border: 1px solid var(--trait);
  background: transparent;
  color: var(--texte);
  cursor: pointer;
}
.action.rejouer { background: var(--ligne); border-color: transparent; color: var(--sur-ligne); }

:focus-visible { outline: 2px solid var(--ligne); outline-offset: 2px; }
:focus:not(:focus-visible) { outline: none; }

@media (prefers-reduced-motion: reduce) {
  .feed { scroll-behavior: auto; }
}
"""

_FEED_JS = """
(function () {
  "use strict";
  var feed = document.getElementById("feed");
  if (!feed) { return; }
  var body = document.body;
  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
  var toggles = Array.prototype.slice.call(document.querySelectorAll(".mode"));
  var sections = Array.prototype.slice.call(feed.querySelectorAll(".parcours"));

  /* Commandes au lecteur : en file d'attente jusqu'à son onReady (API iframe
     YouTube) — une commande envoyée avant la mise en place est ignorée par lui. */
  var readyPlayers = [];
  var pending = new Map();

  function post(iframe, func) {
    if (readyPlayers.indexOf(iframe) === -1) {
      if (!pending.has(iframe)) { pending.set(iframe, []); }
      pending.get(iframe).push(func);
      return;
    }
    iframe.contentWindow.postMessage(
      JSON.stringify({ event: "command", func: func, args: [] }), "*");
  }
  function playerFor(source) {
    var frames = document.querySelectorAll("iframe");
    for (var i = 0; i < frames.length; i += 1) {
      if (frames[i].contentWindow === source) { return frames[i]; }
    }
    return null;
  }
  window.addEventListener("message", function (event) {
    var player = playerFor(event.source);
    if (!player) { return; }
    var data;
    try { data = JSON.parse(event.data); } catch (err) { return; }
    if (data.event !== "onReady") { return; }
    readyPlayers.push(player);
    if (pending.has(player)) {
      pending.get(player).forEach(function (func) { post(player, func); });
      pending.delete(player);
    }
  });
  function players(section) {
    return Array.prototype.slice.call(section.querySelectorAll("iframe"));
  }
  function pauseSection(section) {
    players(section).forEach(function (iframe) { post(iframe, "pauseVideo"); });
  }

  var activeCard = null;
  function setActive(card) {
    if (activeCard === card) { return; }
    if (activeCard) {
      var previous = activeCard.querySelector("iframe");
      if (previous) { post(previous, "pauseVideo"); }
      activeCard.classList.remove("active");
    }
    activeCard = card;
    card.classList.add("active");
    var iframe = card.querySelector("iframe");
    if (iframe) {
      post(iframe, "playVideo");
      post(iframe, card.dataset.son === "1" ? "unMute" : "mute");
    }
  }

  function sectionOf(mode) {
    for (var i = 0; i < sections.length; i += 1) {
      if (sections[i].dataset.mode === mode) { return sections[i]; }
    }
    return null;
  }
  function showMode(mode) {
    var target = sectionOf(mode);
    if (!target) { return; }
    sections.forEach(function (section) {
      section.hidden = section.dataset.mode !== mode;
      if (section.hidden) { pauseSection(section); }
    });
    toggles.forEach(function (button) {
      button.setAttribute("aria-pressed", String(button.dataset.mode === mode));
    });
    body.dataset.mode = mode;
    feed.scrollTo({ top: 0, behavior: reduced.matches ? "auto" : "smooth" });
    setActive(target.querySelector(".carte"));
  }

  toggles.forEach(function (button) {
    button.addEventListener("click", function () { showMode(button.dataset.mode); });
  });
  Array.prototype.slice.call(document.querySelectorAll(".basculer")).forEach(function (button) {
    button.addEventListener("click", function () { showMode(button.dataset.modeVers); });
  });
  Array.prototype.slice.call(document.querySelectorAll(".rejouer")).forEach(function (button) {
    button.addEventListener("click", function () {
      var first = button.closest(".parcours").querySelector(".carte");
      first.scrollIntoView({ behavior: reduced.matches ? "auto" : "smooth" });
      setActive(first);
    });
  });

  /* un appui sur le lecteur active ou coupe le son ; activer le son
     démarre aussi la lecture (un lecteur jamais démarré ne doit pas
     juste être démueté) */
  feed.addEventListener("click", function (event) {
    var lecteur = event.target.closest(".lecteur");
    if (!lecteur) { return; }
    var card = lecteur.closest(".carte");
    var iframe = card.querySelector("iframe");
    if (!iframe) { return; }
    var avecSon = card.dataset.son === "1";
    card.dataset.son = avecSon ? "0" : "1";
    if (avecSon) {
      post(iframe, "mute");
    } else {
      post(iframe, "unMute");
      post(iframe, "playVideo");
    }
  });

  /* la carte visible joue (muette), les autres se mettent en pause */
  if ("IntersectionObserver" in window) {
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.intersectionRatio >= 0.55 &&
            !entry.target.closest(".parcours").hidden) {
          setActive(entry.target);
        }
      });
    }, { threshold: [0.55] });
    Array.prototype.slice.call(feed.querySelectorAll(".carte")).forEach(function (card) {
      observer.observe(card);
    });
  } else {
    var visible = feed.querySelector(".parcours:not([hidden]) .carte");
    if (visible) { setActive(visible); }
  }
})();
"""


def build_feed_html(
    corpus: dict[str, Any],
    runs: dict[str, dict[str, Any]],
    graph_href: str | None = None,
    default_mode: str | Mode = DEFAULT_FEED_MODE,
) -> str:
    """Construit la page unique du feed vertical (les deux modes embarqués) et la renvoie.

    Les parcours des deux modes sont rendus côté serveur et embarqués : le
    basculeur ne fait que changer la section visible, sans rechargement ni
    réimplémentation du moteur en JavaScript.
    """
    from .corpus import videos_by_id

    by_id = videos_by_id(corpus)
    missing = [member.value for member in _FEED_MODES if member.value not in runs]
    if missing:
        raise ValueError(
            "le feed exige les parcours des deux modes ; manquant : " + ", ".join(missing)
        )
    modes = [member.value for member in _FEED_MODES]
    default_mode = _as_mode(default_mode).value
    toggles = "".join(
        f'<button class="mode" data-mode="{mode}" '
        f'aria-pressed="{"true" if mode == default_mode else "false"}" type="button">'
        f"{MODE_LABELS[mode]}</button>"
        for mode in modes
    )
    sections = "\n".join(
        _parcours_html(by_id, runs[mode], mode, mode == default_mode)
        for mode in modes
    )
    graph_html = ""
    if graph_href:
        graph_html = f'<a class="graphe" href="{html.escape(graph_href, quote=True)}">Graphe</a>'
    doc = f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Parcours — Video Topic Explorer</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Overpass:wght@400;600;800&amp;display=swap" rel="stylesheet">
<style>{_FEED_CSS}</style>
</head>
<body data-mode="{html.escape(default_mode, quote=True)}">
<div class="page">
<header class="barre">
<p class="marque">Video Topic Explorer</p>
<nav class="modes" aria-label="Mode du parcours">
{toggles}
</nav>
{graph_html}
</header>
<main class="feed" id="feed">
{sections}
</main>
</div>
<script>{_FEED_JS}</script>
</body>
</html>
"""
    return doc


def render_feed_html(
    corpus: dict[str, Any],
    runs: dict[str, dict[str, Any]],
    out: Path,
    graph_href: str | None = None,
    default_mode: str | Mode = DEFAULT_FEED_MODE,
) -> None:
    """Sauvegarde la page du feed (voir build_feed_html pour la chaîne)."""
    doc = build_feed_html(corpus, runs, graph_href, default_mode)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc, encoding="utf-8")
