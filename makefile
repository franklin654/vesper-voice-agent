.RECIPEPREFIX := >
.PHONY: test eval lint fmt

test:
> uv run pytest -q

eval:
> uv run python -m vesper.eval run --suite smoke

lint:
> uv run ruff check .
> uv run ruff format --check .

fmt:
> uv run ruff format .

