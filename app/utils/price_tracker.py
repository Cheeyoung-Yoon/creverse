# app/utils/price_tracker.py
from typing import Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
import json

@dataclass
class TokenUsage:
    """Track token usage for a single API call."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    
    def __add__(self, other: 'TokenUsage') -> 'TokenUsage':
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens
        )

@dataclass
class PriceTracker:
    """Track API costs and usage statistics."""
    
    # GPT-4o mini pricing (as of task date)
    input_cost_per_1m: float = 0.250  # $0.250 per 1M input tokens
    output_cost_per_1m: float = 2.0  # $2.000 per 1M output tokens
    
    total_usage: TokenUsage = field(default_factory=TokenUsage)
    session_calls: int = 0
    session_start: datetime = field(default_factory=datetime.now)
    call_history: list = field(default_factory=list)
    
    def track_usage(self, usage_data: Dict[str, Any], operation: str = "evaluation") -> Dict[str, Any]:
        """Track usage from an API response and calculate costs."""
        
        # Extract token usage
        prompt_tokens = usage_data.get("prompt_tokens", 0)
        completion_tokens = usage_data.get("completion_tokens", 0)
        total_tokens = usage_data.get("total_tokens", 0)
        
        # Create usage object
        call_usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens
        )
        
        # Calculate costs
        input_cost = (prompt_tokens / 1000000) * self.input_cost_per_1m
        output_cost = (completion_tokens / 1000000) * self.output_cost_per_1m
        total_cost = input_cost + output_cost
        
        # Update totals
        self.total_usage += call_usage
        self.session_calls += 1
        
        # Record call history
        call_record = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "usage": call_usage.__dict__,
            "cost": {
                "input_cost": round(input_cost, 9),
                "output_cost": round(output_cost, 9),
                "total_cost": round(total_cost, 9)
            }
        }
        self.call_history.append(call_record)
        
        return call_record
    
    def get_session_summary(self) -> Dict[str, Any]:
        """Get summary of current session usage and costs."""
        
        # Calculate total costs
        total_input_cost = (self.total_usage.prompt_tokens / 1000) * self.input_cost_per_1m
        total_output_cost = (self.total_usage.completion_tokens / 1000) * self.output_cost_per_1m
        total_session_cost = total_input_cost + total_output_cost
        
        # Calculate session duration
        session_duration = datetime.now() - self.session_start
        
        return {
            "session_info": {
                "start_time": self.session_start.isoformat(),
                "duration_seconds": session_duration.total_seconds(),
                "total_calls": self.session_calls
            },
            "token_usage": {
                "total_prompt_tokens": self.total_usage.prompt_tokens,
                "total_completion_tokens": self.total_usage.completion_tokens,
                "total_tokens": self.total_usage.total_tokens,
                "avg_tokens_per_call": self.total_usage.total_tokens / max(1, self.session_calls)
            },
            "cost_breakdown": {
                "input_cost": round(total_input_cost, 6),
                "output_cost": round(total_output_cost, 6),
                "total_cost": round(total_session_cost, 6),
                "avg_cost_per_call": round(total_session_cost / max(1, self.session_calls), 6)
            },
            "pricing_info": {
                "input_cost_per_1m_tokens": self.input_cost_per_1m,
                "output_cost_per_1m_tokens": self.output_cost_per_1m,
                "model": "gpt-4o-mini"
            }
        }
    
    def export_history(self, filepath: str) -> None:
        """Export call history to JSON file."""
        export_data = {
            "session_summary": self.get_session_summary(),
            "call_history": self.call_history
        }
        
        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
    
    def reset_session(self) -> None:
        """Reset tracking for a new session."""
        self.total_usage = TokenUsage()
        self.session_calls = 0
        self.session_start = datetime.now()
        self.call_history = []

# Global tracker instance
_global_tracker = PriceTracker()

def get_price_tracker() -> PriceTracker:
    """Get the global price tracker instance."""
    return _global_tracker

def track_api_usage(usage_data: Dict[str, Any], operation: str = "evaluation") -> Dict[str, Any]:
    """Convenience function to track API usage globally."""
    return _global_tracker.track_usage(usage_data, operation)

def get_usage_summary() -> Dict[str, Any]:
    """Convenience function to get usage summary."""
    return _global_tracker.get_session_summary()
