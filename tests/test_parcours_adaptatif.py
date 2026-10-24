"""Parcours direct : tests à la frontière HTTP publique du serveur local."""

import http.client
import json
import random
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from http.cookies import SimpleCookie
from pathlib import Path

import pytest

from conftest import load_corpus_from_videos, make_video
from vte import serve
from vte.corpus import topics_of


def start_server(corpus, runs_dir, *, rng=None):
    options = {"rng": rng} if rng is not None else {}
    httpd = serve.make_server(corpus, Path(runs_dir), host="127.0.0.1", port=0, **options)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


def request(httpd, method, path, *, cookie=None, payload=None):
    conn = http.client.HTTPConnection("127.0.0.1", httpd.server_address[1], timeout=10)
    headers = {}
    body = None
    if cookie:
        headers["Cookie"] = cookie
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload)
    try:
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        conn.close()


def begin_session(httpd):
    status, headers, body = request(httpd, "GET", "/")
    assert status == 200
    cookie = SimpleCookie()
    cookie_header = next(
        (value for name, value in headers.items() if name.lower() == "set-cookie"), None
    )
    assert cookie_header is not None, (serve.__file__, headers, body[:600])
    cookie.load(cookie_header)
    session_cookie = f"parcours_session={cookie['parcours_session'].value}"
    status, _, state_body = request(httpd, "GET", "/session", cookie=session_cookie)
    assert status == 200
    return session_cookie, json.loads(state_body), body.decode("utf-8")


@pytest.fixture
def server(rich_corpus, tmp_path):
    httpd = start_server(rich_corpus, tmp_path / "runs")
    httpd.corpus = rich_corpus
    yield httpd
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture
def chain_server(tmp_path):
    corpus = load_corpus_from_videos([
        make_video("a", ["C#", "Roslyn"]),
        make_video("b", ["Roslyn", "Compilateurs"]),
        make_video("c", ["Compilateurs", "LLVM"]),
        make_video("d", ["LLVM", "Rust"]),
    ])
    httpd = start_server(corpus, tmp_path / "runs")
    httpd.corpus = corpus
    yield httpd
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture
def isolated_server(tmp_path):
    corpus = load_corpus_from_videos([make_video("solo", ["SujetUnique"])])
    httpd = start_server(corpus, tmp_path / "runs")
    httpd.corpus = corpus
    yield httpd
    httpd.shutdown()
    httpd.server_close()


def assert_real_transition(corpus, transition):
    by_id = {video["id"]: video for video in corpus["videos"]}
    previous = by_id[transition["from"]]
    following = by_id[transition["to"]]
    path = transition["topic_path"]
    assert path
    assert path[0] in topics_of(previous)
    assert path[-1] in topics_of(following)
    for first, second in zip(path, path[1:]):
        assert any(first in topics_of(video) and second in topics_of(video) for video in corpus["videos"])


def test_arrival_starts_with_one_video_and_two_controls(server):
    _, state, doc = begin_session(server)

    assert state["video"]["id"] == "v1"
    assert doc.count('data-video-id=') == 1
    assert 'action="/parcours"' not in doc
    assert "<select" not in doc
    assert "Simuler un visionnage long" in doc
    assert 'data-action="interest"' in doc
    assert "Zapper" in doc
    assert 'data-action="zap"' in doc
    zap = re.search(r'<button[^>]*data-action="zap"[^>]*>', doc)
    assert zap is not None and "disabled" not in zap.group(0)


def test_interests_replace_the_video_and_move_the_interest_point(server):
    cookie, initial, _ = begin_session(server)
    first_status, _, first_body = request(
        server,
        "POST",
        "/action",
        cookie=cookie,
        payload={"action": "interest", "version": initial["version"]},
    )
    first = json.loads(first_body)
    assert first_status == 200
    assert first["transition"]["from"] == "v1"
    assert first["video"]["id"] == "v2"
    assert first["point_interet"] == "v1"
    assert_real_transition(server.corpus, first["transition"])

    second_status, _, second_body = request(
        server,
        "POST",
        "/action",
        cookie=cookie,
        payload={"action": "interest", "version": first["version"]},
    )
    second = json.loads(second_body)
    assert second_status == 200
    assert second["transition"]["from"] == "v2"
    assert second["video"]["id"] == "v3"
    assert second["point_interet"] == "v2"
    assert_real_transition(server.corpus, second["transition"])


@pytest.mark.parametrize("action", ["interest", "zap"])
def test_stale_action_does_not_create_an_extra_transition(server, action):
    cookie, initial, _ = begin_session(server)
    accepted_status, _, accepted_body = request(
        server,
        "POST",
        "/action",
        cookie=cookie,
        payload={"action": action, "version": initial["version"]},
    )
    accepted = json.loads(accepted_body)
    assert accepted_status == 200

    stale_status, _, stale_body = request(
        server,
        "POST",
        "/action",
        cookie=cookie,
        payload={"action": action, "version": initial["version"]},
    )
    stale = json.loads(stale_body)
    assert stale_status == 409
    assert stale["video"]["id"] == accepted["video"]["id"]
    assert stale["version"] == accepted["version"]


def test_invalid_action_keeps_the_current_video_available_for_retry(server):
    cookie, initial, _ = begin_session(server)
    status, _, body = request(
        server,
        "POST",
        "/action",
        cookie=cookie,
        payload={"action": "invalide", "version": initial["version"]},
    )
    error = json.loads(body)
    assert status == 400
    assert "action inconnue" in error["erreur"]

    state_status, _, state_body = request(server, "GET", "/session", cookie=cookie)
    state = json.loads(state_body)
    assert state_status == 200
    assert state["video"]["id"] == initial["video"]["id"]
    assert state["version"] == initial["version"]
    assert state["status"] == "active"


@pytest.mark.parametrize("action", ["interest", "zap"])
def test_simultaneous_actions_accept_only_one_transition(server, action):
    cookie, initial, _ = begin_session(server)

    def act():
        return request(
            server,
            "POST",
            "/action",
            cookie=cookie,
            payload={"action": action, "version": initial["version"]},
        )[0]

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(lambda _: act(), range(2)))

    assert sorted(statuses) == [200, 409]
    status, _, state_body = request(server, "GET", "/session", cookie=cookie)
    final = json.loads(state_body)
    assert status == 200
    assert final["version"] == 1
    assert final["video"]["id"] == "v2"


def test_local_exhaustion_is_explicit_and_keeps_the_last_video(chain_server):
    cookie, state, _ = begin_session(chain_server)
    seen = {state["video"]["id"]}
    while state["status"] == "active":
        status, _, body = request(
            chain_server,
            "POST",
            "/action",
            cookie=cookie,
            payload={"action": "interest", "version": state["version"]},
        )
        assert status == 200
        result = json.loads(body)
        if result["status"] == "active":
            assert result["video"]["id"] not in seen
            assert_real_transition(chain_server.corpus, result["transition"])
            seen.add(result["video"]["id"])
        state = result

    assert state["status"] == "exhausted"
    assert state["video"]["id"] == "d"
    assert "plus aucune vidéo" in state["message"].lower()


def test_isolated_start_reports_local_exhaustion_without_an_error(isolated_server):
    cookie, initial, _ = begin_session(isolated_server)
    status, _, body = request(
        isolated_server,
        "POST",
        "/action",
        cookie=cookie,
        payload={"action": "interest", "version": initial["version"]},
    )
    result = json.loads(body)
    assert status == 200
    assert result["status"] == "exhausted"
    assert result["video"]["id"] == "solo"
    assert "plus aucune vidéo" in result["message"].lower()


@pytest.fixture
def branch_server(tmp_path):
    """Le point d’intérêt initial et la vidéo quittée ont des voisins divergents."""
    corpus = load_corpus_from_videos([
        make_video("a-start", ["Alpha", "OldPivot"]),
        make_video("b-current", ["Alpha", "Beta"]),
        make_video("c-old-pivot", ["OldPivot", "OldLeaf"]),
        make_video("d-neighbor", ["Beta", "NeighborLeaf"]),
        make_video("e-after-zap-interest", ["OldLeaf", "Further"]),
    ])
    httpd = start_server(corpus, tmp_path / "runs")
    httpd.corpus = corpus
    yield httpd
    httpd.shutdown()
    httpd.server_close()


def test_zap_after_interest_uses_current_video_and_drops_old_interest(branch_server):
    cookie, initial, _ = begin_session(branch_server)
    assert initial["video"]["id"] == "a-start"
    by_id = {video["id"]: video for video in branch_server.corpus["videos"]}
    assert topics_of(by_id["a-start"]) & topics_of(by_id["c-old-pivot"]) == {"OldPivot"}
    assert topics_of(by_id["b-current"]) & topics_of(by_id["d-neighbor"]) == {"Beta"}
    old_pivot_status, _, old_pivot_body = request(
        branch_server,
        "GET",
        "/etape?from=a-start&mode=approfondir&exclu=b-current",
    )
    old_pivot = json.loads(old_pivot_body)
    assert old_pivot_status == 200
    assert old_pivot["to"] == "c-old-pivot"
    assert old_pivot["topic_path"] == ["OldPivot"]
    assert_real_transition(branch_server.corpus, old_pivot)

    interest_status, _, interest_body = request(
        branch_server, "POST", "/action", cookie=cookie,
        payload={"action": "interest", "version": initial["version"]},
    )
    interest = json.loads(interest_body)
    assert interest_status == 200
    assert interest["video"]["id"] == "b-current"
    assert interest["point_interet"] == "a-start"
    assert_real_transition(branch_server.corpus, interest["transition"])

    zap_status, _, zap_body = request(
        branch_server, "POST", "/action", cookie=cookie,
        payload={"action": "zap", "version": interest["version"]},
    )
    zap = json.loads(zap_body)
    assert zap_status == 200
    assert zap["transition"]["from"] == "b-current"
    assert zap["video"]["id"] == "d-neighbor"
    assert zap["point_interet"] is None
    assert zap["transition"]["topic_path"] == ["Beta"]
    assert_real_transition(branch_server.corpus, zap["transition"])


def test_first_zap_explores_and_a_later_interest_restores_the_pivot(branch_server):
    cookie, initial, _ = begin_session(branch_server)
    zap_status, _, zap_body = request(
        branch_server, "POST", "/action", cookie=cookie,
        payload={"action": "zap", "version": initial["version"]},
    )
    zap = json.loads(zap_body)
    assert zap_status == 200
    assert zap["video"]["id"] == "c-old-pivot"
    assert zap["point_interet"] is None
    assert zap["transition"]["topic_path"] == ["OldPivot"]
    assert_real_transition(branch_server.corpus, zap["transition"])

    interest_status, _, interest_body = request(
        branch_server, "POST", "/action", cookie=cookie,
        payload={"action": "interest", "version": zap["version"]},
    )
    interest = json.loads(interest_body)
    assert interest_status == 200
    assert interest["transition"]["from"] == "c-old-pivot"
    assert interest["video"]["id"] == "e-after-zap-interest"
    assert interest["point_interet"] == "c-old-pivot"
    assert_real_transition(branch_server.corpus, interest["transition"])


@pytest.fixture
def widening_server(tmp_path):
    """Réseau où la direction proche mène à une vidéo, puis à un sujet plus éloigné."""
    corpus = load_corpus_from_videos([
        make_video("00-start", ["A", "C", "X"]),
        make_video("01-pivot", ["A", "D", "M"]),
        make_video("02-current", ["D", "B"]),
        make_video("03-near", ["B", "C"]),
        make_video("04-far", ["B", "Z", "Y", "R"]),
        make_video("08-close", ["Y", "R", "M"]),
        make_video("06-farther", ["R", "S"]),
        make_video("09-relay", ["M", "Q", "X", "Z"]),
    ])
    httpd = start_server(corpus, tmp_path / "runs")
    httpd.corpus = corpus
    yield httpd
    httpd.shutdown()
    httpd.server_close()


def post_action(httpd, cookie, state, action):
    status, _, body = request(
        httpd,
        "POST",
        "/action",
        cookie=cookie,
        payload={"action": action, "version": state["version"]},
    )
    return status, json.loads(body)


@pytest.fixture
def restart_server(tmp_path):
    """Cycle visitable plus des vidéos d’entrée éloignées de sa dernière étape."""
    cycle = [
        make_video(f"{index:02d}-cycle", [f"T{index}", f"T{(index + 1) % 10}"])
        for index in range(10)
    ]
    corpus = load_corpus_from_videos(
        cycle
        + [
            make_video("zy-root-two-a", ["T2", "Racine secondaire deux A"]),
            make_video("zz-root-two-b", ["T2", "Racine secondaire deux B"]),
            make_video("zy-root-five-a", ["T5", "Racine secondaire cinq A"]),
            make_video("zz-root-five-b", ["T5", "Racine secondaire cinq B"]),
        ]
    )
    httpd = start_server(corpus, tmp_path / "runs", rng=random.Random(23))
    httpd.corpus = corpus
    yield httpd
    httpd.shutdown()
    httpd.server_close()


def test_exhausted_interest_path_restarts_at_an_unseen_canonical_topic(restart_server, tmp_path):
    cookie, state, _ = begin_session(restart_server)
    shown = {state["video"]["id"]}
    assert state["video"]["id"] == "00-cycle"

    for expected_index in range(1, 10):
        status, state = post_action(restart_server, cookie, state, "interest")
        expected = f"{expected_index:02d}-cycle"
        assert status == 200
        assert state["video"]["id"] == expected
        assert state["video"]["id"] not in shown
        shown.add(state["video"]["id"])
        assert_real_transition(restart_server.corpus, state["transition"])

    status, restarted = post_action(restart_server, cookie, state, "interest")
    assert status == 200
    assert restarted["status"] == "active"
    assert restarted["video"]["id"] not in shown
    assert restarted["video"]["id"] in {
        "zy-root-two-a", "zz-root-two-b", "zy-root-five-a", "zz-root-five-b"
    }
    shown.add(restarted["video"]["id"])
    assert restarted["point_interet"] is None
    assert restarted["message"] == (
        "Tu as exploré les branches disponibles. "
        "On repart sur un autre arbre choisi au hasard."
    )
    assert restarted["transition"]["kind"] == "restart"
    assert restarted["transition"]["topic_path"] == []
    assert "from" not in restarted["transition"]
    assert "to" not in restarted["transition"]
    root_topic = restarted["transition"]["root_topic"]
    assert root_topic in restarted["video"]["topics"]
    assert root_topic in {"T2", "T5"}
    assert root_topic not in restart_server.corpus["dead_topics"]

    duplicate_status, _, duplicate_body = request(
        restart_server,
        "POST",
        "/action",
        cookie=cookie,
        payload={"action": "interest", "version": state["version"]},
    )
    duplicate = json.loads(duplicate_body)
    assert duplicate_status == 409
    assert duplicate["video"]["id"] == restarted["video"]["id"]
    assert duplicate["version"] == restarted["version"]

    page_status, _, page_body = request(restart_server, "GET", "/", cookie=cookie)
    page = page_body.decode("utf-8")
    assert page_status == 200
    assert restarted["message"] in page
    assert f"Nouvelle racine : {root_topic}" in page
    assert 'data-action="interest"' in page
    assert 'data-action="zap"' in page

    replay_server = start_server(
        restart_server.corpus,
        tmp_path / "replay-runs",
        rng=random.Random(23),
    )
    try:
        replay_cookie, replay_state, _ = begin_session(replay_server)
        for _ in range(9):
            status, replay_state = post_action(
                replay_server, replay_cookie, replay_state, "interest"
            )
            assert status == 200
        status, replay = post_action(
            replay_server, replay_cookie, replay_state, "interest"
        )
        assert status == 200
        assert replay["transition"] == restarted["transition"]
        assert replay["video"]["id"] == restarted["video"]["id"]
    finally:
        replay_server.shutdown()
        replay_server.server_close()


def test_zap_after_local_exploration_restarts_away_from_the_rejected_direction(restart_server):
    cookie, state, _ = begin_session(restart_server)
    seen = {state["video"]["id"]}
    for expected_index in range(1, 10):
        status, state = post_action(restart_server, cookie, state, "interest")
        assert status == 200
        assert state["video"]["id"] == f"{expected_index:02d}-cycle"
        seen.add(state["video"]["id"])

    status, restarted = post_action(restart_server, cookie, state, "zap")
    assert status == 200
    assert restarted["status"] == "active"
    assert restarted["video"]["id"] not in seen
    assert restarted["video"]["id"].startswith(("zy-root-", "zz-root-"))
    assert restarted["point_interet"] is None
    assert restarted["transition"]["kind"] == "restart"
    assert restarted["transition"]["root_topic"] in {"T2", "T5"}
    assert restarted["transition"]["root_topic"] not in {"T9", "T0"}
    assert restarted["transition"]["topic_path"] == []
    assert restarted["message"] == (
        "Tu as exploré les branches disponibles. "
        "On repart sur un autre arbre choisi au hasard."
    )


def test_interest_after_restart_establishes_a_new_interest_point(restart_server):
    cookie, state, _ = begin_session(restart_server)
    for expected_index in range(1, 10):
        status, state = post_action(restart_server, cookie, state, "interest")
        assert status == 200
        assert state["video"]["id"] == f"{expected_index:02d}-cycle"

    status, restarted = post_action(restart_server, cookie, state, "interest")
    assert status == 200 and restarted["transition"]["kind"] == "restart"
    root_video = restarted["video"]["id"]

    status, continued = post_action(restart_server, cookie, restarted, "interest")
    assert status == 200
    assert continued["status"] == "active"
    assert continued["video"]["id"] != root_video
    assert continued["video"]["id"].startswith(("zy-root-", "zz-root-"))
    assert continued["point_interet"] == root_video
    assert continued["transition"]["kind"] == "linked"
    assert continued["transition"]["from"] == root_video
    assert continued["transition"]["to"] == continued["video"]["id"]
    assert_real_transition(restart_server.corpus, continued["transition"])


def test_all_unseen_roots_eventually_exhaust_without_repeating_a_video(restart_server):
    cookie, state, _ = begin_session(restart_server)
    shown = {state["video"]["id"]}

    for _ in range(len(restart_server.corpus["videos"]) + 1):
        status, result = post_action(restart_server, cookie, state, "interest")
        assert status == 200
        if result["status"] == "exhausted":
            assert result["video"]["id"] == state["video"]["id"]
            assert result["transition"] is None
            assert "plus aucune vidéo inédite" in result["message"].lower()
            state = result
            break

        video_id = result["video"]["id"]
        assert video_id not in shown
        shown.add(video_id)
        if result["transition"]["kind"] == "linked":
            assert_real_transition(restart_server.corpus, result["transition"])
        else:
            assert result["transition"]["kind"] == "restart"
            assert result["transition"]["topic_path"] == []
        state = result
    else:
        pytest.fail("le parcours doit terminer après avoir épuisé les racines admissibles")

    assert state["status"] == "exhausted"
    assert shown == {video["id"] for video in restart_server.corpus["videos"]}
    page_status, _, page_body = request(restart_server, "GET", "/", cookie=cookie)
    page = page_body.decode("utf-8")
    assert page_status == 200
    assert "plus aucune vidéo inédite" in page.lower()
    assert "Recommencer" not in page
    assert 'data-action="interest" disabled' in page
    assert 'data-action="zap" disabled' in page




def test_zaps_progress_from_a_near_branch_to_a_farther_topic(widening_server):
    cookie, state, _ = begin_session(widening_server)
    seen = {state["video"]["id"]}

    status, state = post_action(widening_server, cookie, state, "interest")
    assert status == 200 and state["video"]["id"] == "01-pivot"
    seen.add(state["video"]["id"])
    status, state = post_action(widening_server, cookie, state, "interest")
    assert status == 200 and state["video"]["id"] == "02-current"
    seen.add(state["video"]["id"])

    status, state = post_action(widening_server, cookie, state, "zap")
    assert status == 200
    assert state["video"]["id"] == "03-near"
    assert state["point_interet"] is None
    assert_real_transition(widening_server.corpus, state["transition"])
    seen.add(state["video"]["id"])

    status, state = post_action(widening_server, cookie, state, "zap")
    assert status == 200
    assert state["video"]["id"] == "04-far"
    assert state["point_interet"] is None
    assert state["transition"]["topic_path"] == ["C", "X", "Z"]
    assert_real_transition(widening_server.corpus, state["transition"])
    assert state["video"]["id"] not in seen
    seen.add(state["video"]["id"])

    status, state = post_action(widening_server, cookie, state, "interest")
    assert status == 200
    assert state["transition"]["from"] == "04-far"
    # 08-close partage deux sujets avec le point d’intérêt, contre un pour
    # 06-farther et 09-relay ; le classement par sujets communs l’emporte.
    assert state["video"]["id"] == "08-close"
    assert state["point_interet"] == "04-far"
    assert state["transition"]["topic_path"] == ["R"]
    assert_real_transition(widening_server.corpus, state["transition"])

    # Le premier zap après cet intérêt repart au rayon local : le sujet éloigné
    # 06-farther reste hors portée et la transition s'arrête sur 09-relay.
    status, state = post_action(widening_server, cookie, state, "zap")
    assert status == 200
    assert state["transition"]["from"] == "08-close"
    assert state["video"]["id"] == "09-relay"
    assert state["point_interet"] is None
    assert state["transition"]["topic_path"] == ["M"]
    assert_real_transition(widening_server.corpus, state["transition"])


def test_repeated_zaps_without_an_initial_interest_keep_exploring(branch_server):
    cookie, state, _ = begin_session(branch_server)
    seen = {state["video"]["id"]}

    for expected in ("c-old-pivot", "e-after-zap-interest"):
        status, state = post_action(branch_server, cookie, state, "zap")
        assert status == 200
        assert state["video"]["id"] == expected
        assert state["point_interet"] is None
        assert state["video"]["id"] not in seen
        assert_real_transition(branch_server.corpus, state["transition"])
        seen.add(state["video"]["id"])
