# test - testing with pytest and tox

testfiles ?= $(wildcard tests/test_*.py)
options ?= -x
options := $(if $(test),$(options) -k $(test),$(options))

# run pytest;  example: make options=-svvvx test=cli test 
test:
	env TESTING=1 pytest $(options) --log-cli-level=ERROR $(testfiles)

# run pytest, dropping into pdb on exceptions or breakpoints
debug:
	env TESTING=1 DEBUGGER=1 pytest $(options) -vvs --log-cli-level INFO --pdb $(testfiles)

# check code coverage quickly with the default Python
coverage:
	env TESTING=1 coverage run --source $(module) -m pytest
	coverage report -m
	coverage html
	$(browser) htmlcov/index.html

# show available test cases 
testls:
	@echo $$($(foreach test,$(testfiles),grep -o '^def test_[[:graph:]]*' $(test);)) |\
	  tr ' ' '\n' | grep -v def | awk -F\( 'BEGIN{xi=0} {printf("%s",$$1);\
	  if(++xi==3){xi=0; printf("\n");} else {printf("\t");}}' |\
	  awk 'BEGIN{print ".TS\nbox,nowarn;\nl | l | l ." } {print} END{print ".TE";}' |\
	  tbl | groff  -T utf8 | awk 'NF';

# test with tox if sources have changed
.PHONY: tox
tox: .tox 
.tox: $(python_src) tox.ini
	tox
	@touch $@

