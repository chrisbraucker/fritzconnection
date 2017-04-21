# -*- coding: utf-8 -*-

"""
Utility module for FritzConnection to list and switch the known callforwardings.

License: MIT https://opensource.org/licenses/MIT
Author: Julian Tatsch
"""

import os
import argparse

# tiny hack to run this as a package but also from the command line. In
# the latter case ValueError is raised from python 2.7 and SystemError
# from Python 3.5
try:
    from . import fritzconnection
except (ValueError, SystemError, ImportError):
    import fritzconnection

__version__ = '0.6.4'

SERVICE = 'X_AVM-DE_OnTel'


def get_version():
    """Get the version of the module."""
    return __version__


class FritzCallforwarding(object):
    """The FritzCallForwarding class offers some convenience functions to manage call forwardings.

    It allows to list and switch the known call forwardings of a fritzbox
    """

    def __init__(self,
                 fritz_connection=None,
                 address=fritzconnection.FRITZ_IP_ADDRESS,
                 port=fritzconnection.FRITZ_TCP_PORT,
                 user=fritzconnection.FRITZ_USERNAME,
                 password=''):
        """Initialize a FritzCallforwarding instance."""
        super(FritzCallforwarding, self).__init__()
        if fritz_connection is None:
            fritz_connection = fritzconnection.FritzConnection(address, port, user, password)
        self.fritz_connection = fritz_connection
        self.service = 1

    def action(self, actionname, **kwargs):
        """A wrapper to perform an action on a service."""
        return self.fritz_connection.call_action(SERVICE+':'+str(self.service),
                                                 actionname, **kwargs)

    @property
    def modelname(self):
        """Get the total number of call forwardings from the fritzbox."""
        return self.fritz_connection.modelname

    def get_no_call_forwardings(self):
        """Get the total number of call forwardings from the fritzbox."""
        return self.action('GetNumberOfDeflections')['NewNumberOfDeflections']

    def get_call_forwarding_list(self, filter_blocked=True):
        """Get the current deflections list from the fritzbox as unparsed xml blob."""
        raw_deflection_list = self.action('GetDeflections')['NewDeflectionList']
        return parse_call_forwarding_list(raw_deflection_list, filter_blocked)

    def get_call_forwarding_by_uid(self, uid):
        """Get a single CallForwarding dict for a uid.

        The dict-keys are: 'uid', 'from_number', 'to_number', 'connection_type', 'enabled'
        """
        kwargs = {'NewDeflectionId': uid}
        deflection_dict = self.action('GetDeflection', **kwargs)
        return {'uid': uid,
                'from_number': deflection_dict['NewNumber'],
                'to_number': deflection_dict['NewDeflectionToNumber'],
                'connection_type': deflection_dict['NewType'],
                'enabled': int(deflection_dict['NewEnable'])}

    def get_call_forwarding_status_by_uid(self, uid):
        """Get the CallForwarding status for a uid."""
        return self.get_call_forwarding_by_uid(uid)['enabled']

    def set_call_forwarding(self, uid, enable):
        """Enable the call forwarding on the fritzbox for a uid."""
        kwargs = {'NewDeflectionId': uid, 'NewEnable': enable}
        self.action('SetDeflectionEnable', **kwargs)
        return self.get_call_forwarding_status_by_uid(uid)

def parse_call_forwarding_list(call_forwarding_list, filter_blocked=True):
    """Get a list with all CallForwarding Dicts, parse and filter the blocked ones out."""
    import xml.etree.ElementTree as ET
    call_forwardings = []
    element_tree = ET.fromstring(call_forwarding_list)
    for element in element_tree.findall('Item'):
        uid = element.find('DeflectionId').text
        enabled = int(element.find('Enable').text)
        connection_type = element.find('Type').text
        from_number = element.find('Number').text
        to_number = element.find('DeflectionToNumber').text
        if filter_blocked:  # without to numbers (= blocked numbers)
            if to_number is not None:
                call_forwardings.append({'uid': uid,
                                         'from_number': from_number,
                                         'to_number': to_number,
                                         'connection_type': connection_type,
                                         'enabled': enabled})
        else:
            call_forwardings.append({'uid': uid,
                                     'from_number': from_number,
                                     'to_number': to_number,
                                     'connection_type': connection_type,
                                     'enabled': enabled})
    return call_forwardings

# ---------------------------------------------------------
# terminal-output:
# ---------------------------------------------------------


def _print_header(call_forwarding):
    print('\nFritzHosts:')
    print('{:<30}{}'.format('version:', get_version()))
    print('{:<30}{}'.format('model:', call_forwarding.modelname))
    print('{:<30}{}'.format('ip:', call_forwarding.fritz_connection.address))


def print_callforwardings(call_forwarding):
    """Print a nice table with all call forwardings."""
    print('\n{}\n'.format(SERVICE + ':' + str(call_forwarding.service)))
    print('{:>5} {:<15} {:<15} {:<10} {:<9}\n'.format(
        'index', 'from', 'to', 'type', 'status'))
    for call_forwarding_entry in call_forwarding.get_call_forwarding_list():
        status = 'active' if call_forwarding_entry['enabled'] == 1 else 'disabled'
        to_number = '-' if call_forwarding_entry['to_number'] is None else call_forwarding_entry['to_number']
        print('{:>5} {:<15} {:<15} {:<10} {:<9}'.format(
            call_forwarding_entry['uid'],
            call_forwarding_entry['from_number'],
            to_number,
            call_forwarding_entry['connection_type'],
            status
            ))


def _print_detail(call_forwarding, detail, quiet):
    """Print the details of a call forwardings entry."""
    uid = detail[0].lower()
    info = call_forwarding.get_call_forwarding_by_uid(uid)
    if info:
        if not quiet:
            print('\n{:<30}{}'.format('Details for index:', uid))
            print('{:<30}{}{}\n'.format('', SERVICE+':'+str(call_forwarding.service),
                                        call_forwarding.get_no_call_forwardings))
            for key, value in info.items():
                print('{:<30}: {}'.format(key, value))
        else:
            print(info['enabled'])
    else:
        if quiet:
            print('0')


def _print_switch(call_forwarding, switch, quiet):
    """Switch and print the details of a call forwardings entry."""
    uid = switch[0].lower()
    if switch[1].lower() in ['on', 'enable', 'enabled', 'active']:
        call_forwarding.set_call_forwarding(uid, 1)
    else:
        call_forwarding.set_call_forwarding(uid, 0)
    _print_detail(call_forwarding, uid, quiet)


def _print_nums(call_forwarding):
    print('{}: {}'.format(SERVICE+':'+str(call_forwarding.service),
                          call_forwarding.get_no_call_forwardings()))

# ---------------------------------------------------------
# cli-section:
# ---------------------------------------------------------


def _get_cli_arguments():
    parser = argparse.ArgumentParser(description='FritzBox Callforwarding')
    parser.add_argument('-i', '--ip-address',
                        nargs='?', default=os.getenv('FRITZ_IP_ADDRESS',
                                                     fritzconnection.FRITZ_IP_ADDRESS),
                        dest='address',
                        help='ip-address of the FritzBox to connect to. '
                             'Default: %s' % fritzconnection.FRITZ_IP_ADDRESS)
    parser.add_argument('--port',
                        nargs='?', default=os.getenv('FRITZ_TCP_PORT',
                                                     fritzconnection.FRITZ_TCP_PORT),
                        dest='port',
                        help='port of the FritzBox to connect to. '
                             'Default: %s' % fritzconnection.FRITZ_TCP_PORT)
    parser.add_argument('-u', '--username',
                        nargs=1, default=os.getenv('FRITZ_USERNAME',
                                                   fritzconnection.FRITZ_USERNAME),
                        help='Fritzbox authentication username')
    parser.add_argument('-p', '--password', required=True,
                        nargs=1, default=os.getenv('FRITZ_PASSWORD', ''),
                        help='Fritzbox authentication password')
    parser.add_argument('-a', '--all',
                        action='store_true',
                        help='Show all forwardings '
                             '(default if no other options given)')
    parser.add_argument('-n', '--nums',
                        action='store_true',
                        help='Show number of call forwardings')
    parser.add_argument('-d', '--detail',
                        nargs=1, default='',
                        help='Show information about call forwarding at index'
                             '(DETAIL: index)')
    parser.add_argument('-q', '--quiet',
                        action='store_true',
                        help='Quiet mode '
                             '(just return state as 0|1 for a requested index)')
    parser.add_argument('-s', '--switch',
                        nargs=2, default='',
                        help='Enable call forwarding at index'
                        '(e.g. 1 enable)')
    args = parser.parse_args()
    return args


def _print_status(arguments):
    call_forwarding = FritzCallforwarding(address=arguments.address,
                                          port=arguments.port,
                                          user=arguments.username,
                                          password=arguments.password)

    if not arguments.quiet:
        _print_header(call_forwarding)

    if arguments.detail:
        _print_detail(call_forwarding, arguments.detail, arguments.quiet)
    elif arguments.switch:
        _print_switch(call_forwarding, arguments.switch, arguments.quiet)
    elif arguments.nums:
        _print_nums(call_forwarding)
    else:
        print_callforwardings(call_forwarding)


def main():
    """Business logic for the program being run by itself."""
    _print_status(_get_cli_arguments())


if __name__ == '__main__':
    main()
