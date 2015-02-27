import numpy
from numpy.testing import assert_raises
from six.moves import cPickle

from fuel.datasets import CIFAR10


def test_cifar10():
    cifar10_train = CIFAR10('train', start=20000)
    assert len(cifar10_train.features) == 30000
    assert len(cifar10_train.targets) == 30000
    assert cifar10_train.num_examples == 30000
    cifar10_test = CIFAR10('test', sources=('targets',))
    assert len(cifar10_test.targets) == 10000
    assert cifar10_test.num_examples == 10000

    first_feature, first_target = cifar10_train.get_data(request=[0])
    assert first_feature.shape == (1, 3072)
    assert first_feature.dtype.kind == 'f'
    assert first_target.shape == (1, 1)
    assert first_target.dtype is numpy.dtype('uint8')

    first_target, = cifar10_test.get_data(request=[0, 1])
    assert first_target.shape == (2, 1)

    assert_raises(ValueError, CIFAR10, 'valid')

    cifar10_test = cPickle.loads(cPickle.dumps(cifar10_test))
    assert len(cifar10_test.targets) == 10000

    cifar_10_test_unflattened = CIFAR10('test', flatten=False)
    cifar_10_test_unflattened.features.shape == (10000, 3, 32, 32)
