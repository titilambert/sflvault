# -=- encoding: utf-8 -=-
#
# SFLvault - Secure networked password store and credentials manager.
#
# Copyright (C) 2008-2009  Savoir-faire Linux inc.
#
# Author: Alexandre Bourget <alexandre.bourget@savoirfairelinux.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


PROGRAM = "SFLvault"
__version__ = __import__('pkg_resources').get_distribution('SFLvault').version


import optparse
import os
import re
import sys
import xmlrpclib
import getpass
import shlex
import socket
import readline


from Crypto.PublicKey import ElGamal
from base64 import b64decode, b64encode
from datetime import *

from sflvault.client.client import SFLvaultClient
from sflvault.lib.common.crypto import *
from sflvault.lib.common import VaultError
from sflvault.client.utils import *
from sflvault.client import ui

class SFLvaultParserError(Exception):
    """For invalid options on the command line"""
    pass


class ExitParserException(Exception):
    """Tells when the parser showed the help for a command."""
    pass

class NoExitParser(optparse.OptionParser):
    """Simple overriding of error handling, so that no sys.exit() is being
    called

    Reference: http://bugs.python.org/issue3079
    """
    def exit(self, status=0, msg=None):
        if msg:
            sys.stderr.write(msg)
        raise ExitParserException()

    def error(self, msg):
        """error(msg : string)

        Print a usage message incorporating 'msg' to stderr and exit.
        If you override this in a subclass, it should not return -- it
        should either exit or raise an exception.
        """
        self.print_usage(sys.stderr)

class SFLvaultShell(object):
    def __init__(self, vault=None):
        self.vault = (vault or SFLvaultClient(shell=True))

    def _run(self):
        """Go through all commands on a pseudo-shell, and execute them,
        caching the passphrase at some point."""
        
        print "Welcome to SFLvault. Type 'help' for help."
        prompt = "SFLvault> "
        
        while True:
            cmd = raw_input(prompt)
            if not cmd:
                continue
            
            # Get sys.argv-like parameters
            args = shlex.split(cmd)

            # Local (shell) cmds take precedence over SFLvaultCommand cmds.
            if len(args) and hasattr(self, args[0]):
                getattr(self, args[0])()
            else:
                parser = NoExitParser(usage=optparse.SUPPRESS_USAGE)
                runcmd = SFLvaultCommand(self.vault, parser)
                try:
                    runcmd._run(args)
                except ExitParserException, e:
                    pass

    def quit(self):
        """Quit command, only available in the shell"""
        raise KeyboardInterrupt()

    def exit(self):
        """Exit command, only available in the shell"""
        raise KeyboardInterrupt()


class SFLvaultCommand(object):
    """Parse command line arguments, and call SFLvault commands
    on them."""
    def __init__(self, vault=None, parser=None):
        """Setup the SFLvaultParser object.

        argv - arguments from the command line
        sflvault - SFLvault object (optional)"""
        self.parser = (parser or optparse.OptionParser(usage=optparse.SUPPRESS_USAGE))
        
        # Use the specified, or create a new one.
        self.vault = (vault or SFLvaultClient())


    def _run(self, argv):
        """Run a certain command"""
        self.argv = argv     # Bump the first (command name)
        self.args = []       # Used after a call to _parse()
        self.opts = object() #  idem.

        # Setup default action = help
        action = 'help'
        self.listcmds = False
        if len(self.argv):
            # Take out the action.
            action = self.argv.pop(0)
            if action in ['-h', '--help', '--list-commands']:
                if action == '--list-commands':
                    self.listcmds = True
                action = 'help'

            if action in ['-v', '--version']:
                print "%s version %s" % (PROGRAM, __version__)
                return

            # Fix for functions
            action = action.replace('-', '_')
        # Check the first parameter, if it's in the local object.

        # Call it or show the help.
        if not hasattr(self, action):
            print "[SFLvault] Invalid command: %s" % action
            action = 'help'

        self.action = action
        try:
            getattr(self, action)()
        except SFLvaultParserError, e:
            print "[SFLvault] Command line error: %s" % e
            print
            self.help(cmd=action, error=e)
        except AuthenticationError:
            raise
        except VaultError:
            #raise
            pass
        except xmlrpclib.Fault, e:
            # On is_admin check failed, on user authentication failed.
            print "[SFLvault] XML-RPC Fault: %s" % e.faultString
        except xmlrpclib.ProtocolError, e:
            # Server crashed
            print "[SFLvault] XML-RPC communication failed: %s" % e
        except VaultConfigurationError, e:
            print "[SFLvault] Configuration error: %s" % e
        except RemotingError, e:
            print "[SFLvault] Remoting error: %s" % e.message
        except ServiceRequireError, e:
            print "[SFLvault] Service-chain setup error: %s" % e.message
        except DecryptError, e:
            print "[SFLvault] There has been an error in decrypting messages: %s" % e.message
        except VaultIDSpecError, e:
            print "[SFLvault] VaultID spec. error: %s" % e.message
        except socket.error, e:
            print "[SFLvault] Connection error: %s" % e.message
            
        

    def _parse(self):
        """Parse the command line options, and fill self.opts and self.args"""
        (self.opts, self.args) = self.parser.parse_args(args=self.argv)


    def _del_last_history_item(self):
        """Remove the last line in history (used to erase passwords from
        history)."""
        readline.remove_history_item(readline.get_current_history_length() - 1)


    def help(self, cmd=None, error=None):
        """Print this help.

        You can use:
        
          help [command]

        to get further help for `command`."""

        # For BASH completion.
        if self.listcmds:
            # Show only a list of commands, for bash-completion.
            for x in dir(self):
                if not x.startswith('_') and callable(getattr(self, x)):
                    print x.replace('_', '-')
            sys.exit()

        # Normal help screen.
        print "%s version %s" % (PROGRAM, __version__)
        print "---------------------------------------------"

        if not cmd:
            print "Here is a quick overview of the commands:"
            # TODO: go around all the self. attributes and display docstrings
            #       and give coherent help for every function if specified.
            #       all those not starting with _.
            for x in dir(self):
                if not x.startswith('_') and callable(getattr(self, x)):
                    doc = getattr(self, x).__doc__
                    if doc:
                        doc = doc.split("\n")[0]
                    else:
                        doc = '[n/a]'
                
                    print " %s%s%s" % (x.replace('_','-'),
                                       (18 - len(x)) * ' ',
                                       doc)
            print "---------------------------------------------"
            print "Call: sflvault [command] --help for more details on each of those commands."
        elif not cmd.startswith('_') and callable(getattr(self, cmd)):
            readcmd = cmd.replace('_','-')

            doc = getattr(self, cmd).__doc__
            if doc:
                print "Help for command: %s" % readcmd
                print "---------------------------------------------"
                print doc
            else:
                print "No documentation available for `%s`." % readcmd

            print ""

            try:
                self.parser.parse_args(args=['--help'])
            except ExitParserException, e:
                pass
        else:
            print "No such command"

        print "---------------------------------------------"
            
        if (error):
            print "ERROR calling %s: %s" % (cmd, error)
        return
            

    def user_add(self):
        """Add a user to the Vault."""
        self.parser.set_usage("user-add [options] username")
        self.parser.add_option('-a', '--admin', dest="is_admin",
                               action="store_true", default=False,
                               help="Give admin privileges to the added user")

        self._parse()

        if (len(self.args) != 1):
            raise SFLvaultParserError("Invalid number of arguments")
        
        username = self.args[0]
        admin = self.opts.is_admin

        self.vault.user_add(username, admin)


    def customer_add(self):
        """Add a new customer to the Vault's database."""
        self.parser.set_usage('customer-add "customer name"')
        self._parse()
        
        if (len(self.args) != 1):
            raise SFLvaultParserError('Invalid number of arguments')

        customer_name = self.args[0]

        self.vault.customer_add(customer_name)


    def user_del(self):
        """Delete an existing user."""
        self.parser.set_usage("user-del username")
        self._parse()

        if (len(self.args) != 1):
            raise SFLvaultParserError("Invalid number of arguments")

        username = self.args[0]

        self.vault.user_del(username)


    def customer_del(self):
        """Delete an existing customer, it's machines and all services.

        Make sure you have detached all services' childs before removing a
        customer with machines which has services that are parents to other
        services."""
        
        self.parser.set_usage("customer-del customer_id")
        self._parse()

        # TODO someday: DRY
        if len(self.args) != 1:
            raise SFLvaultParserError("Invalid number of arguments")

        customer_id = self.vault.vaultId(self.args[0], 'c')

        self.vault.customer_del(customer_id)


    def machine_del(self):
        """Delete an existing machine, including all services.

        Make sure you have detached all services' childs before removing
        a machine which has services that are parents to other services.
        """
        
        self.parser.set_usage("machine-del machine_id")
        self._parse()

        # TODO someday: DRY
        if len(self.args) != 1:
            raise SFLvaultParserError("Invalid number of arguments")

        machine_id = self.vault.vaultId(self.args[0], 'm')

        self.vault.machine_del(machine_id)


    def service_del(self):
        """Delete an existing service. Make sure you have detached all
        childs before removing a parent service."""
        self.parser.set_usage("service-del service_id")
        self._parse()

        # TODO someday: DRY
        if len(self.args) != 1:
            raise SFLvaultParserError("Invalid number of arguments")

        service_id = self.vault.vaultId(self.args[0], 's')

        self.vault.service_del(service_id)
        

    def _machine_options(self):
        self.parser.set_usage("machine-add [options]")
        self.parser.add_option('-c', '--customer', dest="customer_id",
                               help="Customer id, as 'c#123' or '123'")
        self.parser.add_option('-n', '--name', dest="name",
                               help="Machine name, used for display everywhere")
        self.parser.add_option('-d', '--fqdn', dest="fqdn", default='',
                               help="Fully qualified domain name, if available")
        self.parser.add_option('-i', '--ip', dest="ip", default='',
                               help="Machine's IP address, in order to access itfrom it's hierarchical position")
        self.parser.add_option('-l', '--location', dest="location", default='',
                               help="Machine's physical location, position in racks, address, etc..")
        self.parser.add_option('--notes', dest="notes",
                               help="Notes about the machine, references, URLs.")
        
    def machine_add(self):
        """Add a machine to the Vault's database."""

        self._machine_options()
        self._parse()

        if not self.opts.name:
            raise SFLvaultParserError("Required parameter 'name' omitted")
        
        ## TODO: make a list-customers and provide a selection using arrows or
        #        or something alike.
        if not self.opts.customer_id:
            raise SFLvaultParserError("Required parameter 'customer' omitted")

        o = self.opts
        customer_id = self.vault.vaultId(o.customer_id, 'c')
        self.vault.machine_add(customer_id, o.name, o.fqdn,
                               o.ip, o.location, o.notes)


    def _service_options(self):
        """Add options for calls to `service-add` and `service-edit`"""
        
        self.parser.add_option('-m', '--machine', dest="machine_id",
                               help="Attach Service to Machine #, as "\
                                    "'m#123', '123' or an alias")
        self.parser.add_option('-u', '--url', dest="url",
                               help="Service URL, full proto://[username@]"\
                               "fqdn.example.org[:port][/path[#fragment]], "\
                               "WITHOUT the secret.")

        self.parser.add_option('-p', '--parent', dest="parent_id",
                               help="Make this Service child of Parent "\
                                    "Service #")
        self.parser.add_option('-g', '--group', dest="group_ids",
                               action="append", type="string",
                               help="Access group_id for this service, as "\
                               "'g#123' or '123'. Use group-list to view "\
                               "complete list. You can specify multiple groups")
        self.parser.add_option('--notes', dest="notes",
                               help="Notes about the service, references, "\
                                    "URLs.")

    def _service_clean_url(self, url):
        """Remove password in URL, and notify about rewrite."""

        # Rewrite url if a password was included... strip the port and
        #       username from the URL too.
        if url.password:
            out = []
            if url.username:
                out.append('%s@' % url.username)
            
            out.append(url.hostname)
            
            if url.port:
                out.append(":%d" % url.port)
            
            url = urlparse.urlunparse((url[0],
                                       ''.join(out),
                                       url[2], url[3], url[4], url[5]))

            print "NOTE: Do not specify password in URL. Rewritten: %s" % url

        return url


    def service_add(self):
        """Add a service to a particular machine.

        The secret/password/authentication key will be asked in the
        interactive prompt.

        Note : Passwords will never be taken from the URL when invoked on the
               command-line, to prevent sensitive information being held in
               history.
        """
        
        self._service_options()
        self._parse()

        if not self.opts.url:
            raise SFLvaultParserError("Required parameter 'url' omitted")
        
        ## TODO: make a list-customers and provide a selection using arrows or
        #        or something alike.
        if not self.opts.machine_id:
            raise SFLvaultParserError("Machine ID required. Please specify -m|--machine [VaultID]")

        if not self.opts.group_ids:
            raise SFLvaultParserError("At least one group required")
        
        
        o = self.opts

        url = urlparse.urlparse(o.url)
        url = self._service_clean_url(url)

        secret = None

        if not secret:
            # Use raw_input so that we see the password. To make sure we enter
            # a valid and the one we want (what if copy&paste didn't work, and
            # you didn't know ?)
            secret = raw_input("Enter service's password: ")
            self._del_last_history_item()


        machine_id = 0
        parent_id = 0
        group_ids = []
        if o.machine_id:
            machine_id = self.vault.vaultId(o.machine_id, 'm')
        if o.parent_id:
            parent_id = self.vault.vaultId(o.parent_id, 's')
        if o.group_ids:
            group_ids = [self.vault.vaultId(g, 'g') for g in o.group_ids]
            
        self.vault.service_add(machine_id, parent_id, o.url, group_ids, secret,
                               o.notes)
        


    def service_edit(self):
        """Edit service informations."""
        self._something_edit("service-edit [service_id]",
                             'service_id', 's',
                             self.vault.service_get,
                             self.vault.service_put,
                             ui.ServiceEditDialogDisplay,
                             'service-edit aborted')

    def machine_edit(self):
        """Edit machine informations."""
        self._something_edit("machine-edit [machine_id]",
                             'machine_id', 'm',
                             self.vault.machine_get,
                             self.vault.machine_put,
                             ui.MachineEditDialogDisplay,
                             'machine-edit aborted')

    def customer_edit(self):
        """Edit customer informations."""
        self._something_edit("customer-edit [customer_id]",
                             'customer_id', 'c',
                             self.vault.customer_get,
                             self.vault.customer_put,
                             ui.CustomerEditDialogDisplay,
                             'customer-edit aborted')

    def group_edit(self):
        """Edit Group informations"""
        self._something_edit("group-edit [group_id]",
                             'group_id', 'g',
                             self.vault.group_get,
                             self.vault.group_put,
                             ui.GroupEditDialogDisplay,
                             'group-edit aborted')

    def _something_edit(self, usage, required_args, vault_id_type,
                        get_function, put_function, ui_class, abort_message):

        self.parser.set_usage(usage)
        self._parse()

        if not len(self.args):
            raise SFLvaultParserError("Required argument: %s" % required_args)

        thing_id = self.vault.vaultId(self.args[0], vault_id_type)

        # TODO: make the service_edit NOT decrypt stuff (it's not needed
        #       when we're only editing)
        thing = get_function(thing_id)

        dialog = ui_class(thing)
        save, data = dialog.run()

        if save:
            print "Sending data to vault..."
            put_function(thing_id, data)
        else:
            print abort_message


    def service_passwd(self):
        """Change the password for a service.

        Do not specify password on command line, it will be asked on the
        next line.
        """
        self.parser.set_usage("service-passwd [service_id]")
        self._parse()

        if not len(self.args):
            raise SFLvaultParserError("Required argument: service_id")

        newsecret = raw_input("Enter new service password: ")
        self._del_last_history_item()

        self.vault.service_passwd(self.args[0], newsecret)


    def alias(self):
        """Set an alias, local shortcut to VaultIDs (s#123, m#87, etc..)

        List, view or set an alias."""
        self.parser.set_usage("alias [options] [alias [VaultID]]")

        self.parser.add_option('-d', '--delete', dest="delete",
                               metavar="ALIAS", help="Delete the given alias")

        self._parse()

        if self.opts.delete:
            
            res = self.vault.alias_del(self.opts.delete)

            if res:
                print "Alias removed"
            else:
                print "No such alias"

        elif len(self.args) == 0:
            # List aliases
            l = self.vault.alias_list()
            print "Aliased VaultIDs:"
            for x in l:
                print "\t%s\t%s" % (x[0], x[1])

        elif len(self.args) == 1:
            # Show this alias's value
            a = self.vault.alias_get(self.args[0])
            if a:
                print "Aliased VaultID:"
                print "\t%s\t%s" % (self.args[0], a)
            else:
                print "Invalid alias"

        elif len(self.args) == 2:
            try:
                r = self.vault.alias_add(self.args[0], self.args[1])
            except ValueError, e:
                raise SFLvaultParserError(e.message)

            print "Alias added"

        else:
            raise SFLvaultParserError("Invalid number of parameters")


    def customer_list(self):
        """List existing customers.

        This option takes no argument, it just lists customers with their IDs."""
        self._parse()
        
        if len(self.args):
            raise SFLvaultParserError('Invalid number of arguments')

        self.vault.customer_list()

    def user_list(self):
        """List existing users.

        This option takes no argument, it lists the current users and their
        privileges."""
        self.parser.set_usage("user-list [-g]")
        self.parser.add_option('-g', '--groups', default=False,
                               action="store_true", dest="groups",
                               help="List user's group infos")
        self._parse()

        if len(self.args):
            raise SFLvaultParserError("Invalid number of arguments")

        self.vault.user_list(self.opts.groups)


    def _group_service_options(self):
        self.parser.add_option('-g', dest="group_id",
                               help="Group to add the service to")
        self.parser.add_option('-s', dest="service_id",
                               help="Service to be added")

    def _group_service_parse(self):
        if not self.opts.group_id or not self.opts.service_id:
            raise SFLvaultParserError("-g and -s options required")

        self.opts.group_id = self.vault.vaultId(self.opts.group_id, 'g')
        self.opts.service_id = self.vault.vaultId(self.opts.service_id, 's')

    def group_add_service(self):
        """Add a service to a group, doing necessary re-encryption"""
        self.parser.set_usage("group-add-service -g <group_id> -s <service_id>")
        self._group_service_options()
        self._parse()

        self._group_service_parse()
        
        self.vault.group_add_service(self.opts.group_id, self.opts.service_id)

    def group_del_service(self):
        """Remove a service from a group"""
        self.parser.set_usage("group-del-service -g <group_id> -s <service_id>")
        self._group_service_options()
        self._parse()

        self._group_service_parse()
        
        self.vault.group_del_service(self.opts.group_id, self.opts.service_id)


    def _group_user_options(self):
        self.parser.add_option('-g', dest="group_id",
                               help="Group to add the service to")
        self.parser.add_option('-u', dest="user",
                               help="Service to be added")

    def _group_user_parse(self):
        if not self.opts.group_id or not self.opts.user:
            raise SFLvaultParserError("-g and -u options required")
        
        self.opts.group_id = self.vault.vaultId(self.opts.group_id, 'g')

    def group_add_user(self):
        """Add a user to a group, doing necessary re-encryption"""
        self.parser.set_usage("group-add-user [-a] -g <group_id> -u <user>")
        self.parser.add_option('-a', action="store_true", dest='is_admin',
                               default=False, help="Mark as group admin")
        self._group_user_options()
        self._parse()

        self._group_user_parse()
        
        self.vault.group_add_user(self.opts.group_id, self.opts.user,
                                  self.opts.is_admin)

    def group_del_user(self):
        """Remove a user from a group"""
        self.parser.set_usage("group-del-user -g <group_id> -u <user>")
        self._group_user_options()
        self._parse()

        self._group_user_parse()
        
        self.vault.group_del_user(self.opts.group_id, self.opts.user)

    def group_del(self):
        """Remove a group from the Vault

        For this to be successful, the group must have no more services
        associated with it."""
        self.parser.set_usage("group-del -g <group_id>")
        self.parser.add_option('-g', dest="group_id",
                               help="Group to be removed")
        self._parse()

        if not self.opts.group_id:
            raise SFLvaultParserError("-g option required")

        self.vault.group_del(self.opts.group_id)

    def group_add(self):
        """Add a group to the Vault

        This command accepts a group name (as string) as first and only
        parameter.
        """
        self.parser.set_usage("group-add <group name>")
        self._parse()

        if len(self.args) != 1:
            raise SFLvaultParserError("Group name (as string) required")

        self.vault.group_add(self.args[0])


    def group_list(self):
        """List existing groups."""
        self.parser.set_usage("group-list")
        self._parse()

        if len(self.args):
            raise SFLvaultParserError("Invalid number of arguments")

        self.vault.group_list()


    def machine_list(self):
        """List existing machines.

        This command will list all machines in the Vault's database."""
        ## TODO: add support for listing only machines of a certain c#id
        #        (customer_id)
        self.parser.add_option('-v', '--verbose', action="store_true",
                               dest='verbose', default=False,
                               help="Enable verbose output (location and notes)")
        self.parser.add_option('-c', '--customer', dest='customer_id',
                               help="Customer id")
        self._parse()

        customer_id = None
        if self.opts.customer_id:
            customer_id = self.vault.vaultId(self.opts.customer_id, 'c')

        if len(self.args):
            raise SFLvaultParserError("Invalid number of arguments")

        self.vault.machine_list(self.opts.verbose, customer_id)


    def user_passwd(self):
        """Change the passphrase protecting your local private key"""
        self.parser.set_usage("user-passwd")
        self._parse()

        if len(self.args) != 0:
            raise SFLvaultParserError("user-passwd takes no arguments")

        self.vault.user_passwd()

    def user_setup(self):
        """Setup a new user on the vault.

        Call this after an admin has called `user-add` on the Vault.
        
        username  - the username used in the `user-add` call.
        vault_url - the URL (http://example.org:port/vault/rpc) to the
                    Vault"""
        
        self.parser.set_usage("user-setup <username> <vault_url>")
        self._parse()
        
        if len(self.args) != 2:
            raise SFLvaultParserError("Invalid number of arguments")

        username = self.args[0]
        url      = self.args[1]

        self.vault.user_setup(username, url)

    def show(self):
        """Show informations to connect to a particular service.

        VaultID - service ID as 's#123', '123', or alias pointing to a service
                  ID."""
        self.parser.set_usage("show [opts] VaultID")
        self.parser.add_option('-v', '--verbose', dest="verbose",
                               action="store_true", default=False,
                               help="Show verbose output (include notes, "\
                                    "location)")
        self.parser.add_option('-g', '--groups', dest="with_groups",
                               action="store_true", default=False,
                               help="Show groups this service is member of")
        self._parse()

        if len(self.args) != 1:
            raise SFLvaultParserError("Invalid number of arguments")

        vid = self.vault.vaultId(self.args[0], 's')
        verbose = self.opts.verbose

        self.vault.show(vid, verbose, self.opts.with_groups)




    def connect(self):
        """Connect to a remote SSH host, sending password on the way.

        VaultID - service ID as 's#123', '123', or alias pointing to a service
                  ID."""
        # Chop in two parts
        args = self.argv

        if len(args) < 1:
            raise SFLvaultParserError("Invalid number of arguments")

        vid = self.vault.vaultId(args[0], 's')

        self.vault.connect(vid, command_line=args[1:])



    def search(self):
        """Search the Vault for the given keywords"""
        self.parser.set_usage('search [opts] keyword1 ["key word2" ...]')
        self.parser.add_option('-g', '--group', dest="groups",
                               action="append", type="string",
                               help="Search in these groups only")
        self.parser.add_option('-q', '--quiet', dest="verbose",
                               action="store_false", default=True,
                               help="Don't show verbose output (includes notes, location)")
        
        self.parser.add_option('-m', '--machine', dest="machines",
                               action="append", type="string",
                               help="Filter results on these machines only")

        self.parser.add_option('-c', '--customer', dest="customers",
                               action="append", type="string",
                               help="Filter results on these customers only")

        self._parse()

        if not len(self.args):
            raise SFLvaultParserError("Search terms required")

        # Get the values for each filter spec..
        fields = {'groups': 'g',
                  'machines': 'm',
                  'customers': 'c'}
        filters = {}
        for f in fields.keys():
            criteria = None
            if getattr(self.opts, f):
                criteria = [self.vault.vaultId(x, fields[f])
                            for x in getattr(self.opts, f)]
            filters[f] = criteria

        self.vault.search(self.args, filters or None, self.opts.verbose)


class SFLvaultCompleter:
    def __init__(self, namespace):
        self.namespace = namespace
        self.matches = []

    def complete(self, text, state):
        if state == 0:
            self.matches = self.global_matches(text)
        try:
            return self.matches[state]
        except IndexError:
            return None

    def global_matches(self, text):
        matches = []
        for word in self.namespace:
            if word.find(text,0,len(text)) == 0:
                matches.append(word)
        return matches

###
### Execute requested command-line command
###    
def main():
    # Call the appropriate function of the 'f' object, according to 'action'
    func_list = []
    for onefunc in dir(SFLvaultCommand):
        if onefunc[0] != '_':
            func_list.append(onefunc.replace('_', '-'))

    readline.set_completer_delims('_')
    readline.set_completer(SFLvaultCompleter(func_list).complete)
    readline.parse_and_bind("tab: complete")


    if len(sys.argv) == 1 or sys.argv[1] == 'shell':
        s = SFLvaultShell()
        try:
            s._run()
        except (KeyboardInterrupt, EOFError), e:
            print "\nExiting."
            sys.exit()
    else:
        f = SFLvaultCommand()
        f._run(sys.argv[1:])

    

# For wrappers.
if __name__ == "__main__":

    main()