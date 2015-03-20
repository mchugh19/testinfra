# -*- coding: utf8 -*-
# Copyright © 2015 Philippe Pepiot
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import unicode_literals

import base64

from testinfra.backend import base
from testinfra.backend import local


class SshBackend(local.LocalBackend):
    """Run command through ssh command"""

    def __init__(self, hostspec, *args, **kwargs):
        self.host, self.user, self.port = self.parse_hostspec(hostspec)
        super(SshBackend, self).__init__(*args, **kwargs)

    def run(self, command, *args, **kwargs):
        cmd = ["ssh"]
        cmd_args = []
        if self.user:
            cmd.append("-o User=%s")
            cmd_args.append(self.user)
        if self.port:
            cmd.append("-o Port=%s")
            cmd_args.append(self.port)
        cmd.append("%s %s")
        cmd_args.extend([
            self.host,
            self.quote(command, *args),
        ])
        return super(SshBackend, self).run(
            " ".join(cmd), *cmd_args, **kwargs)


class SafeSshBackend(SshBackend):
    """Run command using ssh command but try to get a more sane output

    When using ssh (or a potentially bugged wrapper) additional output can be
    added in stdout/stderr and exit status may not be propagate correctly

    To avoid that kind of bugs, we wrap the command to have an output like
    this:

    TESTINFRA_START;EXIT_STATUS;STDOUT;STDERR;TESTINFRA_END

    where STDOUT/STDERR are base64 encoded, then we parse that magic string to
    get sanes variables
    """

    def run(self, command, *args, **kwargs):
        orig_command = self.quote(command, *args)

        out = super(SafeSshBackend, self).run((
            '''of=$(mktemp)&&ef=$(mktemp)&&%s >$of 2>$ef; r=$?;'''
            '''echo "TESTINFRA_START;$r;$(base64 < $of);$(base64 < $ef);'''
            '''TESTINFRA_END";rm -f $of $ef''') % (orig_command,))

        start = out.stdout.find("TESTINFRA_START;") + len("TESTINFRA_START;")
        end = out.stdout.find("TESTINFRA_END") - 1
        rc, stdout, stderr = out.stdout[start:end].split(";")

        return base.CommandResult(
            rc=int(rc),
            stdout=base64.b64decode(stdout),
            stderr=base64.b64decode(stderr),
            command=orig_command,
        )
