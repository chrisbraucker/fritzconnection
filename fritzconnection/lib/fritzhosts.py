"""
Module to access and control the known hosts.
"""
# This module is part of the FritzConnection package.
# https://github.com/kbr/fritzconnection
# License: MIT (https://opensource.org/licenses/MIT)
# Author: Klaus Bremer


from __future__ import annotations

import itertools

try:
    from typing import Generator
except ImportError:
    from collections.abc import Generator

from ..core.exceptions import (
    FritzActionError,
    FritzArgumentError,
    FritzLookUpError,
)
from ..core.processor import HostStorage
from ..core.utils import get_xml_root
from .fritzbase import AbstractLibraryBase


SERVICE = "Hosts1"


class FritzHosts(AbstractLibraryBase):
    """
    Class to access the registered hosts. All parameters are optional. If
    given, they have the following meaning: `fc` is an instance of
    FritzConnection, `address` the ip of the Fritz!Box, `port` the port
    to connect to, `user` the username, `password` the password,
    `timeout` a timeout as floating point number in seconds, `use_tls` a
    boolean indicating to use TLS (default False).
    """

    def _action(self, actionname, *, arguments=None, **kwargs):
        return self.fc.call_action(SERVICE, actionname, arguments=arguments, **kwargs)

    @property
    def host_numbers(self) -> int:
        """The number of known hosts."""
        result = self._action("GetHostNumberOfEntries")
        return result["NewHostNumberOfEntries"]

    def get_generic_host_entry(self, index: int) -> dict:
        """
        Returns a dictionary with information about a device internally
        registered by the position *index*. Index-positions are
        zero-based.
        """
        return self._action("GetGenericHostEntry", NewIndex=index)

    def get_generic_host_entries(self) -> Generator[dict, None, None]:
        """
        Generator returning a dictionary for every host as provided by
        `get_generic_host_entry()`. (See also `get_hosts_info()` that
        returns a list of dictionaries with different key-names.)
        """
        for index in itertools.count():
            try:
                yield self.get_generic_host_entry(index)
            except IndexError:
                break

    def get_specific_host_entry(self, mac_address: str) -> dict:
        """
        Returns a dictionary with information about a device addressed
        by the MAC-address.
        """
        return self._action("GetSpecificHostEntry", NewMACAddress=mac_address)

    def get_specific_host_entry_by_ip(self, ip: str) -> dict:
        """
        Returns a dictionary with information about a device addressed
        by the ip-address. Provides additional information about
        connection speed and system-updates for AVM devices.
        """
        return self._action("X_AVM-DE_GetSpecificHostEntryByIP", NewIPAddress=ip)

    def get_host_status(self, mac_address: str) -> bool | None:
        """
        Provides status information about the device with the given
        `mac_address`. Returns `True` if the device is active or `False`
        otherwise. Returns `None` if the device is not known or the
        `mac_address` is invalid.
        """
        try:
            result = self.get_specific_host_entry(mac_address)
        except (FritzArgumentError, FritzLookUpError):
            return None
        return result["NewActive"]

    def get_active_hosts(self) -> list[dict]:
        """
        Returns a list of dicts with information about the active
        devices. The dict-keys are: 'ip', 'name', 'mac', 'status',
        'interface_type', 'address_source', 'lease_time_remaining'
        """
        return [host for host in self.get_hosts_info() if host["status"]]

    def get_hosts_info(self) -> list[dict]:
        """
        Returns a list of dicts with information about the known hosts.
        The dict-keys are: 'ip', 'name', 'mac', 'status',
        'interface_type', 'address_source', 'lease_time_remaining'.
        """
        result = []
        for index in itertools.count():
            try:
                host = self.get_generic_host_entry(index)
            except IndexError:
                # no more host entries:
                break
            result.append(
                {
                    "ip": host["NewIPAddress"],
                    "name": host["NewHostName"],
                    "mac": host["NewMACAddress"],
                    "status": host["NewActive"],
                    "interface_type": host["NewInterfaceType"],
                    "address_source": host["NewAddressSource"],
                    "lease_time_remaining": host["NewLeaseTimeRemaining"],
                }
            )
        return result

    def get_mesh_topology(self, raw=False) -> dict | str:
        """
        Returns information about the mesh network topology. If `raw` is
        `False` the topology gets returned as a dictionary with a list
        of nodes. If `raw` is `True` the data are returned as text in
        json format. Default is `False`.
        """
        result = self._action("X_AVM-DE_GetMeshListPath")
        path = result["NewX_AVM-DE_MeshListPath"]
        url = f"{self.fc.address}:{self.fc.port}{path}"
        with self.fc.session.get(url) as response:
            if not response.ok:
                message = f"Error {response.status_code}: Device has no access to topology information."
                raise FritzActionError(message)
            return response.text if raw else response.json()

    def get_wakeonlan_status(self, mac_address: str) -> bool:
        """
        Returns a boolean whether wake on LAN signal gets send to the
        device with the given `mac_address` in case of a remote access.
        """
        info = self._action(
            "X_AVM-DE_GetAutoWakeOnLANByMACAddress", NewMACAddress=mac_address
        )
        return info["NewAutoWOLEnabled"]

    def set_wakeonlan_status(self, mac_address: str, status: bool = False) -> None:
        """
        Sets whether a wake on LAN signal should get send send to the
        device with the given `mac_address` in case of a remote access.
        `status` is a boolean, default value is `False`. This method has
        no return value.
        """
        args = {
            "NewMACAddress": mac_address,
            "NewAutoWOLEnabled": status,
        }
        self._action("X_AVM-DE_SetAutoWakeOnLANByMACAddress", arguments=args)

    def wakeonlan_host(self, mac_address: str) -> None:
        """
        Triggers sending a wake on lan message with the given `mac_address`
        on the local network. This method has no return value.
        """
        self._action("X_AVM-DE_WakeOnLANByMACAddress", NewMACAddress=mac_address)

    def set_host_name(self, mac_address: str, name: str) -> None:
        """
        Sets the hostname of the device with the given `mac_address` to
        the new `name`.
        """
        args = {
            "NewMACAddress": mac_address,
            "NewHostName": name,
        }
        self._action("X_AVM-DE_SetHostNameByMACAddress", arguments=args)

    def get_host_name(self, mac_address: str) -> str:
        """
        Returns a String with the host_name of the device with the given
        mac_address
        """
        return self.get_specific_host_entry(mac_address)["NewHostName"]

    def run_host_update(self, mac_address: str) -> None:
        """
        Triggers the host with the given `mac_address` to run a system
        update. The method returns immediately, but for the device it
        takes some time to do the OS update. All vendor warnings about running a
        system update apply, like not turning power off during a system
        update. So run this command with caution.
        """
        self._action("X_AVM-DE_HostDoUpdate", NewMACAddress=mac_address)

    def get_hosts_attributes(self) -> list[dict]:
        """
        Returns a list of dictionaries with information about all hosts.

        This differs from `get_hosts_info` as the information origins
        from a different FritzOS call: the information about the current
        host stats is provided by a Lua script returning an xml-stream.
        `get_hosts_attributes` triggers the Lua script and converts the
        returned data in a list of dictionaries describing the known
        hosts.

        .. versionadded:: 1.10
        """
        result = self._action("X_AVM-DE_GetHostListPath")
        path = result["NewX_AVM-DE_HostListPath"]
        url = f"{self.fc.address}:{self.fc.port}{path}"
        storage = HostStorage(get_xml_root(source=url, session=self.fc.session))
        return storage.hosts_attributes
