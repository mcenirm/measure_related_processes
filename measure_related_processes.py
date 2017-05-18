#!/usr/bin/env python3

import argparse
import csv
from datetime import datetime, timezone
import sys
import time

import psutil


def build_argument_parser():
    parser = argparse.ArgumentParser(
        description='Run COMMAND and measure the new process and related processes.',
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


FIELD_NAMES = [
    'cpu_num',
    'cpu_percent',
    'cpu_times',
    'create_time',
    'cwd',
    'exe',
    'gids',
    'io_counters',
    'memory_info',
    'memory_percent',
    'name',
    'nice',
    'num_ctx_switches',
    'num_fds',
    'num_handles',
    'num_threads',
    'pid',
    'ppid',
    'status',
    'terminal',
    'uids',
    'username',
]


class NoOpContextManager():
    def __init__(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def prepare_record(cycle, process):
    record = dict(cycle=cycle)
    timestamp = time.time()
    if hasattr(process, 'oneshot'):
        oneshot = process.oneshot()
    else:
        oneshot = NoOpContextManager()
    with oneshot:
        record['pid'] = process.pid
        for name in FIELD_NAMES:
            attr = getattr(process, name, None)
            if attr is None:
                continue
            if callable(attr):
                details = attr()
            else:
                details = attr
            if isinstance(details, tuple) and hasattr(details, '_asdict'):
                for subkey, value in details._asdict().items():
                    key = name + '.' + subkey
                    record[key] = value
            else:
                record[name] = details
    create_time = record['create_time']
    record['elapsed_seconds'] = timestamp - create_time
    record['timestamp'] = datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
    record['create_time'] = datetime.fromtimestamp(create_time, timezone.utc).isoformat()
    return record


def main():
    arguments = parse_arguments()
    cycle = 0
    first = psutil.Popen(arguments.command)
    first_record = prepare_record(cycle, first)
    fieldnames = sorted(first_record.keys())
    with open(arguments.measurement_filename, 'w') as measurement_f:
        writer = csv.DictWriter(measurement_f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(first_record)
        while first.is_running() and first.status() != psutil.STATUS_ZOMBIE:
            cycle += 1
            children = first.children()
            for process in sorted([first, *children], key=lambda _: _.pid):
                record = prepare_record(cycle, process)
                writer.writerow(record)
            time.sleep(arguments.seconds_between_cycles)
        first.wait()


if __name__ == '__main__':
    sys.exit(main())
