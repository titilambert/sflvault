define package-clean
	rm -rf $(1)/dist
	rm -rf $(1)/deb_dist
	rm -rf $(1)/*.egg-info
endef

define package-distclean
	rm -rf $(DIR_RPM)/$(PKG_PREFIX)$(1)
	rm -rf $(DIR_DEB)/$(PKG_PREFIX)$(1)
endef

define package-deb-src
	mkdir -pv $(1)/debian
	cp build-scripts/pydist-overrides $(1)/debian/
	cd $(1) && python setup.py --command-packages=stdeb.command sdist_dsc
	rm -rf $(1)/debian
	mkdir -pv $(DIR_DEB)/$(PKG_PREFIX)$(1)
	cp -vf $(1)/deb_dist/$(PKG_PREFIX)$(1)*.tar.gz $(DIR_DEB)/$(PKG_PREFIX)$(1)/
	cp -vf $(1)/deb_dist/$(PKG_PREFIX)$(1)*.dsc    $(DIR_DEB)/$(PKG_PREFIX)$(1)/
endef

define package-rpm-src
	cd $(1) && python setup.py bdist_rpm --spec-only
	cd $(1) && python setup.py sdist
	mkdir -pv $(DIR_RPM)/$(PKG_PREFIX)$(1)
	cp -vf $(1)/dist/$(PKG_PREFIX)$(1)*.tar.gz $(DIR_RPM)/$(PKG_PREFIX)$(1)/
	awk -f build-scripts/rpm-insert-to-specs.awk -v part=start $(1)/dist/$(PKG_PREFIX)$(1).spec  >$(DIR_RPM)/$(PKG_PREFIX)$(1)/$(PKG_PREFIX)$(1).spec
	cat $(1)/specs.append                                                                       >>$(DIR_RPM)/$(PKG_PREFIX)$(1)/$(PKG_PREFIX)$(1).spec
	awk -f build-scripts/rpm-insert-to-specs.awk -v part=end   $(1)/dist/$(PKG_PREFIX)$(1).spec >>$(DIR_RPM)/$(PKG_PREFIX)$(1)/$(PKG_PREFIX)$(1).spec
endef

define package-rpm-bin
	@echo "Not implemented"
endef

define package-deb-bin
	mkdir $(1)/debian
	cp build-scripts/pydist-overrides $(1)/debian/
	cd $(1) && python setup.py --command-packages=stdeb.command bdist_deb
	rm -rf $(1)/debian
	mkdir -pv $(DIR_DEB)/$(PKG_PREFIX)$(1)
	cp -vf $(1)/deb_dist/$(PKG_PREFIX)$(1)*.deb $(DIR_DEB)/$(PKG_PREFIX)$(1)/
endef
