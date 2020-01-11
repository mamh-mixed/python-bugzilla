# This work is licensed under the GNU GPLv2 or later.
# See the COPYING file in the top-level directory.

import difflib
import getpass
import inspect
import io
import os
import pprint
import shlex
import sys

import bugzilla._cli
from bugzilla._compatimports import IS_PY3

import tests


def get_funcname():
    # Return calling function name
    return inspect.stack()[1][3]


def tests_path(filename):
    testdir = os.path.dirname(__file__)
    if testdir not in filename:
        return os.path.join(testdir, filename)
    return filename


def fake_stream(text):
    if IS_PY3:
        return io.StringIO(text)
    else:
        return io.BytesIO(text)


def monkeypatch_getpass(monkeypatch):
    if IS_PY3:
        monkeypatch.setattr(getpass, "getpass", input)
    else:
        monkeypatch.setattr(getpass, "getpass",
            raw_input)  # pylint: disable=undefined-variable


def open_functional_bz(bzclass, url, kwargs):
    bz = bzclass(url, **kwargs)

    if kwargs.get("force_rest", False):
        assert bz.is_rest() is True
    if kwargs.get("force_xmlrpc", False):
        assert bz.is_xmlrpc() is True

    # Set a session timeout of 30 seconds
    session = bz.get_requests_session()
    origrequest = session.request

    def fake_request(*args, **kwargs):
        if "timeout" not in kwargs:
            kwargs["timeout"] = 60
        return origrequest(*args, **kwargs)

    session.request = fake_request
    return bz


def diff_compare(inputdata, filename):
    """Compare passed string output to contents of filename"""
    filename = tests_path(filename)

    actual_out = inputdata
    if isinstance(inputdata, dict):
        actual_out = pprint.pformat(inputdata, width=81)
    if not actual_out.endswith("\n"):
        actual_out += "\n"

    if not os.path.exists(filename) or tests.CLICONFIG.REGENERATE_OUTPUT:
        open(filename, "w").write(actual_out)
    expect_out = open(filename).read()

    diff = "".join(difflib.unified_diff(expect_out.splitlines(1),
                                        actual_out.splitlines(1),
                                        fromfile=filename or '',
                                        tofile="Generated Output"))
    if diff:
        raise AssertionError("Conversion outputs did not match.\n%s" % diff)


def do_run_cli(capsys, monkeypatch,
               argvstr, bzinstance,
               expectfail=False, stdin=None):
    """
    Run bin/bugzilla.main() directly with passed argv
    """
    argv = shlex.split(argvstr)
    monkeypatch.setattr(sys, "argv", argv)
    if stdin:
        monkeypatch.setattr(sys, "stdin", fake_stream(stdin))
    else:
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

    ret = 0
    try:
        # pylint: disable=protected-access
        if bzinstance is None:
            bugzilla._cli.cli()
        else:
            bugzilla._cli.main(unittest_bz_instance=bzinstance)
    except SystemExit as sys_e:
        ret = sys_e.code

    out, err = capsys.readouterr()
    outstr = out + err

    if ret != 0 and not expectfail:
        raise RuntimeError("Command failed with %d\ncmd=%s\nout=%s" %
                           (ret, argvstr, outstr))
    if ret == 0 and expectfail:
        raise RuntimeError("Command succeeded but we expected success\n"
                           "ret=%d\ncmd=%s\nout=%s" %
                           (ret, argvstr, outstr))
    return outstr
