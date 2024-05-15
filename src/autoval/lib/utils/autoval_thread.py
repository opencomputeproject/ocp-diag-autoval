#!/usr/bin/env python3

import threading
from threading import Barrier
from typing import Any, Callable, List, Optional, Tuple

try:
    import queue
except Exception:
    import Queue as queue  # pyre-fixme

from autoval.lib.utils.autoval_exceptions import TestError
from autoval.lib.utils.autoval_log import AutovalLog


class AutovalThreadError(TestError):
    """
    Exception for errors occuring within an Autoval Thread.
    """

    # pyre-fixme[3]: Return type must be annotated.
    def __init__(
        self,
        message: str = "AutoVal Thread Error",
        # pyre-fixme[2]: Parameter must be annotated.
        component=None,
        # pyre-fixme[2]: Parameter must be annotated.
        error_type=None,
    ):
        super().__init__(message=message, error_type=error_type, component=component)


class AutovalThread(threading.Thread):
    # pyre-fixme[2]: Parameter must be annotated.
    def __init__(self, exception_queue, target, *args, barrier=None, **kwargs) -> None:
        threading.Thread.__init__(self)
        # pyre-fixme[4]: Attribute must be annotated.
        self.exception_queue = exception_queue
        # pyre-fixme[4]: Attribute must be annotated.
        self._autoval_target = target
        # pyre-fixme[4]: Attribute must be annotated.
        self._autoval_args = args
        # pyre-fixme[4]: Attribute must be annotated.
        self._autoval_kwargs = kwargs
        # pyre-fixme[4]: Attribute must be annotated.
        self._barrier = barrier
        # pyre-fixme[4]: Attribute must be annotated.
        self._return = None

    def run(self) -> None:
        try:
            if self._barrier:
                self._barrier.wait()
            self._return = self._autoval_target(
                *self._autoval_args, **self._autoval_kwargs
            )
        except Exception as e:
            AutovalLog.log_error(
                "Exception in %s - %s" % (self._autoval_target, str(e))
            )
            self.exception_queue.put(e)
            raise

    @staticmethod
    # pyre-fixme[3]: Return type must be annotated.
    def start_autoval_thread(
        # pyre-fixme[24]: Generic type `Callable` expects 2 type parameters.
        target: Callable,
        *def_args: Any,
        barrier: Optional[Barrier] = None,
        threadname: str = "AutovalThread",
        **def_kwargs: Any,
    ):
        """
        Start an AutovalThread and return the thread object and a queue.
        Args:
            target (callable): The callable object to be invoked by the run() method.
            def_args (tuple): Default positional arguments for the target function.
            barrier (threading.Barrier, optional): A barrier object that the thread will wait on before starting. Defaults to None.
            threadname (str, optional): The name of the thread. Defaults to "AutovalThread".
            def_kwargs (dict, optional): Default keyword arguments for the target function.
        Returns:
            tuple: A tuple containing the AutovalThread object and a queue.
        """
        _q = queue.Queue()
        _t = AutovalThread(_q, target, *def_args, barrier=barrier, **def_kwargs)
        _t.setName(threadname)
        _t.start()
        return (_t, _q)

    @staticmethod
    # pyre-fixme[3]: Return type must be annotated.
    def wait_for_autoval_thread(
        # pyre-fixme[2]: Parameter must be annotated.
        queue_thread_list,
        timeout: Optional[int] = None,
    ):
        """
        The function takes the list of tuples returned from above function as input
        Wait for the threads to finish and raise error if any of the thread fails.
        When a caller waits for multiple threads to complete, this method uses the
        error type information of the first thread, if it exists, in the raised exception

        Args:
            queue_thread_list: List of AutoVal threads to wait
            timeout: Timeout for threads to complete

        Raises:
            AutovalThreadError: If any of one of the thread raises an exception
        """
        errs = []
        results = []
        first_exception = None
        for t, q in queue_thread_list:
            t.join(timeout)
            try:
                exc = q.get(block=False)
                if first_exception is None:
                    first_exception = exc
                error_message = f"Error Msg: {str(exc)}\n"
                errs.append(error_message)
            except queue.Empty:
                results.append(t._return)
        if len(errs) > 0:
            error_type = getattr(first_exception, "error_type", None)
            component = getattr(first_exception, "component", None)
            raise AutovalThreadError(
                message="AutovalThread(s) failed with ::Thread Errors::\n"
                + "\n".join(errs),
                error_type=error_type,
                component=component,
            )
        return results

    @staticmethod
    # pyre-fixme[24]: Generic type `tuple` expects at least 1 type parameter.
    def get_thread_errs(threads: List[Tuple]) -> List[str]:
        """Poll the exceptions from queue of each thread.

        :param threads: pairs (thread, queue) to be traversed
        :type threads: List[Tuple]
        :return: list of errors occurred in threads
        :rtype: List[str]
        """
        errs = []
        for _, q in threads:
            try:
                exc = q.get(block=False)
                errs.append(str(exc))
            except queue.Empty:
                pass
        return errs
