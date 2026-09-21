import pytest

from histposts.cli import build_parser, main, slug


def test_help_exits_cleanly(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    assert "build" in capsys.readouterr().out


def test_missing_spec_is_a_friendly_error(capsys):
    assert main(["build", "does-not-exist.yaml"]) == 2
    assert "error:" in capsys.readouterr().err


def test_unknown_only_name(tmp_path, capsys):
    spec = tmp_path / "p.yaml"
    spec.write_text("posts:\n- {name: a, file: a.jpg, title: T, info: I}\n", encoding="utf-8")
    assert main(["build", str(spec), "--only", "zzz", "--out", str(tmp_path / "o")]) == 2
    assert "unknown post" in capsys.readouterr().err


def test_slug():
    assert slug("Şişli Çarşı 1900!") == "sisli-carsi-1900"
    assert slug("!!!") == "search"


def test_parser_defaults():
    args = build_parser().parse_args(["build", "posts.yaml"])
    assert args.enhance == "auto" and not args.strict


def test_one_failing_post_does_not_stop_the_batch(tmp_path, monkeypatch, capsys):
    import requests

    from histposts import cli
    from histposts.pipeline import BuildResult

    spec = tmp_path / "p.yaml"
    spec.write_text(
        "posts:\n- {name: a, file: a.jpg, title: T, info: I}\n- {name: b, file: b.jpg, title: T, info: I}\n",
        encoding="utf-8",
    )

    def fake_build(post, folder, *args, **kwargs):
        if post.name == "a":
            raise requests.ConnectionError("boom")
        return BuildResult(post.name, "safe", "gentle", path=folder)

    monkeypatch.setattr(cli, "build_post", fake_build)
    monkeypatch.chdir(tmp_path)
    assert main(["build", str(spec), "--out", str(tmp_path / "out")]) == 1
    out = capsys.readouterr().out
    assert "FAILED" in out and "1/2 posts written" in out
    assert "cached" in out


def test_only_keeps_position_numbering_and_merges_the_report(tmp_path, monkeypatch, capsys):
    import json

    from histposts import cli
    from histposts.pipeline import BuildResult

    spec = tmp_path / "p.yaml"
    spec.write_text(
        "posts:\n- {name: a, file: a.jpg, title: T, info: I}\n- {name: b, file: b.jpg, title: T, info: I}\n",
        encoding="utf-8",
    )
    seen = []

    def fake_build(post, folder, *args, **kwargs):
        seen.append(folder.name)
        return BuildResult(post.name, "safe", "gentle", path=folder)

    monkeypatch.setattr(cli, "build_post", fake_build)
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "out"
    assert main(["build", str(spec), "--out", str(out)]) == 0
    assert main(["build", str(spec), "--out", str(out), "--only", "b"]) == 0
    assert seen == ["01-a", "02-b", "02-b"]
    report = json.loads((out / "license_report.json").read_text(encoding="utf-8"))
    assert sorted(r["name"] for r in report) == ["a", "b"]
    assert "1/1 posts written" in capsys.readouterr().out
