class OrbitError(Exception):
    """Base application exception."""


class ValidationError(OrbitError):
    pass


class RiskViolation(OrbitError):
    pass


class NotFoundError(OrbitError):
    pass


class InvalidOrderState(OrbitError):
    pass
