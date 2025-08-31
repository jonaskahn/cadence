"""Data Transfer Objects for analytics and reporting."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TokenUsageStats(BaseModel):
    """Token usage statistics."""

    total_tokens: int = Field(..., ge=0, description="Total tokens used")
    input_tokens: int = Field(..., ge=0, description="Total input tokens")
    output_tokens: int = Field(..., ge=0, description="Total output tokens")
    average_tokens_per_turn: float = Field(..., ge=0, description="Average tokens per conversation turn")
    estimated_cost: float = Field(..., ge=0, description="Estimated total cost in USD")


class UsageByPeriod(BaseModel):
    """Usage statistics for a time period."""

    period: str = Field(..., description="Time period (e.g., '2024-01-15', '2024-01-W03')")
    thread_count: int = Field(..., ge=0, description="Number of threads created")
    turn_count: int = Field(..., ge=0, description="Number of conversation turns")
    token_usage: TokenUsageStats = Field(..., description="Token usage statistics")
    unique_users: int = Field(..., ge=0, description="Number of unique users")


class TopUser(BaseModel):
    """Top user by usage."""

    user_id: str = Field(..., description="User identifier")
    thread_count: int = Field(..., ge=0, description="Number of threads")
    turn_count: int = Field(..., ge=0, description="Number of turns")
    total_tokens: int = Field(..., ge=0, description="Total tokens used")
    estimated_cost: float = Field(..., ge=0, description="Estimated cost")


class AnalyticsRequest(BaseModel):
    """Request for analytics data."""

    start_date: str = Field(..., description="Start date (ISO format: YYYY-MM-DD)")
    end_date: str = Field(..., description="End date (ISO format: YYYY-MM-DD)")
    org_id: Optional[str] = Field(None, description="Filter by organization ID")
    user_id: Optional[str] = Field(None, description="Filter by user ID")
    group_by: str = Field("day", description="Grouping period (day/week/month)")
    include_costs: bool = Field(True, description="Include cost estimates")

    class Config:
        json_schema_extra = {
            "example": {
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
                "org_id": "org_123",
                "group_by": "day",
                "include_costs": True,
            }
        }


class AnalyticsResponse(BaseModel):
    """Analytics dashboard response."""

    summary: TokenUsageStats = Field(..., description="Overall summary statistics")
    usage_by_period: List[UsageByPeriod] = Field(..., description="Usage broken down by time periods")
    top_users: List[TopUser] = Field(..., description="Top users by usage")
    thread_distribution: Dict[str, int] = Field(..., description="Thread count by status/category")
    average_response_time: Optional[float] = Field(None, description="Average processing time in seconds")
    storage_efficiency: Optional[float] = Field(
        None, description="Storage efficiency percentage (vs full message storage)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "summary": {
                    "total_tokens": 125000,
                    "input_tokens": 45000,
                    "output_tokens": 80000,
                    "average_tokens_per_turn": 85.5,
                    "estimated_cost": 12.50,
                },
                "usage_by_period": [
                    {
                        "period": "2024-01-15",
                        "thread_count": 25,
                        "turn_count": 120,
                        "token_usage": {
                            "total_tokens": 5000,
                            "input_tokens": 2000,
                            "output_tokens": 3000,
                            "average_tokens_per_turn": 41.7,
                            "estimated_cost": 0.45,
                        },
                        "unique_users": 15,
                    }
                ],
                "top_users": [
                    {
                        "user_id": "user_123",
                        "thread_count": 10,
                        "turn_count": 45,
                        "total_tokens": 3200,
                        "estimated_cost": 0.32,
                    }
                ],
                "thread_distribution": {"active": 120, "archived": 45},
                "average_response_time": 1.8,
                "storage_efficiency": 85.2,
            }
        }


class SystemHealthResponse(BaseModel):
    """System health and monitoring response."""

    status: str = Field(..., description="Overall system status")
    uptime: float = Field(..., ge=0, description="System uptime in seconds")
    active_threads: int = Field(..., ge=0, description="Number of active threads")
    total_threads: int = Field(..., ge=0, description="Total number of threads")
    avg_response_time_24h: Optional[float] = Field(None, description="24-hour average response time")
    error_rate_24h: float = Field(..., ge=0, le=100, description="24-hour error rate percentage")
    storage_usage: Dict[str, Any] = Field(..., description="Storage usage information")
    available_plugins: List[str] = Field(..., description="List of available plugins")
    healthy_plugins: List[str] = Field(..., description="List of healthy plugins")
    failed_plugins: List[str] = Field(..., description="List of failed plugins")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "operational",
                "uptime": 86400.0,
                "active_threads": 156,
                "total_threads": 2340,
                "avg_response_time_24h": 1.85,
                "error_rate_24h": 0.02,
                "storage_usage": {
                    "total_size_mb": 450.2,
                    "efficiency_percentage": 87.5,
                    "estimated_full_storage_mb": 3601.6,
                },
                "available_plugins": ["search_agent", "math_agent"],
                "healthy_plugins": ["search_agent", "math_agent"],
                "failed_plugins": [],
            }
        }
