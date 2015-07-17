class ConfigurationError(Exception):
    """Error raised when a configuration value is requested but not set."""


class MissingInputFiles(Exception):
    """Exception raised by a converter when input files are not found.

    Parameters
    ----------
    filenames : list
        A list of filenames that were not found.

    """
    def __init__(self, message, filenames):
        self.filenames = filenames
        super(MissingInputFiles, self).__init__(message, filenames)


class NeedURLPrefix(Exception):
    """Raised when a URL is not provided for a file."""
