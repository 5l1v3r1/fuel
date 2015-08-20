from fuel.downloaders.base import default_downloader


def fill_subparser(subparser):
    """Set up a subparser to download the adult dataset file.

    The Iris dataset file `adult.data` and `adult.test` is downloaded from
    the UCI Machine Learning Repository [UCI].

    .. [UCI] https://archive.ics.uci.edu/ml/datasets/Adult

    Parameters
    ----------
    subparser : :class:`argparse.ArgumentParser`
        Subparser handling the adult command.

    """
    subparser.set_defaults(
        func=default_downloader,
        urls=['https://archive.ics.uci.edu/ml/machine-learning-databases/'
              'adult/adult.data',
              'https://archive.ics.uci.edu/ml/machine-learning-databases/'
              'adult/adult.test'],
        filenames=['adult.data', 'adult.test'])
