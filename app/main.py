from fastapi import FastAPI

app = FastAPI(
    title="BantenPedia RAG API",
    description="Backend API for BantenPedia AI assistant",
    version="0.1.0",
)


@app.get("/health")
def health_check():
    return {"status": "ok"}