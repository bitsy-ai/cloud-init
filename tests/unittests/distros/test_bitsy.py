# This file is part of cloud-init. See LICENSE file for license information.
from unittest.mock import patch
from cloudinit.distros.parsers import hosts
from tests.unittests.helpers import CiTestCase
from . import _get_distro


EXPECTED_HOSTNAME = "mockhostname"
EXPECTED_FQDN = "{}.org.bitsy.ai".format(EXPECTED_HOSTNAME)
EXPECTED_HOSTS = """
# This file /etc/cloud/templates/hosts.bitsy.tmpl is only utilized
# if enabled in cloud-config.  Specifically, in order to enable it
# you need to add the following to config:
# manage_etc_hosts: True
#
# Your system has configured 'manage_etc_hosts' as True.
# As a result, if you wish for changes to this file to persist
# then you will need to either
# a.) make changes to the main file in /etc/cloud/templates/hosts.bitsy.tmpl
# b.) change or remove the value of 'manage_etc_hosts' in
#     /etc/cloud/cloud.cfg or cloud-config from user-data
#
# The following lines are desirable for IPv4 capable hosts
127.0.1.1 {hostname} {fqdn}
127.0.0.1 localhost

# The following lines are desirable for IPv6 capable hosts
::1 ip6-localhost ip6-loopback
fe00::0 ip6-localnet
ff00::0 ip6-mcastprefix
ff02::1 ip6-allnodes
ff02::2 ip6-allrouters
""".format(hostname=EXPECTED_HOSTNAME, fqdn=EXPECTED_FQDN)
BASE_ETC = EXPECTED_HOSTS.strip()


SYSTEM_INFO = {
    "paths": {
        "cloud_dir": "/var/lib/cloud/",
        "templates_dir": "/etc/cloud/templates/",
    },
    "network": {"renderers": "networkd"},
}


class TestBitsyDistro(CiTestCase):
    with_logs = True
    distro = _get_distro("bitsy", SYSTEM_INFO)
    def test_parse_etc_hosts(self):
        eh = hosts.HostsConf(BASE_ETC)
        self.assertEqual(eh.get_entry("127.0.0.1"), [["localhost"]])
        self.assertEqual(
            eh.get_entry("127.0.1.1"),
            [[EXPECTED_HOSTNAME, EXPECTED_FQDN]],
        )
        eh = str(eh)

    @patch("cloudinit.util.write_file")
    def test_add_etc_hosts(self, mock_write_file):
        eh = hosts.HostsConf(BASE_ETC)
        with patch("cloudinit.distros.hosts.HostsConf") as mock_hostsconf:
            mock_hostsconf.return_value = eh
            expected_hostname = "foo"
            expected_fqdn = "foo.mock.com"
            self.distro.update_etc_hosts(expected_hostname, expected_fqdn)

            self.assertTrue(mock_write_file.called)
            (hosts_file, contents), _ = mock_write_file.call_args
            nh = hosts.HostsConf(contents)
            self.assertEqual(hosts_file, "/etc/hosts")
            self.assertEqual(nh.get_entry("127.0.0.1"), [['localhost'],[expected_fqdn, expected_hostname]])
