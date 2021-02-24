""" User defined exceptions """


class UserAuthError(Exception):
    """ Exception class for user authentaction failures
    """

    def __init__(self, error, message=None):
        self.error = error
        self.message = message


class UpdateError(Exception):
    """ Exception when updates to objects fail """

    def __init__(self, error, message=None):
        self.error = error
        self.message = message


class InvalidUsage(Exception):
    """ Exception used by API and CGI to return errors """
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['success'] = False
        rv['message'] = self.message
        return rv
