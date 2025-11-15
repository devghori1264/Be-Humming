#!/usr/bin/env python3

import shutil
import subprocess
from pathlib import Path
from .logging import Log

def which_bin(names):
    """Finds the first available binary from a list of names."""
    for n in names:
        p = shutil.which(n)
        if p:
            return p
    return None

def run_cmd(cmd, expected_outpaths=None, timeout=60):
    try:
        # We use Popen and communicate to handle timeouts and large outputs
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        stdout, stderr = process.communicate(timeout=timeout)
        returncode = process.returncode

        full_output = stdout + stderr

        if returncode != 0:
            return False, f"Command failed (code {returncode}): {cmd[0]}. Error: {full_output}"

        if expected_outpaths:
            for p in expected_outpaths:
                if not Path(p).exists() or Path(p).stat().st_size == 0:
                    return False, f"Expected output not produced: {p}. Cmd output: {full_output}"
        return True, full_output

    except subprocess.TimeoutExpired:
        process.kill()
        return False, f"Command timed out after {timeout}s: {cmd[0]}"
    except FileNotFoundError:
        return False, f"Command not found: {cmd[0]}. Please ensure it's in your PATH."
    except Exception as e:
        return False, f"An unexpected error occurred: {e}"