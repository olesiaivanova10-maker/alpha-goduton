from contextvars import ContextVar

request_context = ContextVar("request_id", default="worker")
company_context = ContextVar("company_id", default=None)
job_context = ContextVar("job_id", default=None)
