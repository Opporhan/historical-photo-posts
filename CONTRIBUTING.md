# Contributing

```bash
pip install -e ".[dev]"
ruff check src tests && ruff format --check src tests && pytest
```

- New photo sources go in `src/histposts/sources/` and return `Candidate` objects.
- New posts go in `posts.yaml`. Only black-and-white or toned, public-domain photographs; every fact in
  `info`/`story` must come from the source record (see `docs/text-verification.md`).
- Changes to `compose.py` need a look at real output (`histposts build posts.yaml --only <name>`), not just tests.
- Before publishing run `histposts verify posts.yaml` and `histposts doctor posts.yaml`; both must be clean.
