from rest_framework.throttling import UserRateThrottle


class InferenceCreateThrottle(UserRateThrottle):
    """Per-user rate limit for creating inference jobs (rate set via
    DEFAULT_THROTTLE_RATES['inference_create']). Guards against accidental or
    abusive bursts of job creation that would multiply expensive AI calls."""

    scope = "inference_create"
