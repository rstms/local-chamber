# version - automatic version management
 
# - Prevent version changes with uncommited changes
# - tag and commit version changes
# - Use 'lightweight tags'


bumpversion = bumpversion $(1) --allow-dirty --commit --tag --current-version $(version) \
  --search '__version__ = "{current_version}"' --replace '__version__ = "{new_version}"' \
  $(project)/version.py

# bump patch level
bump-patch: timestamp
	$(call bumpversion,patch)
	git push

# bump minor version, reset patch to zero
bump-minor: timestamp
	$(call bumpversion,minor)
	git push
	
# bump version, reset minor and patch to zero
bump-major: timestamp
	$(call bumpversion,major)
	git push

# update timestamp if sources have changed
timestamp: .timestamp 
.timestamp: $(src) gitclean
	sed -E -i $(project)/version.py -e "s/(.*__timestamp__.*=).*/\1 \"$$(date --rfc-3339=seconds)\"/"
	git add $(project)/version.py
	@touch $@
	@echo "Timestamp Updated."

# clean up version tempfiles
version-clean:
	rm -f .timestamp
