Name:           kohaku-tabletd
Version:        0.5.1
Release:        1%{?dist}
Summary:        Tablet-mode aware display scaling with a single D-Bus control daemon
License:        MIT
URL:            https://github.com/greedgoddess/kohaku-tabletd
Source0:        %{url}/archive/v%{version}/%{name}-%{version}.tar.gz
BuildArch:      noarch

BuildRequires:  make
BuildRequires:  python3-devel
BuildRequires:  systemd-rpm-macros
BuildRequires:  desktop-file-utils
BuildRequires:  libappstream-glib
Requires:       python3
Requires:       python3-gobject
Requires:       gtk4
Requires:       libadwaita
Requires:       systemd-udev

%description
A user-level daemon that watches the kernel tablet-mode switch, switches the
display scale between a laptop and a tablet value, and exposes a D-Bus API and
CLI (toggle, laptop, tablet, auto, status) so keyboard shortcuts and other
tools all go through one control instance, plus a settings window for the
scales, recent trigger sources and a caller blocklist.

%prep
%autosetup

%build

%install
%make_install PREFIX=%{_prefix} SYSCONFDIR=%{_sysconfdir}
%py_byte_compile %{python3} %{buildroot}%{_prefix}/lib/%{name}

# [doc:spec-check]
%check
make check
desktop-file-validate %{buildroot}%{_datadir}/applications/io.github.greedgoddess.KohakuTabletd.Settings.desktop
appstream-util validate-relax --nonet %{buildroot}%{_metainfodir}/io.github.greedgoddess.KohakuTabletd.Settings.metainfo.xml

# [doc:spec-post]
%post
%systemd_user_post %{name}.service
%udev_rules_update
udevadm trigger --subsystem-match=input --property-match=ID_INPUT_SWITCH=1 >/dev/null 2>&1 || :

%preun
%systemd_user_preun %{name}.service

%postun
%udev_rules_update

%files
%license LICENSE
%doc README.md docs/CODE.md data/keyd-example.conf
%{_bindir}/%{name}
%{_prefix}/lib/%{name}/
%{_userunitdir}/%{name}.service
%{_userpresetdir}/80-%{name}.preset
%{_datadir}/dbus-1/services/io.github.greedgoddess.KohakuTabletd.service
%{_udevrulesdir}/70-%{name}.rules
%{_datadir}/applications/io.github.greedgoddess.KohakuTabletd.Settings.desktop
%{_metainfodir}/io.github.greedgoddess.KohakuTabletd.Settings.metainfo.xml
%{_datadir}/icons/hicolor/scalable/apps/io.github.greedgoddess.KohakuTabletd.Settings.svg
%{_datadir}/icons/hicolor/symbolic/apps/io.github.greedgoddess.KohakuTabletd.Settings-symbolic.svg
%dir %{_sysconfdir}/%{name}
%config(noreplace) %{_sysconfdir}/%{name}/config.toml

%changelog
* Mon Nov 09 2026 greedgoddess <352940295+greedgoddess@users.noreply.github.com> - 0.5.1-1
- Recent calls: hint and link on how to trigger a call

* Mon Nov 09 2026 greedgoddess <352940295+greedgoddess@users.noreply.github.com> - 0.5.0-1
- Registered as an app: own icon, AppStream metadata

* Mon Nov 09 2026 greedgoddess <352940295+greedgoddess@users.noreply.github.com> - 0.4.0-1
- Default scale is GNOME's saved display scale; changing it asks for confirmation
- Recent callers: identify detached callers (keyd) by their systemd unit

* Mon Nov 09 2026 greedgoddess <352940295+greedgoddess@users.noreply.github.com> - 0.3.0-1
- About tab with GitHub link
- Optional daily update check against GitHub releases with desktop notification

* Mon Nov 09 2026 greedgoddess <352940295+greedgoddess@users.noreply.github.com> - 0.2.0-1
- Settings window: default/temporary scale, recent trigger sources, blocklist
- Trigger API records callers and refuses blocked sources

* Mon Nov 09 2026 greedgoddess <352940295+greedgoddess@users.noreply.github.com> - 0.1.1-1
- Apply scale as temporary config so GNOME no longer asks to keep changes

* Mon Nov 09 2026 greedgoddess <352940295+greedgoddess@users.noreply.github.com> - 0.1.0-1
- Initial package
