#!/usr/bin/env python3
"""Root-only integration test; run in an isolated Linux network namespace.

Set DHCPCD_LISTEN_FD_TEST=1 and pass the dhcpcd binary and an UP interface.
"""

import os
import select
import socket
import struct
import subprocess
import sys
import time


HEADER = struct.Struct("@N")
MAX_EVENT_SIZE = 64 * 1024


def read_exact(sock, length, deadline):
    data = bytearray()
    while len(data) < length:
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not select.select([sock], [], [], remaining)[0]:
            raise TimeoutError("timed out waiting for dhcpcd event")
        chunk = sock.recv(length - len(data))
        if not chunk:
            raise EOFError("dhcpcd closed the event socket")
        data.extend(chunk)
    return bytes(data)


def pidfile_for(binary, interface=None):
    command = [binary, "--config=/dev/null", "--printpidfile"]
    if interface:
        command.append(interface)
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def main():
    if os.environ.get("DHCPCD_LISTEN_FD_TEST") != "1":
        print("SKIP: set DHCPCD_LISTEN_FD_TEST=1 in an isolated test environment")
        return 0
    if sys.platform != "linux" or os.geteuid() != 0:
        print("SKIP: requires Linux and root")
        return 0
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} /path/to/dhcpcd interface", file=sys.stderr)
        return 2

    binary = os.path.abspath(sys.argv[1])
    interface = sys.argv[2]
    for pidfile in (pidfile_for(binary), pidfile_for(binary, interface)):
        if os.path.exists(pidfile):
            print(f"SKIP: dhcpcd pidfile already exists: {pidfile}")
            return 0

    parent, child = socket.socketpair()
    process = None
    received_preinit = False
    try:
        command = [
            binary,
            f"--listen-fd={child.fileno()}",
            "--nobackground",
            "--config=/dev/null",
            "--script=/dev/null",
            "--noipv4",
            "--noipv6",
            interface,
        ]
        process = subprocess.Popen(
            command,
            pass_fds=(child.fileno(),),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        child.close()

        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            (length,) = HEADER.unpack(read_exact(parent, HEADER.size, deadline))
            if length > MAX_EVENT_SIZE:
                raise ValueError(f"unexpected event size: {length}")
            event = read_exact(parent, length, deadline)
            if b"reason=PREINIT\0" in event:
                received_preinit = True
                break
        if not received_preinit:
            raise TimeoutError("startup PREINIT event was not forwarded")
    finally:
        child.close()
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                raise RuntimeError("dhcpcd did not stop after SIGTERM")

    parent.settimeout(3)
    while parent.recv(4096):
        pass
    parent.close()
    print("PASS: PREINIT was forwarded and the inherited FD closed on shutdown")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"FAIL: {error}", file=sys.stderr)
        sys.exit(1)
