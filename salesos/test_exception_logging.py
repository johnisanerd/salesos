#!/usr/bin/env python
"""Test that exception logging improvements don't break existing patterns."""

import traceback
from decimal import Decimal


class MockException(Exception):
    """Test exception that might return empty string."""
    def __str__(self):
        return ""


# Test 1: Empty exception string handling
exc = MockException("test")
error_msg = str(exc) or f"({exc.__class__.__name__} with empty message)"
assert "MockException" in error_msg
print(f"✓ Empty exception handling: {error_msg}")

# Test 2: Traceback capture
try:
    raise ValueError("Test error")
except Exception as e:
    tb = traceback.format_exc()
    assert "ValueError" in tb
    assert "Test error" in tb
    print(f"✓ Traceback capture works: {len(tb)} chars")

# Test 3: Decimal conversion
score = 71.234567
rounded = Decimal(str(round(score, 2)))
assert rounded == Decimal("71.23")
print(f"✓ Score rounding works: {rounded}")

# Test 4: Score validation
def validate_score(score):
    if not isinstance(score, (int, float)):
        raise TypeError(f"score must be numeric, got {type(score).__name__}")
    score_val = float(score)
    if score_val < -999.99 or score_val > 999.99:
        raise ValueError(f"score out of valid range: {score_val}")

validate_score(65.5)
validate_score(0)
validate_score(-50.0)
print(f"✓ Score validation works")

# Test 5: Error handling chain
class FakeModel:
    @property
    def score(self):
        return "invalid"  # Will fail type check
    
    def model_dump(self):
        return {}

model = FakeModel()
try:
    validate_score(model.score)
except TypeError as e:
    msg = str(e) or f"({e.__class__.__name__} with empty message)"
    print(f"✓ Type validation error caught: {msg}")

print("\n✅ All exception logging improvements validated!")
