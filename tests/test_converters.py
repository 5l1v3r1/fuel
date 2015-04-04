import h5py
import numpy
from numpy.testing import assert_equal

from fuel.converters.base import fill_hdf5_file


def test_fill_hdf5_file():
    h5file = h5py.File(
        'tmp.hdf5', mode="w", driver='core', backing_store=False)
    train_features = numpy.arange(16, dtype='uint8').reshape((4, 2, 2))
    test_features = numpy.arange(8, dtype='uint8').reshape((2, 2, 2)) + 3
    train_targets = numpy.arange(4, dtype='float32').reshape((4, 1))
    test_targets = numpy.arange(2, dtype='float32').reshape((2, 1)) + 3
    data = ((train_features, test_features), (train_targets, test_targets))
    source_names = ('features', 'targets')
    shapes = ((6, 2, 2), (6, 1))
    dtypes = ('uint8', 'float32')
    split_names = ('train', 'test')
    splits = ((0, 4), (4, 6))
    fill_hdf5_file(
        h5file, data, source_names, shapes, dtypes, split_names, splits)
    assert_equal(h5file.attrs['train'], [0, 4])
    assert_equal(h5file.attrs['test'], [4, 6])
    assert_equal(
        h5file['features'], numpy.vstack([train_features, test_features]))
    assert_equal(
        h5file['targets'], numpy.vstack([train_targets, test_targets]))
    assert h5file['features'].dtype == 'uint8'
    assert h5file['targets'].dtype == 'float32'
    h5file.close()
