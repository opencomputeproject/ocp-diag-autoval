# pyre-unsafe
import asyncio
import inspect
from typing import Awaitable, Callable, Dict, List, NamedTuple, Union


class AsyncJob(NamedTuple):
    func: Union[Callable, Awaitable]
    args: List = []
    kwargs: Dict = {}

    async def run_as_awaitable(self):
        if inspect.iscoroutinefunction(self.func):
            return await self.func(*self.args, **self.kwargs)
        return self.func(*self.args, **self.kwargs)


class AsyncUtils:
    # TODO: if there is a time.sleep() within any code_ref
    # code won't run in parallel
    # Check that here and raise some exception if that's the case

    @staticmethod
    def run_async_jobs(jobs: List[AsyncJob]):
        results = [None for job in jobs]
        asyncio.set_event_loop(asyncio.new_event_loop())
        loop = asyncio.get_event_loop()
        try:
            # TODO use asyncio.run() when python 3.7 is enabled on platform007
            # current usage is forward compatible with 3.7
            loop.run_until_complete(
                asyncio.gather(
                    *[
                        # pyre-fixme[6]: Expected `Awaitable[typing.Any]` for 1st
                        #  param but got `() -> Coroutine[typing.Any, typing.Any,
                        #  typing.Any]`.
                        AsyncUtils.run_async(code_ref.run_as_awaitable, results, index)
                        for index, code_ref in enumerate(jobs)
                    ]
                )
            )
        finally:
            loop.close()
        return results

    @staticmethod
    async def run_async(
        code_ref: Awaitable,
        results: List,
        code_ref_index: int,
    ) -> None:
        # pyre-fixme[29]: `Awaitable[typing.Any]` is not a function.
        results[code_ref_index] = await code_ref()
