from fastapi import FastAPI
from app.api.routes import router as api_router

app = FastAPI(
    title="Razorpay IntentGuard Proxy",
    description="Agentic Intent Verification Gateway for Razorpay API",
    version="1.0.0"
)

# Attach routes
app.include_router(api_router)

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "razorpay-intentguard-proxy"}