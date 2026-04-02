# Publishing

sqldbagent uses PDM for local package builds and publish flows.

## Local Build

```bash
make build
make publish-check
```

This builds both the wheel and sdist, then validates the distribution metadata with `twine check`.

## Publish from a Workstation

```bash
make publish-testpypi
make publish-pypi
```

`pdm publish` builds and uploads distributions. For PyPI token-based publishing, use `__token__` as the username and the API token as the password in your PyPI configuration.

## GitHub Release Flow

The repo includes a trusted-publishing GitHub Actions workflow for tagged releases. To use it:

1. Configure the project on PyPI as a trusted publisher for this GitHub repository.
2. Push a version tag like `v0.1.0`.
3. Let the workflow build the distributions and publish them through PyPI's OIDC trust path.

## Documentation Build

The Sphinx docs are built from `docs/source/conf.py` and can also be used by Read the Docs through the repo-root `.readthedocs.yaml`.
