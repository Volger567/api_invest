class WrongToken:
    class OnlyOneError(Exception):
        pass


class PermissionDeniedError(Exception):
    pass


class UnauthorizedError(Exception):
    pass


class UnknownError(Exception):
    pass
