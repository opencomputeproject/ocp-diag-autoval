import contextvars


# Boolean: if True, AutoVal is called through pytest
ctx_pytest_autoval = contextvars.ContextVar("pytest_autoval", default=False)

ctx_pytest_autoval_results_type = contextvars.ContextVar(
    "pytest_autoval_results_type", default="memory"
)

ctx_pytest_autoval_results = contextvars.ContextVar(
    "pytest_autoval_results", default={}
)

ctx_pytest_autoval_live = contextvars.ContextVar("pytest_autoval_live", default={})
