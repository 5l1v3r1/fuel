import os
import shutil

import certifi
import urllib3
from urllib3.util.url import parse_url


class NeedURLPrefix(Exception):
    """Raised when a URL is not provided for a file."""
    pass


def filename_from_url(url, path=None):
    """Parses a URL to determine a file name.

    Parameters
    ----------
    url : str
        URL to parse.

    """
    http = urllib3.PoolManager(
        cert_reqs='CERT_REQUIRED', ca_certs=certifi.where())
    with http.request('GET', url, preload_content=False) as response:
        headers = response.getheaders()
        if 'Content-Disposition' in headers:
            filename = headers[
                'Content-Disposition'].split('filename=')[1].trim('"')
        else:
            filename = os.path.basename(parse_url(url).path)
    return filename


def download(url, file_handle):
    """Downloads a given URL to a specific file.

    Parameters
    ----------
    url : str
        URL to download.
    file_handle : file
        Where to save the downloaded URL.

    """
    http = urllib3.PoolManager(
        cert_reqs='CERT_REQUIRED', ca_certs=certifi.where())
    with http.request('GET', url, preload_content=False) as response:
        shutil.copyfileobj(response, file_handle)


def default_downloader(directory, urls, filenames, url_prefix=None,
                       clear=False):
    """Downloads or clears files from URLs and filenames.

    Parameters
    ----------
    directory : str
        The directory in which downloaded files are saved.
    urls : list
        A list of URLs to download.
    filenames : list
        A list of file names for the corresponding URLs.
    url_prefix : str, optional
        If provided, this is prepended to filenames that
        lack a corresponding URL.
    clear : bool, optional
        If `True`, delete the given filenames from the given
        directory rather than download them.

    """
    # Parse file names from URL if not provided
    for i, url in enumerate(urls):
        filename = filenames[i]
        if not filename:
            filename = filename_from_url(url)
        if not filename:
            raise ValueError("no filename available for URL '{}'".format(url))
        filenames[i] = filename
    files = [os.path.join(directory, f) for f in filenames]

    if clear:
        for f in files:
            if os.path.isfile(f):
                os.remove(f)
    else:
        for url, f in zip(urls, files):
            if not url:
                if url_prefix is None:
                    raise NeedURLPrefix
                url = url_prefix + filename
            with open(f, 'wb') as file_handle:
                download(url, file_handle)
