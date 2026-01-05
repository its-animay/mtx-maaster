from fastapi import APIRouter, Depends

from app.api.v1.endpoints import exams, masters, questions, security, test_series, tests
from app.security.rate_limit import RateLimiter

# Default per-key limiter applied to all protected routers
default_limiter = RateLimiter(limit=60, window_seconds=60)

api_router = APIRouter()
# Apply X-API-Key + rate limit to core domain routers
api_router.include_router(masters.router, tags=["masters"], dependencies=[Depends(default_limiter)])
api_router.include_router(exams.router, tags=["exams"], dependencies=[Depends(default_limiter)])
api_router.include_router(questions.router, tags=["questions"], dependencies=[Depends(default_limiter)])
api_router.include_router(test_series.router, tags=["test-series"], dependencies=[Depends(default_limiter)])
api_router.include_router(tests.router, tags=["tests"], dependencies=[Depends(default_limiter)])
api_router.include_router(security.router, tags=["security"])
