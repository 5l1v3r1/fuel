import collections
import os

import h5py
import six
import numpy
from six.moves import range

from fuel import config


# See http://python3porting.com/differences.html#buffer
if six.PY3:
    buffer_ = memoryview
else:
    buffer_ = buffer  # noqa


class Subset(object):
    """A description of a subset of examples.

    Parameters
    ----------
    list_or_slice : :class:`list` or :class:`slice`
        List of positive integer indices or slice that describes which
        examples are part of the subset.
    original_num_examples: int
        Number of examples in the dataset this subset belongs to.

    Attributes
    ----------
    is_list : bool
        Whether the Subset is a list-based subset (as opposed to a
        slice-based subset).
    num_examples : int
        Number of examples the Subset spans.
    original_num_examples : int
        Number of examples in the dataset this subset is part of.

    """
    def __init__(self, list_or_slice, original_num_examples):
        self._subset_sanity_check(list_or_slice, original_num_examples)
        if self._is_list(list_or_slice):
            list_or_slice = self._beautify_list(list_or_slice)
        self.list_or_slice = list_or_slice
        self.original_num_examples = original_num_examples

    def __add__(self, other):
        if self.original_num_examples != other.original_num_examples:
            raise ValueError("trying to add two Subset instances with "
                             "different numbers of original examples, they "
                             "can't possibly belong to the same dataset")
        if self.is_list:
            if other.is_list:
                return self.__class__(self.list_or_slice + other.list_or_slice,
                                      self.original_num_examples)
            else:
                return self.__class__(self.list_or_slice +
                                      other[list(range(other.num_examples))],
                                      self.original_num_examples)
        else:
            if other.is_list:
                return self.__class__(self[list(range(self.num_examples))] +
                                      other.list_or_slice,
                                      self.original_num_examples)
            else:
                self_sss = self.slice_to_numerical_args(
                    self.list_or_slice, self.original_num_examples)
                self_start, self_stop, self_step = self_sss
                other_sss = self.slice_to_numerical_args(
                    other.list_or_slice, other.original_num_examples)
                other_start, other_stop, other_step = other_sss
                # Single-step slices can be merged into a slice if they
                # overlap.
                overlap = not (self_stop < other_start or
                               self_start > other_stop)
                if overlap and self_step == other_step == 1:
                    # In case of overlap, the solution is to choose the
                    # smallest start value and largest stop value.
                    return self.__class__(slice(min(self_start, other_start),
                                                max(self_stop, other_stop),
                                                self_step),
                                          self.original_num_examples)
                # Everything else is transformed into lists before merging.
                else:
                    return self.__class__(
                        self[list(range(self.num_examples))] +
                        other[list(range(other.num_examples))],
                        self.original_num_examples)

    def __getitem__(self, key):
        self._request_sanity_check(key, self.num_examples)
        # slice(None, None, None) selects the whole subset, no need to index
        # anything
        if key == slice(None, None, None):
            return self.list_or_slice
        elif self._is_list(key):
            if self.is_list:
                return [self.list_or_slice[index] for index in key]
            else:
                start, stop, step = self.slice_to_numerical_args(
                    self.list_or_slice, self.original_num_examples)
                return [start + (index * step) for index in key]
        else:
            if self.is_list:
                return self.list_or_slice[key]
            else:
                start, stop, step = self.slice_to_numerical_args(
                    self.list_or_slice, self.original_num_examples)
                key_start, key_stop, key_step = self.slice_to_numerical_args(
                    key, self.num_examples)
                return slice(start + step * key_start,
                             start + step * key_stop,
                             step * key_step)

    @classmethod
    def subset_of(cls, subset, list_or_slice):
        """Construct a Subset that is a subset of another Subset.

        Parameters
        ----------
        subset : Subset
            Subset to take the subset of.
        list_or_slice : :class:`list` or :class:`slice`
            List of positive integer indices or slice that describes which
            examples are part of the subset's subset.

        """
        return cls(subset[list_or_slice], subset.original_num_examples)

    @staticmethod
    def safe_unsorted_fancy_index(indexable, request):
        """Safe unsorted fancy indexing.

        Some objects, such as h5py datasets, only support list indexing
        if the list is sorted.

        This static method adds support for unsorted list indexing by
        sorting the requested indices, accessing the corresponding
        elements and re-shuffling the result.

        Parameters
        ----------
        request : list of int
            Unsorted list of example indices.
        indexable : any fancy-indexable object
            Indexable we'd like to do unsorted fancy indexing on.

        """
        if len(request) > 1:
            indices = numpy.argsort(request)
            data = numpy.empty(shape=(len(request),) + indexable.shape[1:],
                               dtype=indexable.dtype)
            data[indices] = indexable[numpy.array(request)[indices], ...]
        else:
            data = indexable[request]
        return data

    @staticmethod
    def slice_to_numerical_args(slice_, num_examples):
        """Translate a slice's attributes into numerical attributes.

        Parameters
        ----------
        slice_ : :class:`slice`
            Slice for which numerical attributes are wanted.
        num_examples : int
            Number of examples in the indexable that is to be sliced
            through. This determines the numerical value for the `stop`
            attribute in case it's `None`.

        """
        start = slice_.start if slice_.start is not None else 0
        stop = slice_.stop if slice_.stop is not None else num_examples
        step = slice_.step if slice_.step is not None else 1
        return start, stop, step

    def index_within_subset(self, indexable, subset_request,
                            safe_hdf5_indexing=True):
        """Index an indexable object within the context of this subset.

        Parameters
        ----------
        indexable : indexable object
            The object to index through.
        subset_request : :class:`list` or :class:`slice`
            List of positive integer indices or slice that constitutes
            the request *within the context of this subset*. This
            request will be translated to a request on the indexable
            object.
        safe_hdf5_indexing : bool, optional
            If the indexable is an HDF5 dataset and the request is a list
            of indices, work around the fancy indexing limitation that
            requires lists of indices to be sorted by indexing in sorted
            order and reshuffling the result in the original order.
            Default to `True`.

        """
        # Translate the request within the context of this subset to a
        # request to the indexable object
        if isinstance(subset_request, int):
            request, = self[[subset_request]]
        else:
            request = self[subset_request]
        # Integer or slice requests can be processed directly.
        if isinstance(request, int) or hasattr(request, 'step'):
            return indexable[request]
        # List requests are handled differently whether the indexable is
        # an HDF5 dataset, a numpy array or another type of indexable.
        else:
            # If the indexable is an HDF5 dataset, it only supports fancy
            # indexing with sorted lists. As a workaround, if
            # `safe_hdf5_indexing` is set to `True`, Subset will do the
            # indexing in sorted order, and reshuffle the result in the
            # original order.
            if isinstance(indexable, h5py.Dataset) and safe_hdf5_indexing:
                return self.safe_unsorted_fancy_index(indexable, request)
            # If
            #   a) the indexable is a numpy array, or
            #   b) it's an HDF5 dataset and the request is a sorted list of
            #      indices,
            # then the request can be processed directly.
            elif isinstance(indexable, (numpy.ndarray, h5py.Dataset)):
                return indexable[request]
            # Anything else (e.g. lists) isn't considered to support fancy
            # indexing, so Subset does it manually.
            else:
                return iterable_fancy_indexing(indexable, request)

    def _is_list(self, list_or_slice):
        """Determines if an object is a list or a slice.

        Parameters
        ----------
        list_or_slice : :class:`list` or :class:`slice`
            It is assumed to be one or the other, **and nothing else**.

        Returns
        -------
        rval : bool
            `True` if the object is a list, `False` if it's a slice.

        """
        return not hasattr(list_or_slice, 'step')

    @property
    def is_list(self):
        """Whether this subset is list-based (as opposed to slice-based)."""
        return self._is_list(self.list_or_slice)

    @property
    def num_examples(self):
        """The number of examples this subset spans."""
        if self.is_list:
            return len(self.list_or_slice)
        else:
            start, stop, step = self.slice_to_numerical_args(
                self.list_or_slice, self.original_num_examples)
            # The problem of finding the number of examples with start > 0
            # reduces to the problem of finding the number of examples with
            # start' = 0 and stop' = stop - start (assuming start < stop, which
            # is enforced in _slice_subset_sanity_check).
            stop = stop - start
            start = 0
            # We count the number of times (stop - 1) is divisible by step
            # (because stop is defined exclusively), plus 1 (because we count
            # the zero index).
            return (stop - 1) // step + 1

    def _subset_sanity_check(self, list_or_slice, num_examples):
        if self._is_list(list_or_slice):
            self._list_subset_sanity_check(list_or_slice, num_examples)
        else:
            self._slice_subset_sanity_check(list_or_slice, num_examples)

    def _list_subset_sanity_check(self, indices, num_examples):
        if len(indices) == 0:
            raise ValueError('Subset instances cannot be defined by an empty '
                             'list (it would be an empty subset)')
        if any(index < 0 for index in indices):
            raise ValueError('Subset instances cannot be defined by a list '
                             'containing negative indices')
        if max(indices) >= num_examples:
            raise ValueError('Subset instances cannot be defined by a list '
                             'containing indices greater than or equal to the '
                             'original number of examples')

    def _slice_subset_sanity_check(self, slice_, num_examples):
        numeric_args = (arg for arg in (slice_.start, slice_.stop, slice_.step)
                        if arg is not None)
        if any(arg < 0 for arg in numeric_args):
            raise ValueError('Subset instances cannot be defined by a slice '
                             'with negative start, stop or step arguments')
        if slice_.stop is not None and slice_.stop > num_examples:
            raise ValueError('Subset instances cannot be defined by a slice '
                             'whose stop value is greater than the original '
                             'number of examples')
        if slice_.start is not None and slice_.start >= num_examples:
            raise ValueError('Subset instances cannot be defined by a slice '
                             'whose start value is greater than or equal to '
                             'the original number of examples')
        if (slice_.start is not None and slice_.stop is not None and
                slice_.start >= slice_.stop):
            raise ValueError('Subset instances cannot be defined by a slice '
                             'whose start value is greater than or equal to '
                             'its stop value (it would be an empty subset)')

    def _request_sanity_check(self, list_or_slice, num_examples):
        if self._is_list(list_or_slice):
            self._list_request_sanity_check(list_or_slice, num_examples)
        else:
            self._slice_request_sanity_check(list_or_slice, num_examples)

    def _list_request_sanity_check(self, indices, num_examples):
        if len(indices) == 0:
            raise ValueError('list-based requests cannot be empty (this would '
                             'produce an empty return value)')
        if any(index < 0 for index in indices):
            raise ValueError('Subset does not support list-based requests '
                             'with negative indices')
        if max(indices) >= num_examples:
            raise ValueError('list-based requests cannot contain indices '
                             'greater than or equal to the number of examples '
                             'the subset spans')

    def _slice_request_sanity_check(self, slice_, num_examples):
        numeric_args = (arg for arg in (slice_.start, slice_.stop, slice_.step)
                        if arg is not None)
        if any(arg < 0 for arg in numeric_args):
            raise ValueError('Subset does not support slice-based requests '
                             'with negative start, stop or step arguments')
        if slice_.stop is not None and slice_.stop > num_examples:
            raise ValueError('slice-based requests cannot have a stop value '
                             'greater than the number of examples the subset '
                             'spans (this would produce a return value with '
                             'smaller length than expected')
        if slice_.start is not None and slice_.start >= num_examples:
            raise ValueError('slice-based requests cannot have a start value '
                             'greater than the number of examples the subset '
                             'spans (this would produce an empty return '
                             'value)')
        if (slice_.start is not None and slice_.stop is not None and
                slice_.start >= slice_.stop):
            raise ValueError('slice-based requests cannot have a start value '
                             'greater than or equal to its stop value (this '
                             'would produce an empty return value)')

    def _beautify_list(self, indices):
        # List elements should be unique and sorted
        indices = list(sorted(set(indices)))
        # If indices are contiguous, convert them into a slice
        contiguous_indices = all(
            indices[i] + 1 == indices[i + 1] for i in range(len(indices) - 1))
        if contiguous_indices:
            return slice(indices[0], indices[-1] + 1, None)
        else:
            return indices


def iterable_fancy_indexing(iterable, request):
    if isinstance(iterable, numpy.ndarray):
        return iterable[request]
    else:
        return [iterable[r] for r in request]


def find_in_data_path(filename):
    """Searches for a file within Fuel's data path.

    This function loops over all paths defined in Fuel's data path and
    returns the first path in which the file is found.

    Parameters
    ----------
    filename : str
        Name of the file to find.

    Returns
    -------
    file_path : str
        Path to the first file matching `filename` found in Fuel's
        data path.

    Raises
    ------
    IOError
        If the file doesn't appear in Fuel's data path.

    """
    for path in config.data_path:
        path = os.path.expanduser(os.path.expandvars(path))
        file_path = os.path.join(path, filename)
        if os.path.isfile(file_path):
            return file_path
    raise IOError("{} not found in Fuel's data path".format(filename))


def lazy_property_factory(lazy_property):
    """Create properties that perform lazy loading of attributes."""
    def lazy_property_getter(self):
        if not hasattr(self, '_' + lazy_property):
            self.load()
        if not hasattr(self, '_' + lazy_property):
            raise ValueError("{} wasn't loaded".format(lazy_property))
        return getattr(self, '_' + lazy_property)

    def lazy_property_setter(self, value):
        setattr(self, '_' + lazy_property, value)

    return lazy_property_getter, lazy_property_setter


def do_not_pickle_attributes(*lazy_properties):
    r"""Decorator to assign non-pickable properties.

    Used to assign properties which will not be pickled on some class.
    This decorator creates a series of properties whose values won't be
    serialized; instead, their values will be reloaded (e.g. from disk) by
    the :meth:`load` function after deserializing the object.

    The decorator can be used to avoid the serialization of bulky
    attributes. Another possible use is for attributes which cannot be
    pickled at all. In this case the user should construct the attribute
    himself in :meth:`load`.

    Parameters
    ----------
    \*lazy_properties : strings
        The names of the attributes that are lazy.

    Notes
    -----
    The pickling behavior of the dataset is only overridden if the
    dataset does not have a ``__getstate__`` method implemented.

    Examples
    --------
    In order to make sure that attributes are not serialized with the
    dataset, and are lazily reloaded after deserialization by the
    :meth:`load` in the wrapped class. Use the decorator with the names of
    the attributes as an argument.

    >>> from fuel.datasets import Dataset
    >>> @do_not_pickle_attributes('features', 'targets')
    ... class TestDataset(Dataset):
    ...     def load(self):
    ...         self.features = range(10 ** 6)
    ...         self.targets = range(10 ** 6)[::-1]

    """
    def wrap_class(cls):
        if not hasattr(cls, 'load'):
            raise ValueError("no load method implemented")

        # Attach the lazy loading properties to the class
        for lazy_property in lazy_properties:
            setattr(cls, lazy_property,
                    property(*lazy_property_factory(lazy_property)))

        # Delete the values of lazy properties when serializing
        if not hasattr(cls, '__getstate__'):
            def __getstate__(self):
                serializable_state = self.__dict__.copy()
                for lazy_property in lazy_properties:
                    attr = serializable_state.get('_' + lazy_property)
                    # Iterators would lose their state
                    if isinstance(attr, collections.Iterator):
                        raise ValueError("Iterators can't be lazy loaded")
                    serializable_state.pop('_' + lazy_property, None)
                return serializable_state
            setattr(cls, '__getstate__', __getstate__)

        return cls
    return wrap_class
