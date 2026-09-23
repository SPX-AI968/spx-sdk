# Publishing to PyPI

Distribution: `simplex-ai-sdk`. Python import: `simplex_ai`. Repository: `SPX-AI968/spx-sdk`.

`spx-sdk` on PyPI is an unrelated existing package. Availability of the chosen name must be checked again at publication; a 404 does not reserve it.

1. Review the release and update the version in `pyproject.toml`, `src/simplex_ai/__init__.py`, and the User-Agent in `src/simplex_ai/client.py` together.
2. Start from a clean checkout and a fresh virtual environment:

   ```bash
   python -m pip install -e '.[dev]'
   pytest
   ruff check .
   mypy src/simplex_ai
   python -m build
   python -m twine check dist/*
   ```

3. Install the generated wheel in a separate environment and check the import. Run `examples/smoke.py` with a real `SIMPLEX_API_TOKEN` if desired. The smoke test makes an inference request and consumes API usage.
4. Sign in to the correct PyPI account, enable its required authentication, and create a publication token. Do not commit the token or put it in shell history. Use Twine's interactive credential prompt or a secure environment/secret store.
5. Upload exactly the new wheel and sdist (replace the version below for later releases):

   ```bash
   python -m twine upload dist/simplex_ai_sdk-0.1.0-py3-none-any.whl dist/simplex_ai_sdk-0.1.0.tar.gz
   ```

6. After upload succeeds, verify `pip install simplex-ai-sdk==0.1.0` in a fresh environment. Tag the reviewed commit as `v0.1.0` and publish release notes on GitHub. PyPI versions cannot be overwritten.

The CI workflow tests and builds only. It does not publish to PyPI or require publication credentials.
