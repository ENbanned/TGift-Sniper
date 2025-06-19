

class GiftSniperError(Exception):
    pass


class ConfigurationError(GiftSniperError):
    pass


class AuthenticationError(GiftSniperError):
    pass


class PurchaseError(GiftSniperError):
    pass


class InsufficientBalanceError(PurchaseError):
    pass
