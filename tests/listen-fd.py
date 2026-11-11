#!/usr/bin/env python3
"""Root-only integration test; run in an isolated Linux network namespace.

Set DHCPCD_LISTEN_FD_TEST=1 and pass the dhcpcd binary and an UP interface.
"""

import os
import select
import signal
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


def read_preinit(sock, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        (length,) = HEADER.unpack(read_exact(sock, HEADER.size, deadline))
        if length > MAX_EVENT_SIZE:
            raise ValueError(f"unexpected event size: {length}")
        event = read_exact(sock, length, deadline)
        if b"reason=PREINIT\0" in event:
            return
    raise TimeoutError("startup PREINIT event was not forwarded")


def read_until_close(sock, timeout=10):
    deadline = time.monotonic() + timeout
    data = bytearray()
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not select.select([sock], [], [], remaining)[0]:
            return bytes(data), False
        chunk = sock.recv(4096)
        if not chunk:
            return bytes(data), True
        data.extend(chunk)


def read_until_eof(sock, timeout=10):
    data, closed = read_until_close(sock, timeout)
    if not closed:
        raise TimeoutError("timed out waiting for the event socket to close")
    return data


def unpack_frames(data):
    frames = []
    offset = 0
    while offset < len(data):
        if len(data) - offset < HEADER.size:
            raise ValueError("truncated event length prefix")
        (length,) = HEADER.unpack_from(data, offset)
        offset += HEADER.size
        if length > MAX_EVENT_SIZE:
            raise ValueError(f"unexpected event size: {length}")
        if len(data) - offset < length:
            raise ValueError("truncated event payload")
        frames.append(data[offset : offset + length])
        offset += length
    return frames


def pidfile_for(binary, interface=None):
    command = [binary, "--config=/dev/null", "--printpidfile"]
    if interface:
        command.append(interface)
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def listener_command(binary, fd, interface, background):
    command = [
        binary,
        f"--listen-fd={fd}",
        "--config=/dev/null",
        "--script=/dev/null",
        "--noipv4",
        "--noipv6",
    ]
    command.append("--background" if background else "--nobackground")
    command.append(interface)
    return command


def test_output_only_input(binary, interface, version):
    parent, child = socket.socketpair()
    process = None
    try:
        process = subprocess.Popen(
            listener_command(binary, child.fileno(), interface, False),
            pass_fds=(child.fileno(),),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        child.close()
        read_preinit(parent)

        # A control command sent in the reverse direction must not be parsed
        # or answered on this event-only stream.
        parent.sendall(b"--version\n\0")
        reply, closed = read_until_close(parent, timeout=3)
        frames = unpack_frames(reply)
        if version + b"\0" in frames:
            raise AssertionError("event-only FD parsed an inbound control command")
        if not closed:
            raise AssertionError("event-only FD did not close after inbound data")
    finally:
        child.close()
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                raise RuntimeError("foreground dhcpcd did not stop after SIGTERM")
        parent.close()
    print("PASS: inherited FD forwards events only and rejects inbound commands")


def test_daemonized_startup(binary, interface):
    parent, child = socket.socketpair()
    launcher = None
    daemon_pid = None
    pidfile = pidfile_for(binary, interface)
    try:
        launcher = subprocess.Popen(
            listener_command(binary, child.fileno(), interface, True),
            pass_fds=(child.fileno(),),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        child.close()
        launcher.wait(timeout=10)
        if launcher.returncode != 0:
            raise RuntimeError(
                f"daemonization launcher exited with status {launcher.returncode}"
            )

        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                with open(pidfile, encoding="ascii") as stream:
                    daemon_pid = int(stream.read().strip())
                break
            except (FileNotFoundError, ValueError):
                time.sleep(0.05)
        if daemon_pid is None:
            raise TimeoutError("daemon pidfile did not appear")
        read_preinit(parent)
    finally:
        child.close()
        if daemon_pid is None:
            try:
                with open(pidfile, encoding="ascii") as stream:
                    daemon_pid = int(stream.read().strip())
            except (FileNotFoundError, ValueError):
                pass
        if daemon_pid is not None:
            try:
                os.kill(daemon_pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                read_until_eof(parent)
            except TimeoutError:
                try:
                    os.kill(daemon_pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                raise RuntimeError("daemon did not close the inherited event FD")
        if launcher is not None and launcher.poll() is None:
            launcher.terminate()
            launcher.wait(timeout=10)
        parent.close()
    print("PASS: inherited FD survives daemonization and forwards PREINIT")


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

    version_output = subprocess.run(
        [binary, "--version"], check=True, capture_output=True, text=True
    ).stdout.strip()
    version = version_output.splitlines()[0].split()[-1].encode()
    test_output_only_input(binary, interface, version)
    test_daemonized_startup(binary, interface)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"FAIL: {error}", file=sys.stderr)
        sys.exit(1)
