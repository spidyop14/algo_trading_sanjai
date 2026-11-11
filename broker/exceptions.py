class BrokerError(Exception): pass
class AuthenticationRequired(BrokerError): pass
class TokenExpired(BrokerError): pass
class LiveExecutionDisabled(BrokerError): pass
