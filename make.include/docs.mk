# make clean targets

# generate Sphinx HTML documentation, including API docs
#
install-docs:
	pip install -U .[docs]

docs: install-docs clean-docs
	sphinx-apidoc -o docs/ $(project)
	$(MAKE) -C docs html
	$(browser) docs/_build/html/index.html

# clean up documentation files
clean-docs:
	rm -f docs/$(project).rst
	rm -f docs/modules.rst
	$(MAKE) -C docs clean

# run a dev-mode docs webserver; recompiling on changes 
servedocs: docs
	watchmedo shell-command -p '*.rst' -c '$(MAKE) -C docs html' -R -D .
