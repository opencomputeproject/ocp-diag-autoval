#!/usr/bin/env python3

import contextlib
import importlib
import time
from functools import wraps

import autoval.lib.utils.autoval_shared_data as av_data


def retry(tries, sleep_seconds, exponential: bool = False, exceptions=Exception):
    """
    Simple decorator for retrying function call. The function will be called
    until it succeeds for up to num_tries times.

    @param tries: number of tries before failing
    @sleep_seconds: Time in seconds to sleep between attempts
    @exponential: If true will double sleep_seconds between each attempt
    @exceptions: an exception or a tuple of exceptions that if seen will retry;
        raise otherwise
    """

    def decorated_retry(function):
        @wraps(function)
        def function_retry(*args, **kwargs):
            mutable_sleep = sleep_seconds
            mutable_tries = tries

            while mutable_tries > 1:
                try:
                    return function(*args, **kwargs)
                except exceptions:
                    time.sleep(mutable_sleep)
                    if exponential:
                        mutable_sleep *= 2
                    mutable_tries -= 1

            return function(*args, **kwargs)

        return function_retry

    return decorated_retry


@contextlib.contextmanager
def ignored(exceptions, exception_string=None):
    """
    Provide 'with' statement to ignore certain exceptions.

    @param Tuple[Exception]/Exception exceptions: catch these exceptions
    @param str exception_string: optional; if provided, will ignore exception
        if this string is in the exception message
    """
    exception_string = exception_string if exception_string else ""
    try:
        yield
    except exceptions as e:
        if exception_string in str(e):
            pass
        else:
            raise


class PytestLive:
    def __init__(self, step: str, class_instance):
        self._step = step
        self._class_instance = class_instance
        self._pytest_live = None
        if av_data.ctx_pytest_autoval.get():
            live_info = av_data.ctx_pytest_autoval_live.get()
            if live_info.get("module_name") is not None:
                self._pytest_live = importlib.import_module(live_info["module_name"])

    def __enter__(self):
        if self._pytest_live is not None:
            self._pytest_live.run_live_validation(
                step=self._step, phase="pre", class_instance=self._class_instance
            )

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._pytest_live is not None:
            self._pytest_live.run_live_validation(
                step=self._step, phase="post", class_instance=self._class_instance
            )
