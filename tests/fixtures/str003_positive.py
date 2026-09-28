"""Positive cases for STR003: Popen(stdout/stderr=PIPE) waited on undrained."""

import subprocess
import subprocess as sp
from subprocess import PIPE, Popen


def wait_after_stdout_pipe() -> None:
    proc = subprocess.Popen(["true"], stdout=subprocess.PIPE)
    proc.wait()


def wait_after_stderr_pipe() -> None:
    proc = subprocess.Popen(["true"], stderr=subprocess.PIPE)
    proc.wait()


def poll_loop_after_pipe() -> None:
    proc = subprocess.Popen(["true"], stdout=subprocess.PIPE)
    while proc.poll() is None:
        pass


def aliased_module() -> None:
    proc = sp.Popen(["true"], stdout=sp.PIPE)
    proc.wait()


def from_import() -> None:
    proc = Popen(["true"], stdout=PIPE)
    proc.wait()


def both_pipes_waited() -> None:
    proc = subprocess.Popen(["true"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    proc.wait()
