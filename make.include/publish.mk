# publish - build package and publish

# create distributable files if sources have changed
.PHONY: dist 
dist: .dist
.dist:	gitclean tox
	@echo Building $(project)
	pip wheel -w dist .
	@touch $@

release_args = '{\
  "tag_name": "v$(version)",\
  "target_commitish": "$(branch)",\
  "name": "v$(version)",\
  "body": "Release of version $(version)",\
  "draft": false,\
  "prerelease": false\
}'
release_url = https://api.github.com/repos/$(organization)/$(project)/releases
release_header = -H 'Authorization: token ${GITHUB_TOKEN}'

# create a github release from the current version
release: dist 
	@echo pushing Release $(project) v$(version) to github...
	curl $(release_header) --data $(release_args) $(release_url)

# publish to pypi
publish: release
	$(call require_pypi_config)
	@set -e;\
	if [ "$(version)" != "$(pypi_version)" ]; then \
	  $(call verify_action,publish to PyPi) \
	  echo publishing $(project) $(version) to PyPI...;\
	  flit publish;\
	else \
	  echo $(project) $(version) is up-to-date on PyPI;\
	fi

# check current pypi version 
pypi-check:
	$(call require_pypi_config)
	@echo '$(project) local=$(version) pypi=$(call check_pypi_version)'

# clean up publish generated files
publish-clean:
	rm -f .dist
	rm -rf .tox

# functions
define require_pypi_config =
$(if $(wildcard ~/.pypirc),,$(error publish failed; ~/.pypirc required))
endef

pypi_version := $(shell pip install $(project)==fnord.plough.plover.xyzzy 2>&1 |\
  awk -F'[,() ]' '/^ERROR: Could not find a version .* \(from versions:.*\)/{print $$(NF-1)}')

define check_null =
$(if $(1),$(1),$(error $(2)))
endef

check_pypi_version = $(call check_null,$(pypi_version),PyPi version query failed)
