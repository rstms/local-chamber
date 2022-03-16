# top-level Makefile 

# remove module from the local python environment
uninstall: 
	pip uninstall -yqq $(project)

# install to the local environment from the source directory
install: 
	pip install --upgrade .

# local install in editable mode for development
dev: uninstall 
	pip install --upgrade -e .[dev]

# remove all build, test, coverage and Python artifacts
clean: 
	for clean in $(call included,clean); do ${MAKE} $$clean; done

include $(wildcard make.include/*.mk)
