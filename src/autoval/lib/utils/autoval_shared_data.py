import contextvars


# Boolean: if True, AutoVal is called through pytest
# pyre-fixme[5]: Global expression must be annotated.
ctx_pytest_autoval = contextvars.ContextVar("pytest_autoval", default=False)

# pyre-fixme[5]: Global expression must be annotated.
ctx_pytest_autoval_results_type = contextvars.ContextVar(
    "pytest_autoval_results_type", default="memory"
)

# pyre-fixme[5]: Global expression must be annotated.
ctx_pytest_autoval_results = contextvars.ContextVar(
    "pytest_autoval_results", default={}
)

# pyre-fixme[5]: Global expression must be annotated.
ctx_pytest_autoval_live = contextvars.ContextVar("pytest_autoval_live", default={})
