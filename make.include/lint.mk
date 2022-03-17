# lint / source format

lint_src = $(project) tests docs

# blacken python source (code formatter)
fmt: lint 
	isort $(lint_src)
	black $(lint_src)

# check style, lint with flake8
lint:
	flake8 --config tox.ini $(lint_src)

# vim:ft=make
