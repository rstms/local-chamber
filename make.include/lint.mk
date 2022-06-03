# lint / source format

lint_src = $(module) tests docs

_fmt:
	isort $(lint_src)
	black $(lint_src)
	flake8 --config tox.ini $(lint_src)

# blacken python source (code formatter)
fmt: _fmt

# check style, lint with flake8
lint: _fmt

# vim:ft=make
