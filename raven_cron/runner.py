from os import getenv, SEEK_END
from raven import Client
from subprocess import call
from tempfile import TemporaryFile
from argparse import ArgumentParser
from sys import argv, exit
from time import time
from .version import VERSION

MAX_MESSAGE_SIZE = 1000

parser = ArgumentParser(description='Wraps commands and reports failing ones to sentry')
# FIXME: Should we also use a configuration file ?
parser.add_argument(
    '--dsn',
    metavar='SENTRY_DSN',
    default=getenv('SENTRY_DSN'),
    help='Sentry server address',
)
parser.add_argument(
    '--version',
    action='version',
    version=VERSION,
)
parser.add_argument(
    'cmd',
    nargs='*',
    help='The command to run',
)

def run(args=argv[1:]):
    opts = parser.parse_args(args)
    runner = CommandReporter(**vars(opts))
    runner.run()

class CommandReporter(object):
    def __init__(self, cmd, dsn):
        if len(cmd) <= 1:
            cmd = cmd[0]

        self.dsn = dsn
        self.command = cmd
        self.client = None

    def run(self):
        buf = TemporaryFile()
        start = time()

        exit_status = call(self.command, stdout=buf, stderr=buf, shell=True)
        
        if exit_status > 0:
            elapsed = time() - start
            self.report_fail(exit_status, buf, elapsed)

        buf.close()
        
    def report_fail(self, exit_status, buf, elapsed):
        # Hack to get the file size since the tempfile doesn't exist anymore
        buf.seek(0, SEEK_END)
        if buf.tell() > MAX_MESSAGE_SIZE:
            buf.seek(0)
        else:
            buf.seek(-MAX_MESSAGE_SIZE, SEEK_END)

        last_lines = buf.read()

        message="Command %s exited with exit status %d" % (self.command, exit_status)
        #print message

        if self.dsn is None:
            return
        
        if self.client is None:
            self.client = Client(dsn=self.dsn)

        # FIXME: extras are not displayed
        self.client.capture(
            'raven.events.Message',
            message=message,
            extra={
                'command': self.command,
                'exit_status': exit_status,
                'last_lines': last_lines,
            },
            time_spent=elapsed
        )
