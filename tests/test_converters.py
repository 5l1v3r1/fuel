import os

import h5py
import numpy
from numpy.testing import assert_equal, assert_raises

from fuel.converters.base import fill_hdf5_file
from fuel.converters import binarized_mnist


class TestFillHDF5File(object):
    def setUp(self):
        self.h5file = h5py.File(
            'file.hdf5', mode='w', driver='core', backing_store=False)
        self.train_features = numpy.arange(
            16, dtype='uint8').reshape((4, 2, 2))
        self.test_features = numpy.arange(
            8, dtype='uint8').reshape((2, 2, 2)) + 3
        self.train_targets = numpy.arange(
            4, dtype='float32').reshape((4, 1))
        self.test_targets = numpy.arange(
            2, dtype='float32').reshape((2, 1)) + 3

    def tearDown(self):
        self.h5file.close()

    def test_data(self):
        fill_hdf5_file(
            self.h5file,
            (('train', 'features', self.train_features),
             ('train', 'targets', self.train_targets),
             ('test', 'features', self.test_features),
             ('test', 'targets', self.test_targets)))
        assert_equal(self.h5file['features'],
                     numpy.vstack([self.train_features, self.test_features]))
        assert_equal(self.h5file['targets'],
                     numpy.vstack([self.train_targets, self.test_targets]))

    def test_dtype(self):
        fill_hdf5_file(
            self.h5file,
            (('train', 'features', self.train_features),
             ('train', 'targets', self.train_targets),
             ('test', 'features', self.test_features),
             ('test', 'targets', self.test_targets)))
        assert_equal(str(self.h5file['features'].dtype), 'uint8')
        assert_equal(str(self.h5file['targets'].dtype), 'float32')

    def test_multiple_length_error(self):
        train_targets = numpy.arange(8, dtype='float32').reshape((8, 1))
        assert_raises(ValueError, fill_hdf5_file, self.h5file,
                      (('train', 'features', self.train_features),
                       ('train', 'targets', train_targets)))

    def test_multiple_dtype_error(self):
        test_features = numpy.arange(8, dtype='float32').reshape((2, 2, 2)) + 3
        assert_raises(
            ValueError, fill_hdf5_file, self.h5file,
            (('train', 'features', self.train_features),
             ('test', 'features', test_features)))

    def test_multiple_shape_error(self):
        test_features = numpy.arange(16, dtype='float32').reshape((2, 4, 2)) + 3
        assert_raises(
            ValueError, fill_hdf5_file, self.h5file,
            (('train', 'features', self.train_features),
             ('test', 'features', test_features)))


class TestBinarizedMNIST(object):
    def setUp(self):
        numpy.random.seed(9 + 5 + 2015)
        self.train_mock = numpy.random.randint(0, 2, (5, 784))
        self.valid_mock = numpy.random.randint(0, 2, (5, 784))
        self.test_mock = numpy.random.randint(0, 2, (5, 784))
        numpy.savetxt('binarized_mnist_train.amat', self.train_mock)
        numpy.savetxt('binarized_mnist_valid.amat', self.valid_mock)
        numpy.savetxt('binarized_mnist_test.amat', self.test_mock)

    def tearDown(self):
        os.remove('binarized_mnist_train.amat')
        os.remove('binarized_mnist_valid.amat')
        os.remove('binarized_mnist_test.amat')
        os.remove('mock_binarized_mnist.hdf5')

    def test_converter(self):
        binarized_mnist('.', 'mock_binarized_mnist.hdf5')
        h5file = h5py.File('mock_binarized_mnist.hdf5', mode='r')
        assert_equal(h5file['features'][...],
                     numpy.vstack([self.train_mock, self.valid_mock,
                                   self.test_mock]).reshape((-1, 1, 28, 28)))
        assert_equal(str(h5file['features'].dtype), 'uint8')
        assert_equal(tuple(dim.label for dim in h5file['features'].dims),
                     ('batch', 'channel', 'height', 'width'))
