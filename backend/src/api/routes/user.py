"""User and authentication API endpoints."""

from fastapi import APIRouter

router = APIRouter(tags=["user"])


@router.get("/user/me")
async def get_current_user():
    return {"email": "user@example.com", "subscription_tier": "free",
            "reports_this_month": 0, "reports_limit": 3}


@router.get("/user/usage")
async def user_usage():
    return {"reports_generated": 0, "reports_limit": 3}
