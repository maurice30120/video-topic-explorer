"""Sous-commande CLI `run` et point d'entrée `python -m vte` (spécification MVP).

Le mode seul détermine le rayon (story 16 : jamais élargi, mode = choix
explicite) : aucun flag --radius ne doit exister. `python -m vte` doit
déléguer à la CLI comme `python -m vte.cli`.
"""

import json
import runpy
import sys

import pytest

from vte import cli
from vte import graph_engine

from conftest import make_video


@pytest.fixture
def chain_corpus_path(tmp_path):
    videos = [
        make_video("a", ["C#", "Roslyn"]),
        make_video("b", ["Roslyn", "Compilateurs"]),
        make_video("c", ["Compilateurs", "LLVM"]),
        make_video("d", ["LLVM", "Rust"]),
    ]
    path = tmp_path / "corpus.json"
    path.write_text(json.dumps({"videos": videos}, ensure_ascii=False), encoding="utf-8")
    return path


def test_run_mode_alone_determines_radius(chain_corpus_path, tmp_path):
    """Approfondir = 1, Découvrir = 3 : le mode suffit, pas de rayon paramétrable."""
    for mode, radius in (("approfondir", 1), ("decouvrir", 3)):
        out = tmp_path / f"run-{mode}.json"
        code = cli.main(["run", str(chain_corpus_path), "--start", "a", "--mode", mode, "--out", str(out)])
        assert code == 0
        assert json.loads(out.read_text(encoding="utf-8"))["radius"] == radius


def test_run_rejects_radius_override(chain_corpus_path, tmp_path):
    """Story 16 : le rayon n'est jamais élargi à la main — le flag n'existe pas."""
    with pytest.raises(SystemExit) as exc:
        cli.main([
            "run", str(chain_corpus_path), "--start", "a", "--mode", "decouvrir",
            "--radius", "2", "--out", str(tmp_path / "run.json"),
        ])
    assert exc.value.code == 2  # argparse : option inconnue


def test_python_dash_m_vte_delegates_to_cli(chain_corpus_path, monkeypatch, capsys):
    """`python -m vte` délègue à vte.cli.main, comme `python -m vte.cli`."""
    monkeypatch.setattr(sys, "argv", ["vte", "stats", str(chain_corpus_path)])
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("vte", run_name="__main__")
    assert exc.value.code == 0
    assert "composantes connectées : 1" in capsys.readouterr().out

def test_render_without_out_writes_default_page(chain_corpus_path, tmp_path, monkeypatch):
    """`render` sans --out : code 0, page écrite à l'emplacement par défaut."""
    monkeypatch.chdir(tmp_path)
    run_file = tmp_path / "run.json"
    assert cli.main(["run", str(chain_corpus_path), "--start", "a", "--mode", "approfondir", "--out", str(run_file)]) == 0
    code = cli.main(["render", str(chain_corpus_path), "--run", str(run_file)])
    assert code == 0
    assert (tmp_path / "out" / "parcours.html").is_file()

def test_graph_without_out_writes_default_image(chain_corpus_path, tmp_path, monkeypatch):
    """`graph` sans --out : code 0, image écrite à l'emplacement par défaut."""
    monkeypatch.chdir(tmp_path)
    code = cli.main(["graph", str(chain_corpus_path)])
    assert code == 0
    assert (tmp_path / "out" / "graphe.png").is_file()

def test_run_accepts_exactly_the_engine_modes(chain_corpus_path, tmp_path):
    """Les modes acceptés par la CLI sont exactement ceux du moteur (graph_engine.Mode)."""
    for mode in graph_engine.Mode:
        out = tmp_path / f"run-{mode.value}.json"
        assert cli.main(["run", str(chain_corpus_path), "--start", "a", "--mode", mode.value, "--out", str(out)]) == 0


def test_run_rejects_mode_outside_engine_types(chain_corpus_path):
    """Un mode absent des types du moteur est refusé par argparse (code 2)."""
    with pytest.raises(SystemExit) as exc:
        cli.main(["run", str(chain_corpus_path), "--start", "a", "--mode", "teleporter"])
    assert exc.value.code == 2
