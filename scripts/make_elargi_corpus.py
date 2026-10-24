"""Corpus élargi (57 vidéos) : corpus réel + panel de genres YouTube.

Part du corpus réel figé (data/corpus_real.json, 35 vidéos techniques) et
lui ajoute 22 vidéos YouTube réelles couvrant un panel élargi de genres :
musique, fun/culture internet, science, économie, jeux vidéo.

Chaque ID a été validé via l'oEmbed public de YouTube (titre + chaîne) ;
les sujets (3-5 par vidéo) sont assignés manuellement à partir du titre
public — aucune clé API, aucun appel LLM.

Le panel est conçu pour rester une seule composante connectée, avec des
ponts réels entre genres :

- Science ↔ technique : « Machine Learning », « Réseaux de neurones »,
  « Deep Learning » (3Blue1Brown ↔ cluster ML du corpus réel) ;
- Musique ↔ science : « Apprentissage » (Lofi Girl ↔ 3Blue1Brown,
  Veritasium) et « Culture internet » ;
- Musique ↔ technique : « Tutoriels » (design sonore ↔ cluster LLVM/Rust) ;
- Fun ↔ jeux vidéo : « Histoire » (bill wurtz ↔ Boss Keys Zelda) ;
- Économie ↔ science : « Pédagogie » (CrashCourse ↔ Veritasium).

Régénérer :  python3 scripts/make_elargi_corpus.py
Stats :      python3 -m vte.cli stats data/corpus_elargi.json
"""

import json
from pathlib import Path

PROVENANCE = {"source": "manual-curated", "model": "human", "version": "2026-10"}

# (id, chaîne, titre, sujets 3-5, genre pour la description)
PANEL = [
    # --- Musique (pont avec le corpus réel via « Tutoriels ») ---
    ("dQw4w9WgXcQ", "Rick Astley", "Rick Astley - Never Gonna Give You Up (Official Video) (4K Remaster)", ["Pop", "Clip vidéo", "Mème internet", "Culture internet"], "Clip musical"),
    ("fJ9rUzIMcZQ", "Queen Official", "Queen – Bohemian Rhapsody (Official Video Remastered)", ["Rock", "Clip vidéo", "Composition musicale", "Histoire de la musique"], "Clip musical"),
    ("9bZkp7q19f0", "officialpsy", "PSY - GANGNAM STYLE(강남스타일) M/V", ["Pop", "Clip vidéo", "Phénomène viral", "Culture internet"], "Clip musical"),
    ("BTYAsjAVa3I", "Lofi Girl", "3 A.M Study Session [lofi hip hop]", ["Musique", "Musique électronique", "Production musicale", "Apprentissage", "Culture internet"], "Mix lofi"),
    ("44NUPu7cVfI", "Rick Beato", "What Makes This Song Great? \"Just What I Needed\" THE CARS", ["Théorie musicale", "Analyse musicale", "Production musicale", "Rock"], "Vidéo-essai"),
    ("Rd9K0Q_Ykx0", "How Do You Do? with David Bennett", "How Adam Neely pioneered Music Theory YouTube and then quit • How Do You Do ep.13", ["Théorie musicale", "Analyse musicale", "Histoire de la musique", "Culture internet"], "Vidéo-essai"),
    ("BsGCGB_LZAo", "EDM Tips", "Sound Design Explained in 28 Minutes", ["Design sonore", "Musique électronique", "Production musicale", "Tutoriels"], "Tutoriel"),

    # --- Fun / culture internet ---
    ("jNQXAC9IVRw", "jawed", "Me at the zoo", ["Culture internet", "Histoire d'Internet", "Phénomène viral"], "Vlog"),
    ("xuCn8ux2gbs", "bill wurtz", "history of the entire world, i guess", ["Histoire", "Humour", "Animation", "Visualisation", "Culture internet"], "Animation"),
    ("ZZ5LpwO-An4", "ProtoOfSnagem", "HEYYEYAAEYAAAEYAEYAA", ["Mème internet", "Humour", "Musique", "Culture internet", "Phénomène viral"], "Mème"),

    # --- Science (pont avec la technique via les sujets ML du corpus réel) ---
    ("aircAruvnKk", "3Blue1Brown", "But what is a neural network? | Deep learning chapter 1", ["Réseaux de neurones", "Deep Learning", "Machine Learning", "Mathématiques"], "Vidéo pédagogique"),
    ("fNk_zzaMoSs", "3Blue1Brown", "Vectors | Chapter 1, Essence of linear algebra", ["Mathématiques", "Algèbre linéaire", "Visualisation", "Apprentissage"], "Vidéo pédagogique"),
    ("h6fcK_fRYaI", "Kurzgesagt – In a Nutshell", "The Egg - A Short Story", ["Science", "Philosophie", "Animation", "Univers", "Science-fiction"], "Animation"),
    ("MBRqu0YOH14", "Kurzgesagt – In a Nutshell", "Optimistic Nihilism", ["Science", "Philosophie", "Existentialisme", "Univers", "Animation"], "Animation"),
    ("2Vrhk5OjBP8", "AlphaPhoenix", "I bought 1000 meters of wire to settle a physics debate", ["Science", "Physique", "Électricité", "Expérimentation"], "Expérience"),
    ("rhgwIhB58PA", "Veritasium", "The Biggest Myth In Education", ["Pédagogie", "Sciences cognitives", "Apprentissage", "Culture internet"], "Vidéo-essai"),

    # --- Économie (pont avec la science via « Pédagogie ») ---
    ("3ez10ADR_gM", "CrashCourse", "Intro to Economics: Crash Course Econ #1", ["Économie", "Macroéconomie", "Microéconomie", "Pédagogie"], "Cours"),
    ("GtksJpfoM_g", "Economics Explained", "The Stagnating Economy of Canada | Economics Explained", ["Économie", "Macroéconomie", "Politique publique", "Croissance économique"], "Analyse économique"),

    # --- Jeux vidéo (pont avec fun via « Histoire », avec musique via la culture internet) ---
    ("a1hHOVIkrcc", "Game Maker's Toolkit", "The World Design of Castlevania: Symphony of the Night | Boss Keys", ["Game design", "Level design", "Metroidvania", "Exploration"], "Vidéo-essai"),
    ("nn2MXwplMZA", "Game Maker's Toolkit", "The World Design of Super Metroid | Boss Keys", ["Game design", "Level design", "Metroidvania", "Exploration"], "Vidéo-essai"),
    ("QhWdBhc3Wjc", "Game Maker's Toolkit", "The World Design of Dark Souls | Boss Keys", ["Game design", "Level design", "Exploration", "Difficulté"], "Vidéo-essai"),
    ("emtlJ5SXLM4", "Game Maker's Toolkit", "The Legend of Zelda / Zelda II's dungeon design | Boss Keys", ["Game design", "Level design", "Exploration", "Histoire"], "Vidéo-essai"),
]


def build() -> dict:
    here = Path(__file__).resolve().parent.parent
    real = json.loads((here / "data" / "corpus_real.json").read_text(encoding="utf-8"))
    videos = list(real["videos"])
    for vid, channel, title, topics, kind in PANEL:
        videos.append({
            "id": vid,
            "url": f"https://www.youtube.com/watch?v={vid}",
            "title": title,
            "channel": channel,
            "description": f"{kind} YouTube sur : {', '.join(topics)}.",
            "topics": [
                {
                    "raw": t,
                    "canonical": t,
                    "justification": "assigné depuis le titre public",
                    "provenance": PROVENANCE,
                }
                for t in topics
            ],
        })
    return {"videos": videos, "provenance": PROVENANCE}


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "data" / "corpus_elargi.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    corpus = build()
    out.write_text(json.dumps(corpus, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ids = [v["id"] for v in corpus["videos"]]
    print(f"corpus élargi : {out} ({len(ids)} vidéos, {len(set(ids))} IDs uniques)")
