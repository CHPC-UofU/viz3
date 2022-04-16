# SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
# SPDX-License-Identifier: GPL-2.0-only
"""
Abstract caches (awkwardly named to allow using "cache" as a variable name).
Beware that this module is not meant to be used ouside viz3, since the
filesystem cache is not collision free.

Probably should be replaced by something on PyPI, if better.
"""
import abc
import base64
import collections
import copy
import datetime
import functools
import json
import logging
import os
import re
import typing


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def convert_json_datetime_strings(json_dict: dict) -> dict:
    """
    Converts ISO-8601 strings within a dictionary to datetime objects.
    """
    for key, value in json_dict.items():
        try:
            json_dict[key] = datetime.datetime.fromisoformat(value)
        except (ValueError, AttributeError, TypeError):
            pass
    return json_dict


def convert_datetime_to_json_string(dt: datetime.datetime) -> str:
    """
    Converts the given datetime object to a ISO-8601 string format.
    """
    return dt.isoformat()


class AbstractCache(abc.ABC):
    """
    An abstract cache object that caches data.
    """

    @abc.abstractmethod
    def retrieve(self, key: str, identifier: str) -> typing.Any:
        """
        Retrieves the data associated with the given key and identifier.

        Throws KeyError if the data does not exist.

        The key can be an arbitrary string, the identifier must be a valid
        Python identifier.
        """
        pass

    @abc.abstractmethod
    def store(self, key: str, identifier: str, data: typing.Any):
        """
        Stores the data given with the a key and identifier.

        The key can be an arbitrary string, the identifier must be a valid
        Python identifier.
        """
        pass

    def retrieve_or_update(self, key: str, identifier: str, fetch_func, *args, **kwargs) \
            -> typing.Any:
        """
        Retries the data associated with the the given key and identifier and
        fetches and stores it if it is not found.

        The key can be an arbitrary string, the identifier must be a valid
        Python identifier.
        """
        try:
            return self.retrieve(key, identifier)
        except KeyError:
            data = fetch_func(*args, **kwargs)
            self.store(key, identifier, copy.deepcopy(data))
            return data

    def fetch_and_update_or_fallback(self, key: str, identifier: str, fetch_func, *args, **kwargs):
        """
        Attempts to fetch the data from fetch_func(), but falls back to trying
        to retrieve it from the cache if that fetch fails. If the fetch
        succeeds, updates the cache with the new data.
        """
        try:
            data = fetch_func(*args, **kwargs)
        except Exception as original_err:
            logger.debug("Failed to fetch for {}/{}; falling back to cache".format(key, identifier))
            try:
                return self.retrieve(key, identifier)
            except KeyError:
                raise original_err
        else:
            self.store(key, identifier, data)
            return data


class PersistentFileCache(AbstractCache):
    """
    Stores a cache on disk with no regards to invalidation.
    """

    def __init__(self, dir: str):
        self._dir = dir
        self._file_cache = InMemoryCache()
        if not os.path.exists(self._dir):
            raise FileNotFoundError("No cache directory: {}".format(self._dir))
        if not os.path.isdir(self._dir):
            raise NotADirectoryError("Cache directory given is not a directory: {}".format(self._dir))

    def _key_filepath(self, key: str, identifier: str) -> str:
        # Note: this mapping is not collision free, one could probably
        #       construct a key that maps the filename to an existing key.
        #       However, this module is within viz3, and the only keys we are
        #       recieving are

        # Produce a human readable filename from the key; we are using
        # knowledge about queries in viz3 to help make it more readable
        replacements = {
            "{": "",
            "}": "",
            "|": "_or_",
            "[^": "_not_any_",
            "[": "_any_",
            "]": "",
            '"': "",
            "'": "",
            ":": "_",
            " ": "_",
            ",": "_",
        }
        new_key = key.replace(r"^[^\v].*$", "")

        def replacement(match):
            ch = match.group(0)
            return replacements.get(ch, "")

        file_prefix = re.sub(r"[^a-zA-Z0-9_-]", replacement, new_key)
        filename = file_prefix + identifier + ".json"
        return os.path.join(self._dir, filename)

    @staticmethod
    def _read_from_cache(filepath):
        logger.debug("Attempting to retrieve file: %s", filepath)
        with open(filepath, "r") as f:
            return json.load(f, object_hook=convert_json_datetime_strings)

    @staticmethod
    def _write_to_cache(filepath, data):
        logger.debug("Attempting to store file: %s", filepath)
        with open(filepath, "w") as f:
            # default: run str if not serializable by default
            return json.dump(data, f, default=convert_datetime_to_json_string)

    def retrieve(self, key: str, identifier: str):
        filepath = self._key_filepath(key, identifier)
        try:
            return self._file_cache.retrieve_or_update(filepath, "", self._read_from_cache, filepath)
        except OSError as err:
            raise KeyError(err)

    def store(self, key: str, identifier: str, data: typing.Any):
        filepath = self._key_filepath(key, identifier)
        if os.path.exists(filepath):
            return

        self._write_to_cache(filepath, data)


class NopCache(AbstractCache):

    def __init__(self):
        pass

    def retrieve(self, query: str, identifier: str):
        raise KeyError()

    def store(self, query: str, identifier: str, data: typing.Any):
        return


class InMemoryCache(AbstractCache):

    def __init__(self):
        self._cache = collections.defaultdict(dict)

    def retrieve(self, query: str, identifier: str):
        return self._cache[identifier][query]

    def store(self, query: str, identifier: str, data: typing.Any):
        self._cache[identifier][query] = data


def class_fallback_cache(func):
    """
    Caches the result of the wrapped function in the class's .cache(). If the
    function fails, the results from the cache are returned.

    >>> import random
    >>> class Klass:
    ...     def __init__(self):
    ...         self._cache = InMemoryCache()
    ...     def cache(self):
    ...         return self._cache
    ...     @class_fallback_cache
    ...     def num(self):
    ...         if random.random() > 0.5:
    ...             raise Exception()
    ...         return 1
    >>> k = Klass()
    >>> assert all(k.num() == 1 for _ in range(1_000_000))
    """
    # See https://gist.github.com/Zearin/2f40b7b9cfc51132851a for a good
    # explanation of decorators
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        identifier = "." + func.__name__
        arg0 = "0"
        if len(args) > 0:
            first_arg = args[0]
            if isinstance(first_arg, set) or isinstance(first_arg, frozenset):
                # Make caching consistent
                first_arg = sorted(first_arg)

            arg0 = str(first_arg)
        return self.cache().fetch_and_update_or_fallback(arg0, identifier, func, self, *args, **kwargs)

    return wrapper
