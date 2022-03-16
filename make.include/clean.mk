# make clean targets


# clean all
clean-clean: clean-build clean-pyc clean-test

# remove build artifacts
clean-build: 
	rm -fr build/
	rm -fr dist/
	rm -fr wheels/
	rm -fr .eggs/
	find . -name '*.egg-info' -exec rm -fr {} +
	find . -name '*.egg' -exec rm -f {} +

# remove Python file artifacts
clean-pyc: 
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

# remove test and coverage artifacts
clean-test: 
	rm -f pytest.log
	rm -fr .tox/
	rm -f .coverage
	rm -fr htmlcov/
	rm -fr .pytest_cache
