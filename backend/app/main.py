from fastapi import FastAPI, HTTPException
from .company_context import get_company_context
from .schemas import CompanyContext

app = FastAPI(title="Alpha Hack Company Context API", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/companies/{company_id}/context", response_model=CompanyContext)
def company_context(company_id: str):
    try:
        return get_company_context(company_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
