""" User defined exceptions """


class UserAuthError(Exception):
    """ Exception class for user authentaction failures
    """

    def __init__(self, error, message=None):
        self.error = error
        self.message = message
