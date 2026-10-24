"""Parcours direct : tests à la frontière HTTP publique du serveur local."""

import http.client
import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from http.cookies import SimpleCookie
from pathlib import Path

import pytest

from conftest import load_corpus_from_videos, make_video
from vte import serve
from vte.corpus import topics_of


def start_server(corpus, runs_dir):
    httpd = serve.make_server(corpus, Path(runs_dir), host="127.0.0.1", port=0)
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
    assert re.search(r'<button[^>]*data-action="zap"[^>]*disabled', doc)


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


def test_stale_action_does_not_create_an_extra_transition(server):
    cookie, initial, _ = begin_session(server)
    accepted_status, _, accepted_body = request(
        server,
        "POST",
        "/action",
        cookie=cookie,
        payload={"action": "interest", "version": initial["version"]},
    )
    accepted = json.loads(accepted_body)
    assert accepted_status == 200

    stale_status, _, stale_body = request(
        server,
        "POST",
        "/action",
        cookie=cookie,
        payload={"action": "interest", "version": initial["version"]},
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


def test_simultaneous_actions_accept_only_one_transition(server):
    cookie, initial, _ = begin_session(server)

    def act():
        return request(
            server,
            "POST",
            "/action",
            cookie=cookie,
            payload={"action": "interest", "version": initial["version"]},
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
