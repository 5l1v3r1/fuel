from __future__ import print_function
import argparse
import gzip
import mock
import os
import shutil
import struct
import tarfile
import tempfile

import h5py
import numpy
import six
from numpy.testing import assert_equal, assert_raises
from scipy.io import savemat
from six.moves import range, zip, cPickle

from fuel.converters.base import (fill_hdf5_file, check_exists,
                                  MissingInputFiles)
from fuel.converters import binarized_mnist, cifar10, mnist, cifar100, svhn

if six.PY3:
    getbuffer = memoryview
else:
    getbuffer = numpy.getbuffer


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
            (('train', 'features', self.train_features, '.'),
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
        test_features = numpy.arange(
            8, dtype='float32').reshape((2, 2, 2)) + 3
        assert_raises(
            ValueError, fill_hdf5_file, self.h5file,
            (('train', 'features', self.train_features),
             ('test', 'features', test_features)))

    def test_multiple_shape_error(self):
        test_features = numpy.arange(
            16, dtype='uint8').reshape((2, 4, 2)) + 3
        assert_raises(
            ValueError, fill_hdf5_file, self.h5file,
            (('train', 'features', self.train_features),
             ('test', 'features', test_features)))


class TestMNIST(object):
    def setUp(self):
        MNIST_IMAGE_MAGIC = 2051
        MNIST_LABEL_MAGIC = 2049
        numpy.random.seed(9 + 5 + 2015)
        self.train_features_mock = numpy.random.randint(
            0, 256, (10, 1, 28, 28)).astype('uint8')
        self.train_targets_mock = numpy.random.randint(
            0, 10, (10, 1)).astype('uint8')
        self.test_features_mock = numpy.random.randint(
            0, 256, (10, 1, 28, 28)).astype('uint8')
        self.test_targets_mock = numpy.random.randint(
            0, 10, (10, 1)).astype('uint8')
        self.tempdir = tempfile.mkdtemp()
        self.train_images_path = os.path.join(
            self.tempdir, 'train-images-idx3-ubyte.gz')
        self.train_labels_path = os.path.join(
            self.tempdir, 'train-labels-idx1-ubyte.gz')
        self.test_images_path = os.path.join(
            self.tempdir, 't10k-images-idx3-ubyte.gz')
        self.test_labels_path = os.path.join(
            self.tempdir, 't10k-labels-idx1-ubyte.gz')
        self.wrong_images_path = os.path.join(self.tempdir, 'wrong_images.gz')
        self.wrong_labels_path = os.path.join(self.tempdir, 'wrong_labels.gz')
        with gzip.open(self.train_images_path, 'wb') as f:
            f.write(struct.pack('>iiii', *(MNIST_IMAGE_MAGIC, 10, 28, 28)))
            f.write(getbuffer(self.train_features_mock.flatten()))
        with gzip.open(self.train_labels_path, 'wb') as f:
            f.write(struct.pack('>ii', *(MNIST_LABEL_MAGIC, 10)))
            f.write(getbuffer(self.train_targets_mock.flatten()))
        with gzip.open(self.test_images_path, 'wb') as f:
            f.write(struct.pack('>iiii', *(MNIST_IMAGE_MAGIC, 10, 28, 28)))
            f.write(getbuffer(self.test_features_mock.flatten()))
        with gzip.open(self.test_labels_path, 'wb') as f:
            f.write(struct.pack('>ii', *(MNIST_LABEL_MAGIC, 10)))
            f.write(getbuffer(self.test_targets_mock.flatten()))
        with gzip.open(self.wrong_images_path, 'wb') as f:
            f.write(struct.pack('>iiii', *(2000, 10, 28, 28)))
        with gzip.open(self.wrong_labels_path, 'wb') as f:
            f.write(struct.pack('>ii', *(2000, 10)))

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def test_converter(self):
        filename = os.path.join(self.tempdir, 'mock_mnist.hdf5')
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        subparser = subparsers.add_parser('mnist')
        subparser.set_defaults(
            directory=self.tempdir, output_file=filename)
        mnist.fill_subparser(subparser)
        args = parser.parse_args(['mnist'])
        args_dict = vars(args)
        func = args_dict.pop('func')
        func(**args_dict)
        h5file = h5py.File(filename, mode='r')
        assert_equal(
            h5file['features'][...],
            numpy.vstack(
                [self.train_features_mock, self.test_features_mock]))
        assert_equal(
            h5file['targets'][...],
            numpy.vstack([self.train_targets_mock, self.test_targets_mock]))
        assert_equal(str(h5file['features'].dtype), 'uint8')
        assert_equal(str(h5file['targets'].dtype), 'uint8')
        assert_equal(tuple(dim.label for dim in h5file['features'].dims),
                     ('batch', 'channel', 'height', 'width'))
        assert_equal(tuple(dim.label for dim in h5file['targets'].dims),
                     ('batch', 'index'))

    def test_wrong_image_magic(self):
        assert_raises(
            ValueError, mnist.read_mnist_images, self.wrong_images_path)

    def test_wrong_label_magic(self):
        assert_raises(
            ValueError, mnist.read_mnist_labels, self.wrong_labels_path)

    def test_read_image_bool(self):
        assert_equal(mnist.read_mnist_images(self.train_images_path, 'bool'),
                     self.train_features_mock >= 128)

    def test_read_image_float(self):
        rval = mnist.read_mnist_images(self.train_images_path, 'float32')
        assert_equal(rval, self.train_features_mock.astype('float32') / 255.)
        assert_equal(str(rval.dtype), 'float32')

    def test_read_image_value_error(self):
        assert_raises(ValueError, mnist.read_mnist_images,
                      self.train_images_path, 'int32')


class TestBinarizedMNIST(object):
    def setUp(self):
        numpy.random.seed(9 + 5 + 2015)
        self.train_mock = numpy.random.randint(0, 2, (5, 784))
        self.valid_mock = numpy.random.randint(0, 2, (5, 784))
        self.test_mock = numpy.random.randint(0, 2, (5, 784))
        self.tempdir = tempfile.mkdtemp()
        numpy.savetxt(
            os.path.join(self.tempdir, 'binarized_mnist_train.amat'),
            self.train_mock)
        numpy.savetxt(
            os.path.join(self.tempdir, 'binarized_mnist_valid.amat'),
            self.valid_mock)
        numpy.savetxt(
            os.path.join(self.tempdir, 'binarized_mnist_test.amat'),
            self.test_mock)

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def test_converter(self):
        filename = os.path.join(self.tempdir, 'mock_binarized_mnist.hdf5')
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        subparser = subparsers.add_parser('binarized_mnist')
        subparser.set_defaults(directory=self.tempdir, output_file=filename)
        binarized_mnist.fill_subparser(subparser)
        args = parser.parse_args(['binarized_mnist'])
        args_dict = vars(args)
        func = args_dict.pop('func')
        func(**args_dict)
        h5file = h5py.File(filename, mode='r')
        assert_equal(h5file['features'][...],
                     numpy.vstack([self.train_mock, self.valid_mock,
                                   self.test_mock]).reshape((-1, 1, 28, 28)))
        assert_equal(str(h5file['features'].dtype), 'uint8')
        assert_equal(tuple(dim.label for dim in h5file['features'].dims),
                     ('batch', 'channel', 'height', 'width'))


class TestCIFAR10(object):
    def setUp(self):
        numpy.random.seed(9 + 5 + 2015)
        self.train_features_mock = [
            numpy.random.randint(0, 256, (10, 3, 32, 32)).astype('uint8')
            for i in range(5)]
        self.train_targets_mock = [
            numpy.random.randint(0, 10, (10,)).astype('uint8')
            for i in range(5)]
        self.test_features_mock = numpy.random.randint(
            0, 256, (10, 3, 32, 32)).astype('uint8')
        self.test_targets_mock = numpy.random.randint(
            0, 10, (10,)).astype('uint8')
        self.tempdir = tempfile.mkdtemp()
        cwd = os.getcwd()
        os.chdir(self.tempdir)
        os.mkdir('cifar-10-batches-py')
        for i, (x, y) in enumerate(zip(self.train_features_mock,
                                       self.train_targets_mock)):
            filename = os.path.join(
                'cifar-10-batches-py', 'data_batch_{}'.format(i + 1))
            with open(filename, 'wb') as f:
                cPickle.dump({'data': x, 'labels': y}, f)
        filename = os.path.join('cifar-10-batches-py', 'test_batch')
        with open(filename, 'wb') as f:
            cPickle.dump({'data': self.test_features_mock,
                          'labels': self.test_targets_mock},
                         f)
        with tarfile.open('cifar-10-python.tar.gz', 'w:gz') as tar_file:
            tar_file.add('cifar-10-batches-py')
        os.chdir(cwd)

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def test_converter(self):
        filename = os.path.join(self.tempdir, 'mock_cifar10.hdf5')
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        subparser = subparsers.add_parser('cifar10')
        subparser.set_defaults(directory=self.tempdir, output_file=filename)
        cifar10.fill_subparser(subparser)
        args = parser.parse_args(['cifar10'])
        args_dict = vars(args)
        func = args_dict.pop('func')
        func(**args_dict)
        h5file = h5py.File(filename, mode='r')
        assert_equal(
            h5file['features'][...],
            numpy.vstack(
                self.train_features_mock + [self.test_features_mock]))
        assert_equal(
            h5file['targets'][...],
            numpy.hstack(self.train_targets_mock +
                         [self.test_targets_mock]).reshape((-1, 1)))
        assert_equal(str(h5file['features'].dtype), 'uint8')
        assert_equal(str(h5file['targets'].dtype), 'uint8')
        assert_equal(tuple(dim.label for dim in h5file['features'].dims),
                     ('batch', 'channel', 'height', 'width'))
        assert_equal(tuple(dim.label for dim in h5file['targets'].dims),
                     ('batch', 'index'))


class TestCIFAR100(object):
    def setUp(self):
        numpy.random.seed(9 + 5 + 2015)
        self.train_features_mock = numpy.random.randint(
            0, 256, (10, 3, 32, 32)).astype('uint8')
        self.train_fine_labels_mock = numpy.random.randint(
            0, 100, (10,)).astype('uint8')
        self.train_coarse_labels_mock = numpy.random.randint(
            0, 20, (10,)).astype('uint8')
        self.test_features_mock = numpy.random.randint(
            0, 256, (10, 3, 32, 32)).astype('uint8')
        self.test_fine_labels_mock = numpy.random.randint(
            0, 100, (10,)).astype('uint8')
        self.test_coarse_labels_mock = numpy.random.randint(
            0, 20, (10,)).astype('uint8')
        self.tempdir = tempfile.mkdtemp()
        cwd = os.getcwd()
        os.chdir(self.tempdir)
        os.mkdir('cifar-100-python')
        filename = os.path.join('cifar-100-python', 'train')
        with open(filename, 'wb') as f:
            cPickle.dump({'data': self.train_features_mock.reshape((10, -1)),
                          'fine_labels': self.train_fine_labels_mock,
                          'coarse_labels': self.train_coarse_labels_mock}, f)
        filename = os.path.join('cifar-100-python', 'test')
        with open(filename, 'wb') as f:
            cPickle.dump({'data': self.test_features_mock.reshape((10, -1)),
                          'fine_labels': self.test_fine_labels_mock,
                          'coarse_labels': self.test_coarse_labels_mock}, f)
        with tarfile.open('cifar-100-python.tar.gz', 'w:gz') as tar_file:
            tar_file.add('cifar-100-python')
        os.chdir(cwd)

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def test_converter(self):
        filename = os.path.join(self.tempdir, 'mock_cifar100.hdf5')
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        subparser = subparsers.add_parser('cifar100')
        subparser.set_defaults(directory=self.tempdir, output_file=filename)
        cifar100.fill_subparser(subparser)
        args = parser.parse_args(['cifar100'])
        args_dict = vars(args)
        func = args_dict.pop('func')
        func(**args_dict)
        h5file = h5py.File(filename, mode='r')
        assert_equal(
            h5file['features'][...],
            numpy.vstack([self.train_features_mock, self.test_features_mock]))
        assert_equal(
            h5file['fine_labels'][...],
            numpy.hstack([self.train_fine_labels_mock,
                          self.test_fine_labels_mock]).reshape((-1, 1)))
        assert_equal(
            h5file['coarse_labels'][...],
            numpy.hstack([self.train_coarse_labels_mock,
                          self.test_coarse_labels_mock]).reshape((-1, 1)))
        assert_equal(str(h5file['features'].dtype), 'uint8')
        assert_equal(str(h5file['fine_labels'].dtype), 'uint8')
        assert_equal(str(h5file['coarse_labels'].dtype), 'uint8')
        assert_equal(tuple(dim.label for dim in h5file['features'].dims),
                     ('batch', 'channel', 'height', 'width'))
        assert_equal(tuple(dim.label for dim in h5file['fine_labels'].dims),
                     ('batch', 'index'))
        assert_equal(tuple(dim.label for dim in h5file['coarse_labels'].dims),
                     ('batch', 'index'))


class TestSVHN(object):
    def setUp(self):
        numpy.random.seed(9 + 5 + 2015)
        self.f1_train_features_mock = numpy.random.randint(
            0, 256, (32, 32, 3, 10)).astype('uint8')
        self.f1_train_targets_mock = numpy.random.randint(
            0, 10, (10, 1)).astype('uint8')
        self.f1_test_features_mock = numpy.random.randint(
            0, 256, (32, 32, 3, 10)).astype('uint8')
        self.f1_test_targets_mock = numpy.random.randint(
            0, 10, (10, 1)).astype('uint8')
        self.f1_extra_features_mock = numpy.random.randint(
            0, 256, (32, 32, 3, 10)).astype('uint8')
        self.f1_extra_targets_mock = numpy.random.randint(
            0, 10, (10, 1)).astype('uint8')
        self.tempdir = tempfile.mkdtemp()
        cwd = os.getcwd()
        os.chdir(self.tempdir)
        savemat('train_32x32.mat', {'X': self.f1_train_features_mock,
                                    'y': self.f1_train_targets_mock})
        savemat('test_32x32.mat', {'X': self.f1_test_features_mock,
                                   'y': self.f1_test_targets_mock})
        savemat('extra_32x32.mat', {'X': self.f1_extra_features_mock,
                                    'y': self.f1_extra_targets_mock})
        with tarfile.open('train.tar.gz', 'w:gz'):
            pass
        with tarfile.open('test.tar.gz', 'w:gz'):
            pass
        with tarfile.open('extra.tar.gz', 'w:gz'):
            pass
        os.chdir(cwd)

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def test_format_1_converter_not_implemented(self):
        assert_raises(NotImplementedError, svhn.convert_svhn_format_1,
                      self.tempdir, 'svhn_format_1.hdf5')

    def test_format_2_converter(self):
        filename = os.path.join(self.tempdir, 'svhn_format_2.hdf5')
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        subparser = subparsers.add_parser('svhn')
        svhn.fill_subparser(subparser)
        subparser.set_defaults(directory=self.tempdir, output_file=filename)
        args = parser.parse_args(['svhn', '2'])
        args_dict = vars(args)
        func = args_dict.pop('func')
        func(**args_dict)
        h5file = h5py.File(filename, mode='r')
        assert_equal(
            h5file['features'][...],
            numpy.vstack([self.f1_train_features_mock.transpose(3, 2, 0, 1),
                          self.f1_test_features_mock.transpose(3, 2, 0, 1),
                          self.f1_extra_features_mock.transpose(3, 2, 0, 1)]))
        assert_equal(
            h5file['targets'][...],
            numpy.vstack([self.f1_train_targets_mock,
                          self.f1_test_targets_mock,
                          self.f1_extra_targets_mock]))
        assert_equal(str(h5file['features'].dtype), 'uint8')
        assert_equal(str(h5file['targets'].dtype), 'uint8')
        assert_equal(tuple(dim.label for dim in h5file['features'].dims),
                     ('batch', 'channel', 'height', 'width'))
        assert_equal(tuple(dim.label for dim in h5file['targets'].dims),
                     ('batch', 'index'))

    @mock.patch('fuel.converters.svhn.convert_svhn_format_1')
    def test_converter_call_format_1(self, mock_converter_format_1):
        svhn.convert_svhn(1, './', 'svhn_format_{}.hdf5')
        mock_converter_format_1.assert_called_with('./', 'svhn_format_1.hdf5')

    @mock.patch('fuel.converters.svhn.convert_svhn_format_2')
    def test_converter_call_format_2(self, mock_converter_format_2):
        svhn.convert_svhn(2, './', 'svhn_format_{}.hdf5')
        mock_converter_format_2.assert_called_with('./', 'svhn_format_2.hdf5')

    def test_converter_error_wrong_format(self):
        assert_raises(ValueError, svhn.convert_svhn, 3, './', 'mock.hdf5')


def test_check_exists():
    try:
        directory = tempfile.mkdtemp()
        with open(os.path.join(directory, 'abcdef.txt'), 'w') as f:
            print('\n', file=f)

        @check_exists(required_files=['abcdef.txt'])
        def foo(directory, a=None, b=None):
            pass
        try:
            foo(directory)
        except MissingInputFiles:
            assert False, "MissingInputFiles raised when files present"

        @check_exists(required_files=['ghijkl.txt'])
        def bar(directory, c=None, d=None):
            pass

        assert_raises(MissingInputFiles, bar, directory)

        @check_exists(required_files=['abcdef.txt', 'ghijkl.txt'])
        def baz(directory, x, y=None):
            pass

        assert_raises(MissingInputFiles, baz, directory, 9)

        try:
            baz(directory, 9)
        except MissingInputFiles as e:
            assert e.filenames == ['ghijkl.txt']

        with open(os.path.join(directory, 'ghijkl.txt'), 'w') as f:
            print('\n\n', file=f)

        try:
            bar(directory)
            baz(directory, 44)
        except MissingInputFiles:
            assert False, "MissingInputFiles raised when files present"

    finally:
        os.remove(os.path.join(directory, 'abcdef.txt'))
        os.remove(os.path.join(directory, 'ghijkl.txt'))
        os.rmdir(directory)
