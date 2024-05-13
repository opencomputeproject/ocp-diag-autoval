#!/usr/bin/env python3

import argparse
import importlib
import json
import os
import sys
import tempfile
from shutil import rmtree

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Runs remote modules")
    parser.add_argument("-m", "--module", type=str, dest="module_name", default=None)
    parser.add_argument("-c", "--class", type=str, dest="class_name", default=None)
    parser.add_argument("-f", "--function", type=str, dest="function_name")
    parser.add_argument("-p", "--params", dest="params", nargs="+")
    args = parser.parse_args()
    if args.module_name is None or args.function_name is None:
        raise Exception(
            "-m/--module, -f/--function is required to execute remote module"
        )
    _module = importlib.import_module(args.module_name)
    if args.class_name is not None:
        try:
            _class = getattr(_module, args.class_name)
        except AttributeError:
            raise Exception("%s class not found" % args.class_name)
    else:
        _class = _module
    _method = getattr(_class, args.function_name)

    tmpdir = tempfile.mkdtemp(prefix="autoval_module_runner_")
    os.chdir(tmpdir)
    if args.params is not None:
        data = _method(*args.params)
    else:
        data = _method()
    rmtree(tmpdir, ignore_errors=True)
    data_json = json.dumps(data)
    print(data_json)
