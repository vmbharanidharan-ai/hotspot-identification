# Publishing pmhc-hotspot

## PyPI (pip)

```bash
pip install build twine
python -m build
twine check dist/*
twine upload dist/*   # requires PYPI_API_TOKEN
```

Install from TestPyPI first when validating a release:

```bash
twine upload --repository testpypi dist/*
pip install -i https://test.pypi.org/simple/ pmhc-hotspot
```

## conda-forge

The base package is **noarch** pure Python. Submit a feedstock with `conda/meta.yaml` as the starting recipe.

1. Fork `conda-forge/staged-recipes`
2. Add a `pmhc-hotspot` recipe pointing at the GitHub release tarball or PyPI sdist
3. Pin runtime deps: `python`, `numpy`, `scipy`, `pandas`, `biopython`, `click`, `pyyaml`
4. Keep ML extras (`xgboost`, `scikit-learn`) out of the base feedstock unless publishing a variant

Local conda build:

```bash
conda build conda/
```

## GitHub release automation

Tag a release to trigger `.github/workflows/release.yml`:

```bash
git tag v0.2.0
git push origin v0.2.0
```

Set repository secret `PYPI_API_TOKEN` before enabling automated uploads.
