# Copyright (C) 2022 Bitsy AI Labs
#
# Author: Leigh Johnson <leigh@bitsy.ai>
#
# This file is part of cloud-init. See LICENSE file for license information.

from cloudinit import distros, helpers
from cloudinit import log as logging
from cloudinit import subp, util
from cloudinit.settings import PER_INSTANCE
from cloudinit.distros.parsers.hostname import HostnameConf

LOG = logging.getLogger(__name__)

NETWORK_FILE_HEADER = """\
# This file is generated from information provided by the datasource.  Changes
# to it will not persist across an instance reboot.  To disable cloud-init's
# network configuration capabilities, write a file
# /etc/cloud/cloud.cfg.d/99-disable-network-config.cfg with the following:
# network: {config: disabled}
"""

class Distro(distros.Distro):
    """
    BitsyLinux is an OpenEmbedded Linux distribution based on the Yocto Project
    """

    init_cmd = ["systemctl"]
    network_conf_dir = "/etc/systemd/network/"
    network_conf_fn = {
        "eni": "/etc/network/interfaces.d/50-cloud-init.cfg",
        "netplan": "/etc/netplan/50-cloud-init.yaml",
    }
    resolve_conf_fn = "/etc/systemd/resolved.conf"
    systemd_locale_conf_fn = "/etc/locale.conf"
    renderer_configs = {
        "networkd": {
            "resolv_conf_fn": resolve_conf_fn,
            "network_conf_dir": network_conf_dir,
        },
        "netplan": {
            "netplan_path": network_conf_fn["netplan"],
            "netplan_header": NETWORK_FILE_HEADER,
            "postcmds": True,
        },
    }

    def __init__(self, name, cfg, paths):
        distros.Distro.__init__(self, name, cfg, paths)
        # This will be used to restrict certain
        # calls from repeatly happening (when they
        # should only happen say once per instance...)
        self._runner = helpers.Runners(paths)
        self.osfamily = "bitsy"
        self.default_locale = "en_US.UTF-8"
        self.system_locale = None
        cfg["ssh_svcname"] = "sshd.socket"

    def _read_system_hostname(self):
        sys_hostname = self._read_hostname(self.hostname_conf_fn)
        return (self.hostname_conf_fn, sys_hostname)

    def _read_hostname_conf(self, filename) -> HostnameConf:
        conf = HostnameConf(util.load_file(filename))
        conf.parse()
        return conf

    def _write_hostname(self, hostname, filename) -> None:
        conf = None
        try:
            # Try to update the previous one
            # so lets see if we can read it first.
            conf = self._read_hostname_conf(filename)
        except IOError as e:
            LOG.error("Error opening file %s - %s", filename, e)
        if not conf:
            conf = HostnameConf("")
        conf.set_hostname(hostname)
        util.write_file(filename, str(conf), omode="w", mode=0o644)

    def _read_hostname(self, filename, default=None):
        hostname = None
        try:
            conf: HostnameConf = self._read_hostname_conf(filename)
            hostname = conf.hostname
        except IOError as e:
            LOG.error("Error opening file %s - %s", filename, e)
        if not hostname:
            return default
        return hostname

    def apply_locale(self, locale, out_fn=None):
        if out_fn is not None and out_fn != "/etc/locale.conf":
            LOG.warning(
                "Invalid locale_configfile %s, only supported "
                "value is /etc/locale.conf",
                out_fn,
            )
        cmd = ["localectl", "set-locale", locale]
        subp.subp(cmd, capture=False)


    def install_packages(self, pkglist):
        self.package_command("install", pkgs=pkglist)

    def package_command(self, command, args=None, pkgs=None):
        if pkgs is None:
            pkgs = []

        cmd = ["dnf", "-y"]
        if args and isinstance(args, str):
            cmd.append(args)
        elif args and isinstance(args, list):
            cmd.extend(args)

        cmd.append(command)

        pkglist = util.expand_package_list("%s-%s", pkgs)
        cmd.extend(pkglist)

        # Allow the output of this to flow outwards (ie not be captured)
        subp.subp(cmd, capture=False)

    def set_timezone(self, tz):
        cmd = ["timedatectl", "set-timezone", tz]
        subp.subp(cmd, capture=False)

    def update_package_sources(self):
        self._runner.run(
            "update-sources",
            self.package_command,
            ["makecache"],
            freq=PER_INSTANCE,
        )
