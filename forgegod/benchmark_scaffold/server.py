"""Minimal FastAPI app — benchmark scaffold."""

from fastapi import FastAPI

app = FastAPI(title="Benchmark App")


@app.get("/")
async def root():
    return {"message": "Hello from benchmark scaffold"}
