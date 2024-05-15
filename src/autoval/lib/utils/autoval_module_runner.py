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
    # pyre-fixme[5]: Global expression must be annotated.
    args = parser.parse_args()
    if args.module_name is None or args.function_name is None:
        raise Exception(
            "-m/--module, -f/--function is required to execute remote module"
        )
    # pyre-fixme[5]: Global expression must be annotated.
    _module = importlib.import_module(args.module_name)
    if args.class_name is not None:
        try:
            # pyre-fixme[5]: Global expression must be annotated.
            _class = getattr(_module, args.class_name)
        except AttributeError:
            raise Exception("%s class not found" % args.class_name)
    else:
        _class = _module
    # pyre-fixme[5]: Global expression must be annotated.
    _method = getattr(_class, args.function_name)

    # pyre-fixme[5]: Global expression must be annotated.
    tmpdir = tempfile.mkdtemp(prefix="autoval_module_runner_")
    os.chdir(tmpdir)
    if args.params is not None:
        # pyre-fixme[5]: Global expression must be annotated.
        data = _method(*args.params)
    else:
        data = _method()
    rmtree(tmpdir, ignore_errors=True)
    # pyre-fixme[5]: Global expression must be annotated.
    data_json = json.dumps(data)
    print(data_json)
