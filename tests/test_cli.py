"""Sous-commande CLI `run` et point d'entrée `python -m vte` (spécification MVP).

Le rayon est un paramètre explicite (spec #27, ticket #35) : la CLI prend
`--rayon`, plus aucun `--mode` n'existe. `python -m vte` doit déléguer à la
CLI comme `python -m vte.cli`.
"""

import json
import runpy
import sys

import pytest

from vte import cli

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


def test_run_rayon_explicite_porte_par_le_run(chain_corpus_path, tmp_path):
    """Le rayon passé à la CLI est porté tel quel par le run, jamais un mode."""
    for rayon in (1, 3):
        out = tmp_path / f"run-r{rayon}.json"
        code = cli.main(["run", str(chain_corpus_path), "--start", "a", "--rayon", str(rayon), "--out", str(out)])
        assert code == 0
        payload = json.loads(out.read_text(encoding="utf-8"))
        assert payload["radius"] == rayon
        assert "mode" not in payload


def test_run_rejects_mode_flag(chain_corpus_path, tmp_path):
    """Ticket #35 : plus aucun --mode — l'option inconnue est refusée (code 2)."""
    with pytest.raises(SystemExit) as exc:
        cli.main([
            "run", str(chain_corpus_path), "--start", "a", "--mode", "nimporte",
            "--out", str(tmp_path / "run.json"),
        ])
    assert exc.value.code == 2  # argparse : option inconnue


def test_run_rejects_rayon_hors_plage(chain_corpus_path, capsys):
    """Un rayon < 1 est une erreur explicite du moteur (code 1), jamais un repli."""
    code = cli.main(["run", str(chain_corpus_path), "--start", "a", "--rayon", "0"])
    assert code == 1
    assert "rayon" in capsys.readouterr().err


def test_run_rejects_rayon_non_entier(chain_corpus_path):
    """Le rayon est un entier de hops — argparse refuse le reste (code 2)."""
    with pytest.raises(SystemExit) as exc:
        cli.main(["run", str(chain_corpus_path), "--start", "a", "--rayon", "loin"])
    assert exc.value.code == 2


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
    assert cli.main(["run", str(chain_corpus_path), "--start", "a", "--rayon", "1", "--out", str(run_file)]) == 0
    code = cli.main(["render", str(chain_corpus_path), "--run", str(run_file)])
    assert code == 0
    assert (tmp_path / "out" / "parcours.html").is_file()


def test_graph_without_out_writes_default_image(chain_corpus_path, tmp_path, monkeypatch):
    """`graph` sans --out : code 0, image écrite à l'emplacement par défaut."""
    monkeypatch.chdir(tmp_path)
    code = cli.main(["graph", str(chain_corpus_path)])
    assert code == 0
    assert (tmp_path / "out" / "graphe.png").is_file()
