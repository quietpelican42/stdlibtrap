"""Negative controls for STR003: pipes that are drained, or not present."""

import subprocess


def uses_communicate() -> None:
    proc = subprocess.Popen(["true"], stdout=subprocess.PIPE)
    proc.communicate()


def reads_stdout_directly() -> None:
    proc = subprocess.Popen(["true"], stdout=subprocess.PIPE)
    assert proc.stdout is not None
    proc.stdout.read()
    proc.wait()


def iterates_stdout() -> None:
    proc = subprocess.Popen(["true"], stdout=subprocess.PIPE)
    assert proc.stdout is not None
    for _line in proc.stdout:
        pass
    proc.wait()


def no_pipe_no_wait_issue() -> None:
    proc = subprocess.Popen(["true"])
    proc.wait()


def poll_outside_loop_is_fine() -> None:
    proc = subprocess.Popen(["true"], stdout=subprocess.PIPE)
    proc.communicate()
    proc.poll()


def wait_without_pipe_at_all() -> None:
    proc = subprocess.Popen(["true"], stdout=None)
    proc.wait()
