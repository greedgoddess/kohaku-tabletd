NAME       := kohaku-tabletd
VERSION    := $(shell sed -n 's/^__version__ = "\(.*\)"/\1/p' src/kohaku_tabletd/__init__.py)
PREFIX     ?= /usr
SYSCONFDIR ?= /etc
LIBDIR     ?= $(PREFIX)/lib/$(NAME)
RPMDIR     := $(CURDIR)/rpmbuild

.PHONY: install check dist rpm version clean

# [doc:mk-install]
install:
	install -d $(DESTDIR)$(LIBDIR)/kohaku_tabletd
	install -m 644 src/kohaku_tabletd/*.py $(DESTDIR)$(LIBDIR)/kohaku_tabletd/
	install -d $(DESTDIR)$(PREFIX)/bin
	sed 's|@LIBDIR@|$(LIBDIR)|' bin/$(NAME).in > $(DESTDIR)$(PREFIX)/bin/$(NAME)
	chmod 755 $(DESTDIR)$(PREFIX)/bin/$(NAME)
	install -Dm 644 data/$(NAME).service $(DESTDIR)$(PREFIX)/lib/systemd/user/$(NAME).service
	install -Dm 644 data/80-$(NAME).preset $(DESTDIR)$(PREFIX)/lib/systemd/user-preset/80-$(NAME).preset
	install -Dm 644 data/io.github.greedgoddess.KohakuTabletd.service \
	  $(DESTDIR)$(PREFIX)/share/dbus-1/services/io.github.greedgoddess.KohakuTabletd.service
	install -Dm 644 data/70-$(NAME).rules $(DESTDIR)$(PREFIX)/lib/udev/rules.d/70-$(NAME).rules
	install -Dm 644 data/config.toml $(DESTDIR)$(SYSCONFDIR)/$(NAME)/config.toml
	install -Dm 644 data/io.github.greedgoddess.KohakuTabletd.Settings.desktop \
	  $(DESTDIR)$(PREFIX)/share/applications/io.github.greedgoddess.KohakuTabletd.Settings.desktop

# [doc:mk-check]
check:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

# [doc:mk-rpm]
dist:
	git archive --format=tar.gz --prefix=$(NAME)-$(VERSION)/ -o $(NAME)-$(VERSION).tar.gz HEAD

rpm: dist
	rpmbuild -ba packaging/$(NAME).spec \
	  --define "_topdir $(RPMDIR)" --define "_sourcedir $(CURDIR)"

version:
	@echo $(VERSION)

clean:
	rm -rf $(RPMDIR) $(NAME)-*.tar.gz
