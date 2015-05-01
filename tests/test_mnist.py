import os

import numpy

from numpy.testing import assert_raises, assert_equal, assert_allclose

from fuel import config
from fuel.datasets import MNIST
from tests import skip_if_not_available


def test_mnist_train():
    skip_if_not_available(datasets=['mnist.hdf5'])

    dataset = MNIST('train', load_in_memory=False)
    handle = dataset.open()
    data, labels = dataset.get_data(handle, slice(0, 10))
    assert data.dtype == 'uint8'
    assert data.shape == (10, 1, 28, 28)
    known = numpy.array([0, 0, 0, 0, 0, 0, 0, 0, 30, 36, 94, 154, 170, 253,
                         253, 253, 253, 253, 225, 172, 253, 242, 195,  64, 0,
                         0, 0, 0])
    assert_allclose(data[0][0][6], known)
    assert labels[0] == 5
    assert dataset.num_examples == 60000
    dataset.close(handle)


def test_mnist_test():
    skip_if_not_available(datasets=['mnist.hdf5'])

    dataset = MNIST('test', load_in_memory=False)
    handle = dataset.open()
    data, labels = dataset.get_data(handle, slice(0, 10))
    assert data.dtype == 'uint8'
    assert data.shape == (10, 1, 28, 28)
    known = numpy.array([0, 0, 0, 0, 0, 0, 84, 185, 159, 151, 60, 36, 0, 0, 0,
                         0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    assert_allclose(data[0][0][7], known)
    assert labels[0] == 7
    assert dataset.num_examples == 10000
    dataset.close(handle)


def test_mnist_axes():
    skip_if_not_available(datasets=['mnist.hdf5'])

    dataset = MNIST('train', load_in_memory=False)
    assert_equal(dataset.axis_labels['features'],
                 ('batch', 'channel', 'height', 'width'))


def test_mnist_invalid_split():
    skip_if_not_available(datasets=['mnist.hdf5'])

    assert_raises(ValueError, MNIST, 'dummy')


def test_mnist_data_path():
    skip_if_not_available(datasets=['mnist.hdf5'])

    assert MNIST('train').data_path == os.path.join(config.data_path,
                                                    'mnist.hdf5')
