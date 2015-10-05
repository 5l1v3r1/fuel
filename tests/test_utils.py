import operator
import os
import shutil
import tempfile

from numpy.testing import assert_raises, assert_equal
from six.moves import range, cPickle

from fuel import config
from fuel.iterator import DataIterator
from fuel.utils import do_not_pickle_attributes, find_in_data_path, Subset


class TestSubset(object):
    def test_raises_value_error_on_negative_indices(self):
        # Subset should not support lists with negative elements.
        assert_raises(ValueError, Subset, [0, -1], 2)

    def test_raises_value_error_on_too_large_indices(self):
        # Subset should not support lists with indices greater or equal to
        # the original number of examples.
        assert_raises(ValueError, Subset, [0, 10], 2)

    def test_raises_value_error_on_empty_list(self):
        # Subset should not support empty lists
        assert_raises(ValueError, Subset, [], 15)

    def test_raises_value_error_on_negative_slices(self):
        # Subset should not support slices with negative start, stop or step.
        assert_raises(ValueError, Subset, slice(-1, None, None), 2)
        assert_raises(ValueError, Subset, slice(None, -1, None), 2)
        assert_raises(ValueError, Subset, slice(None, None, -1), 2)

    def test_raises_value_error_on_slice_out_of_bound(self):
        # Subset should not support slices that go out of bound with respect to
        # the original number of examples.
        assert_raises(ValueError, Subset, slice(None, 10, None), 2)

    def test_raises_value_error_on_empty_slice(self):
        # Subset should not support slices that lead to an empty subset
        assert_raises(ValueError, Subset, slice(11, 10, None), 15)

    def test_list_num_examples(self):
        assert_equal(Subset([0, 3, 8, 13], 15).num_examples, 4)

    def test_slice_num_examples(self):
        assert_equal(Subset(slice(3, 18, 1), 50).num_examples, 15)
        assert_equal(Subset(slice(2, 37, 7), 50).num_examples, 5)
        assert_equal(Subset(slice(2, 37, 8), 50).num_examples, 5)

    def test_is_slice_property(self):
        assert Subset(slice(None, None, None), 2).is_slice
        assert not Subset([0, 1, 3], 4).is_slice

    def test_is_list_property(self):
        assert not Subset(slice(None, None, None), 2).is_list
        assert Subset([0, 1, 3], 4).is_list

    def test_lists_are_unique_and_sorted(self):
        assert_equal(Subset([0, 3, 3, 5], 10).list_or_slice, [0, 3, 5])
        assert_equal(Subset([0, 3, 1, 5], 10).list_or_slice, [0, 1, 3, 5])

    def test_contiguous_lists_are_transformed_into_slices(self):
        assert_equal(Subset([1, 2, 3], 10).list_or_slice, slice(1, 4, None))

    def test_list_subset_list_request(self):
        assert_equal(Subset([0, 2, 5, 7, 10, 15], 16)[[3, 2, 4]], [7, 5, 10])

    def test_list_subset_slice_request(self):
        assert_equal(Subset([0, 2, 5, 7, 10, 15], 16)[slice(1, 4, 2)], [2, 7])

    def test_slice_subset_list_request(self):
        assert_equal(Subset(slice(1, 14, 3), 16)[[3, 2, 4]], [10, 7, 13])

    def test_slice_subset_slice_request(self):
        assert_equal(Subset(slice(1, 14, 3), 16)[slice(1, 4, 2)],
                     slice(4, 13, 6))

    def test_add_raises_value_error_when_incompatible(self):
        # Adding two Subset instances should only work when they have the same
        # number of original examples.
        assert_raises(
            ValueError, operator.add, Subset([1, 3], 10), Subset([2, 4], 11))

    def test_add_list_list(self):
        assert_equal((Subset([0, 3, 2, 8], 10) +
                      Subset([0, 4, 5], 10)).list_or_slice,
                     [0, 2, 3, 4, 5, 8])

    def test_add_list_slice(self):
        assert_equal((Subset([0, 3, 2, 8], 10) +
                      Subset(slice(1, 9, 3), 10)).list_or_slice,
                      [0, 1, 2, 3, 4, 7, 8])

    def test_add_slice_list(self):
        assert_equal((Subset(slice(1, 9, 3), 10) +
                      Subset([0, 3, 2, 8], 10)).list_or_slice,
                      [0, 1, 2, 3, 4, 7, 8])

    def test_add_contiguous_single_step_slice_slice(self):
        assert_equal((Subset(slice(0, 4, 1), 10) +
                      Subset(slice(4, 7, 1), 10)).list_or_slice,
                      slice(0, 7, 1))
        assert_equal((Subset(slice(4, 7, 1), 10) +
                      Subset(slice(0, 4, 1), 10)).list_or_slice,
                      slice(0, 7, 1))

    def test_add_overlapping_single_step_slice_slice(self):
        assert_equal((Subset(slice(0, 6, 1), 10) +
                      Subset(slice(4, 7, 1), 10)).list_or_slice,
                      slice(0, 7, 1))
        assert_equal((Subset(slice(4, 7, 1), 10) +
                      Subset(slice(0, 6, 1), 10)).list_or_slice,
                      slice(0, 7, 1))

    def test_adding_slice_slice_falls_back_to_list(self):
        # If Subset can't find a way to add two slices together, it must
        # return a list-based Subset.
        assert_equal((Subset(slice(0, 8, 3), 20) +
                      Subset(slice(12, 19, 2), 20)).list_or_slice,
                      [0, 3, 6, 12, 14, 16, 18])


@do_not_pickle_attributes("non_picklable", "bulky_attr")
class DummyClass(object):
    def __init__(self):
        self.load()

    def load(self):
        self.bulky_attr = list(range(100))
        self.non_picklable = lambda x: x


class FaultyClass(object):
    pass


@do_not_pickle_attributes("iterator")
class UnpicklableClass(object):
    def __init__(self):
        self.load()

    def load(self):
        self.iterator = DataIterator(None)


@do_not_pickle_attributes("attribute")
class NonLoadingClass(object):
    def load(self):
        pass


class TestFindInDataPath(object):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        os.mkdir(os.path.join(self.tempdir, 'dir1'))
        os.mkdir(os.path.join(self.tempdir, 'dir2'))
        self.original_data_path = config.data_path
        config.data_path = os.path.pathsep.join(
            [os.path.join(self.tempdir, 'dir1'),
             os.path.join(self.tempdir, 'dir2')])
        with open(os.path.join(self.tempdir, 'dir1', 'file_1.txt'), 'w'):
            pass
        with open(os.path.join(self.tempdir, 'dir2', 'file_1.txt'), 'w'):
            pass
        with open(os.path.join(self.tempdir, 'dir2', 'file_2.txt'), 'w'):
            pass

    def tearDown(self):
        config.data_path = self.original_data_path
        shutil.rmtree(self.tempdir)

    def test_returns_file_path(self):
        assert_equal(find_in_data_path('file_2.txt'),
                     os.path.join(self.tempdir, 'dir2', 'file_2.txt'))

    def test_returns_first_file_found(self):
        assert_equal(find_in_data_path('file_1.txt'),
                     os.path.join(self.tempdir, 'dir1', 'file_1.txt'))

    def test_raises_error_on_file_not_found(self):
        assert_raises(IOError, find_in_data_path, 'dummy.txt')


class TestDoNotPickleAttributes(object):
    def test_load(self):
        instance = cPickle.loads(cPickle.dumps(DummyClass()))
        assert_equal(instance.bulky_attr, list(range(100)))
        assert instance.non_picklable is not None

    def test_value_error_no_load_method(self):
        assert_raises(ValueError, do_not_pickle_attributes("x"), FaultyClass)

    def test_value_error_iterator(self):
        assert_raises(ValueError, cPickle.dumps, UnpicklableClass())

    def test_value_error_attribute_non_loaded(self):
        assert_raises(ValueError, getattr, NonLoadingClass(), 'attribute')
