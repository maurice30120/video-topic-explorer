"""CLI du MVP : ingestion manuelle, extraction Gemini (cachée), parcours, rendu HTML, graphe.

Utilisation :
    python -m vte ingest data/videos_raw.json
    python -m vte extract data/videos_raw.json data/corpus.json
    python -m vte run data/corpus.json --start vid-001 --mode decouvrir
    python -m vte render data/corpus.json --run data/runs/<fichier>.json --out out/parcours.html
    python -m vte.cli feed data/corpus.json --start vid-001 --out out/site/index.html
    python -m vte graph data/corpus.json --run data/runs/<fichier>.json --out out/graphe.png (ou .svg)
    python -m vte stats data/corpus.json
    python -m vte serve data/corpus.json --port 8000
    python -m vte.cli smoke --site out/site --first-video ghnY4S8unMM (ou --url https://…)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from . import graph_engine
from .corpus import CorpusError, canonical, load_corpus

EXTRACTION_PROMPT = (
    "Pour la vidéo suivante, extrais 3 à 5 sujets pertinents, sous forme de liste JSON "
    'd\'objets {{"raw": "<libellé>", "justification": "<courte justification fondée sur les données>"}}. '
    "Réponds uniquement avec le JSON, sans texte autour.\n\n"
    "Titre : {title}\nDescription : {description}\nTranscription : {transcript}"
)


def _model_version(response: Any, fallback: str) -> str:
    """Version réelle du modèle rapportée par la réponse API (jamais « cached »)."""
    for attr in ("model_version", "modelVersion"):
        value = getattr(response, attr, None)
        if value:
            return str(value)
    return fallback


def _save_corpus(done: dict[str, Any], corpus_path: Path) -> None:
    """Figé le corpus sur disque (cache immédiat), une sauvegarde par vidéo."""
    corpus_path.parent.mkdir(parents=True, exist_ok=True)
    corpus_path.write_text(
        json.dumps({"videos": list(done.values())}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def cmd_ingest(args: argparse.Namespace) -> int:
    """Fusionne des métadonnées collées à la main (JSON) dans videos_raw.json.

    Format d'entrée : [{"id": ..., "url": ..., "title": ..., "description": ..., "transcript": ...}]
    Pas de clé API YouTube ; la collecte est manuelle.
    """
    raw = json.loads(Path(args.input).read_text(encoding="utf-8"))
    out = Path(args.output)
    existing: dict[str, Any] = {}
    if out.exists():
        existing = {v["id"]: v for v in json.loads(out.read_text(encoding="utf-8"))}
    for video in raw:
        if not video.get("id") or not video.get("title"):
            raise CorpusError("chaque vidéo doit avoir un id et un titre")
        existing[video["id"]] = video
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(list(existing.values()), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(existing)} vidéo(s) dans {out}")
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    """Extraction Gemini une seule fois, avec cache immédiat dans le corpus.

    Nécessite GEMINI_API_KEY ; le résultat est figé et jamais rappelé pendant les parcours.
    Une extraction qui échoue ou sort de la plage 3-5 sujets est enregistrée avec
    un motif visible (extraction_error) : la vidéo est flaggée, pas acceptée en silence.
    """
    raw_path, corpus_path = Path(args.input), Path(args.output)
    raw_videos = json.loads(raw_path.read_text(encoding="utf-8"))
    corpus: dict[str, Any] = {"videos": []}
    if corpus_path.exists():
        corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    done = {v["id"]: v for v in corpus.get("videos", [])}

    try:
        import google.generativeai as genai
    except ImportError:
        print("google-generativeai non installé ; installez-le ou fournissez les sujets à la main.", file=sys.stderr)
        return 2

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY manquante (variable d'environnement).", file=sys.stderr)
        return 2
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(args.model)
    failures = 0

    for video in raw_videos:
        vid = video["id"]
        # Cache : seules les extractions réussies (sujets figés) sont cachées ;
        # une vidéo flaggée (extraction_error) n'est pas « déjà extraite » : elle sera réessayée.
        if vid in done and done[vid].get("topics") and not done[vid].get("extraction_error"):
            continue
        prompt = EXTRACTION_PROMPT.format(
            title=video.get("title", ""),
            description=video.get("description", ""),
            transcript=video.get("transcript") or "(non disponible)",
        )
        try:
            response = model.generate_content(prompt)
            extracted = json.loads(response.text.strip().removeprefix("```json").removesuffix("```").strip())
            if not isinstance(extracted, list):
                raise ValueError("réponse JSON inattendue (liste attendue)")
            if not 3 <= len(extracted) <= 5:
                raise ValueError(f"{len(extracted)} sujets extraits (plage attendue : 3 à 5)")
            version = _model_version(response, args.model)
            topics = []
            for item in extracted:
                raw_label = item["raw"]
                topics.append({
                    "raw": raw_label,
                    "canonical": canonical(raw_label),
                    "justification": item.get("justification", ""),
                    "provenance": {"source": "gemini", "model": args.model, "version": version},
                })
        except Exception as exc:
            # Exception visible : la vidéo est flaggée dans le corpus, jamais acceptée en silence.
            flagged = dict(video)
            flagged.pop("topics", None)
            flagged["extraction_error"] = str(exc)
            done[vid] = flagged
            _save_corpus(done, corpus_path)
            print(f"ÉCHEC extraction : {vid} ({exc})", file=sys.stderr)
            failures += 1
            continue
        enriched = dict(video)
        enriched["topics"] = topics
        done[vid] = enriched
        # Sauvegarde immédiate (cache) après chaque vidéo.
        _save_corpus(done, corpus_path)
        print(f"extrait : {vid} ({len(topics)} sujets)")
    if failures:
        print(f"{failures} exception(s) d'extraction enregistrée(s) dans le corpus (extraction_error).", file=sys.stderr)
        return 1
    print(f"corpus figé : {corpus_path}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    corpus = load_corpus(args.corpus)
    try:
        run = graph_engine.parcours(corpus, args.start, args.mode)
    except graph_engine.PathfindingError as exc:
        print(f"ERREUR : {exc}", file=sys.stderr)
        return 1
    out = Path(args.out) if args.out else Path("data/runs") / f"{args.start}-{args.mode}.json"
    graph_engine.save_run(run, out)
    print(json.dumps(run.to_dict(), ensure_ascii=False, indent=2))
    print(f"run : {out}")
    return 0


def cmd_baseline(args: argparse.Namespace) -> int:
    corpus = load_corpus(args.corpus)
    videos = graph_engine.baseline(corpus, args.start)[:5]
    print(json.dumps({"start": args.start, "baseline": videos}, ensure_ascii=False, indent=2))
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    from .render import render_html

    corpus = load_corpus(args.corpus)
    run = json.loads(Path(args.run).read_text(encoding="utf-8"))
    out = Path(args.out) or Path("out/parcours.html")
    render_html(corpus, run, out)
    print(f"page HTML : {out}")
    return 0


def cmd_feed(args: argparse.Namespace) -> int:
    """Feed vertical : les parcours des deux modes calculés ici et embarqués dans la page."""
    from .render import render_feed_html

    corpus = load_corpus(args.corpus)
    runs: dict[str, dict[str, Any]] = {}
    try:
        for mode in ("decouvrir", "approfondir"):
            runs[mode] = graph_engine.parcours(corpus, args.start, mode).to_dict()
    except graph_engine.PathfindingError as exc:
        print(f"ERREUR : {exc}", file=sys.stderr)
        return 1
    out = Path(args.out) if args.out else Path("out/site/index.html")
    render_feed_html(corpus, runs, out, graph_href=args.graph_href)
    print(f"feed : {out}")
    return 0


def cmd_graph(args: argparse.Namespace) -> int:
    from .render import render_graph

    corpus = load_corpus(args.corpus)
    run = json.loads(Path(args.run).read_text(encoding="utf-8")) if args.run else None
    out = Path(args.out) or Path("out/graphe.png")
    render_graph(corpus, run, out)
    print(f"graphe statique : {out}")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    """Serveur local minimal : page de sélection, parcours lancés depuis la page, graphe à la demande."""
    from .serve import serve_forever

    corpus = load_corpus(args.corpus)
    serve_forever(corpus, Path(args.runs_dir), host=args.host, port=args.port)
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    """Affiche les stats du graphe biparti : composantes, sujets morts, densité."""
    corpus = load_corpus(args.corpus)
    stats = graph_engine.graph_stats(corpus)
    print(f"vidéos : {stats['videos']}")
    print(f"sujets : {stats['topics']} (dont {len(stats['dead_topics'])} sujets morts)")
    print(f"liens vidéo-sujet : {stats['edges']}")
    sizes = ", ".join(str(size) for size in stats["component_sizes"])
    print(f"composantes connectées : {stats['components']} (tailles : {sizes})")
    print(f"sujets morts : {', '.join(stats['dead_topics']) or 'aucun'}")
    print(f"sujets reliant plusieurs vidéos : {', '.join(stats['linking_topics']) or 'aucun'}")
    print(f"densité : {stats['density']:.3f}")
    return 0


def cmd_smoke(args: argparse.Namespace) -> int:
    """Contrôle de fumée du site : contenu généré (répertoire) ou URL publique.

    Le déploiement GitHub Pages est lent à propager : le contrôle distant
    retente (attempts x delay) avant d'échouer.
    """
    from .smoke import SmokeCheckError, check_deployed_url, check_site_dir

    try:
        if args.url:
            check_deployed_url(
                args.url,
                first_video=args.first_video,
                graph_name=args.graph,
                attempts=args.attempts,
                delay=args.delay,
            )
            print(f"contrôle de fumée : {args.url} sert le feed (première carte {args.first_video})")
        else:
            check_site_dir(args.site, first_video=args.first_video, graph_name=args.graph)
            print(f"contrôle de fumée : {args.site} — la racine sert le feed (première carte {args.first_video})")
    except SmokeCheckError as exc:
        print(f"ERREUR : {exc}", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vte", description="Video Topic Explorer — MVP")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("ingest", help="fusionne des métadonnées manuelles")
    p.add_argument("input")
    p.add_argument("--output", default="data/videos_raw.json")
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("extract", help="extraction Gemini une fois, mise en cache")
    p.add_argument("input")
    p.add_argument("--output", default="data/corpus.json")
    p.add_argument("--model", default="gemini-1.5-flash")
    p.set_defaults(func=cmd_extract)

    p = sub.add_parser("run", help="calcule un parcours (Approfondir ou Découvrir)")
    p.add_argument("corpus")
    p.add_argument("--start", required=True)
    p.add_argument("--mode", required=True, choices=["approfondir", "decouvrir"])
    p.add_argument("--out", default=None)
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("baseline", help="liste baseline (sujets communs)")
    p.add_argument("corpus")
    p.add_argument("--start", required=True)
    p.set_defaults(func=cmd_baseline)

    p = sub.add_parser("render", help="page HTML minimale d'un parcours")
    p.add_argument("corpus")
    p.add_argument("--run", required=True)
    p.add_argument("--out", default=None)
    p.set_defaults(func=cmd_render)

    p = sub.add_parser("feed", help="page feed vertical : parcours des deux modes embarqués")
    p.add_argument("corpus")
    p.add_argument("--start", required=True)
    p.add_argument("--out", default=None)
    p.add_argument("--graph-href", default="graphe.png")
    p.set_defaults(func=cmd_feed)

    p = sub.add_parser("graph", help="graphe statique avec sous-graphe surligné")
    p.add_argument("corpus")
    p.add_argument("--run", default=None)
    p.add_argument("--out", default=None)
    p.set_defaults(func=cmd_graph)

    p = sub.add_parser("stats", help="stats du graphe : composantes, sujets morts, densité")
    p.add_argument("corpus")
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("serve", help="page locale : sélection, parcours, graphe à la demande")
    p.add_argument("corpus")
    p.add_argument("--runs-dir", default="data/runs")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("smoke", help="contrôle de fumée du site : répertoire généré ou URL publique")
    p.add_argument("--site", default="out/site", help="répertoire du site généré (contrôle local)")
    p.add_argument("--url", default=None, help="URL publique de la racine du site (contrôle distant)")
    p.add_argument("--first-video", required=True, help="première vidéo attendue du parcours par défaut")
    p.add_argument("--graph", default="graphe.png")
    p.add_argument("--attempts", type=int, default=10, help="tentatives du contrôle distant")
    p.add_argument("--delay", type=float, default=30.0, help="secondes entre deux tentatives distantes")
    p.set_defaults(func=cmd_smoke)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
