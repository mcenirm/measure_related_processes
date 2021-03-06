#!/usr/bin/env python3

import argparse
import csv
from datetime import datetime, timezone
import sys
import time

import psutil


def build_argument_parser():
    parser = argparse.ArgumentParser(
        description=(
            'Run COMMAND and measure the new'
            ' process and related processes.'
        ),
    )
    parser.add_argument(
        '-m',
        dest='measurement_filename',
        help='name of file to hold measurements',
        default='measurements.csv',
    )
    parser.add_argument(
        '-s',
        dest='seconds_between_cycles',
        help='seconds between cycles',
        default=1.0,
    )
    parser.add_argument(
        'command',
        metavar='COMMAND',
        help='command line to run and measure',
        nargs=argparse.REMAINDER,
    )
    return parser


def parse_arguments():
    parser = build_argument_parser()
    arguments = parser.parse_args()
    if not arguments.command:
        parser.error('Missing command line')
    return arguments


class NoOpContextManager():
    def __init__(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class SafetyGoggles():
    def __init__(self, backing=None):
        self._backing = backing

    def __str__(self):
        return 'N/A' if self._backing is None else str(self._backing)

    def __getattr__(self, name):
        if self._backing is None:
            details = None
        else:
            attr = getattr(self._backing, name, None)
            details = None
            if attr is not None:
                details = attr() if callable(attr) else attr
        if isinstance(details, (int, float, str)):
            result = details
        else:
            result = SafetyGoggles(details)
        setattr(self, name, result)
        return result


class MeasurementsWriter():
    def __init__(self, csvfile):
        self.csvfile = csvfile
        self.writer = None
        self.header = []
        self.record = []

    def writeprocess(self, cycle, process):
        if hasattr(process, 'oneshot'):
            oneshot = process.oneshot()
        else:
            oneshot = NoOpContextManager()
        timestamp = time.time()
        with oneshot:
            self.writefield(
                'Timestamp',
                datetime.fromtimestamp(
                    timestamp,
                    timezone.utc,
                ).isoformat()
            )
            p = SafetyGoggles(process)
            self.writefield('PID', p.pid)
            self.writefield('PPID', p.ppid)
            self.writefield('Image', p.name)
            self.writefield('Elapsed', timestamp - p.create_time)
            self.writefield('System time', p.cpu_times.system)
            self.writefield('User time', p.cpu_times.user)
            self.writefield('Threads', p.num_threads)
            self.writefield('Active memory', p.memory_info.rss)
            self.writefield('Virtual memory', p.memory_info.vms)
            self.writefield('Read operations', p.io_counters.read_count)
            self.writefield('Read bytes', p.io_counters.read_bytes)
            self.writefield('Write operations', p.io_counters.write_count)
            self.writefield('Write bytes', p.io_counters.write_bytes)
            self.writefield('Cycle', cycle)
            self.writefield('State', p.status)
            self.writefield('File descriptors', p.num_fds)
            self.writefield('Shared memory', p.memory_info.shared)
            self.writefield(
                'Voluntary context switches',
                p.num_ctx_switches.voluntary,
            )
            self.writefield(
                'Involuntary context switches',
                p.num_ctx_switches.involuntary,
            )
            self.writefield('Current working directory', p.cwd)
            self.writerecord()

    def writefield(self, label, value):
        if self.writer is None:
            self.header.append(label)
        self.record.append(value)

    def writerecord(self):
        if self.writer is None:
            self.writer = csv.writer(self.csvfile)
            self.writer.writerow(self.header)
        self.writer.writerow(self.record)
        self.record = []


def main():
    arguments = parse_arguments()
    cycle = 0
    first = psutil.Popen(arguments.command)
    with open(arguments.measurement_filename, 'w') as measurement_f:
        writer = MeasurementsWriter(measurement_f)
        while first.is_running() and first.status() != psutil.STATUS_ZOMBIE:
            cycle += 1
            children = first.children()
            for process in sorted([first, *children], key=lambda _: _.pid):
                writer.writeprocess(cycle, process)
            time.sleep(arguments.seconds_between_cycles)
        first.wait()


if __name__ == '__main__':
    sys.exit(main())
