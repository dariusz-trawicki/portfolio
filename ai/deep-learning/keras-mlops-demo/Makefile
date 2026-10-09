export PYTHONPATH := src
PY ?= python

.PHONY: install train serve test mlflow-ui drift-ok drift-alert registry rollback figures clean

install:            ## install the project with dev dependencies
	pip install -e ".[dev]"

train:              ## train + quality gate + promote to production (if the gate passes)
	$(PY) -m mlops_demo.train --promote

serve:              ## start the API on http://localhost:8000 (docs: /docs)
	uvicorn mlops_demo.serve:app --port 8000

test:               ## unit and integration tests
	$(PY) -m pytest -q

mlflow-ui:          ## experiment browser on http://localhost:5000
	@# $(PY) -m mlflow rather than a bare `mlflow`: the UI must use THE SAME MLflow as training,
	@# otherwise an older version cannot open a database created by a newer one.
	$(PY) -m mlflow ui --backend-store-uri sqlite:///mlflow.db --port 5000

drift-ok:           ## normal traffic, monitoring should stay quiet
	$(PY) -m mlops_demo.simulate --n 1500 --drift 0.0 --reset
	$(PY) -m mlops_demo.monitor --window 1500

drift-alert:        ## traffic after the "world" changed, monitoring should ALERT (exit code 1)
	$(PY) -m mlops_demo.simulate --n 1500 --drift 0.8 --reset
	-$(PY) -m mlops_demo.monitor --window 1500

registry:           ## show which version is in production
	$(PY) -m mlops_demo.registry show

rollback:           ## roll back to the previous production version
	$(PY) -m mlops_demo.registry rollback

figures:            ## regenerate README figures (needs: uv sync --extra figures)
	$(PY) scripts/make_figures.py

clean:              ## remove artifacts, the MLflow database and caches
	rm -rf artifacts mlruns mlflow.db exp .pytest_cache dist
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
