# SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
# SPDX-License-Identifier: GPL-2.0-only
"""
Defines a query language used by the XML visualization definition.
"""
from __future__ import annotations
import typing

import more_itertools

from . import core


class LanguageSyntaxError(Exception):
    pass


def _parse_relative_path(text: str, parent_path: typing.Optional[core.Path] = None) -> core.Path:
    """
    Parses text into a core.Path(), with a parent path allowing the given text
    to be relative to the given parent path.
    """
    if not text.startswith("."):  # absolute path
        return core.Path(text)

    if parent_path is None:
        raise LanguageSyntaxError("Cannot use relative path '{}' without parent path".format(text))

    rel_path = core.Path(text)
    return parent_path.join_after_common_descendant(rel_path)


class BindLanguage:

    def __init__(self, path: core.Path, keep_when_filtered_out: bool = False):
        self._path = path
        self._keep_when_filtered_out = keep_when_filtered_out

    @classmethod
    def from_string(cls, text: str, parent_path: core.Path) -> BindLanguage:
        keep_when_filtered_out = False
        if text.endswith("!"):
            text = text.rstrip("!")
            keep_when_filtered_out = True

        return cls(_parse_relative_path(text, parent_path), keep_when_filtered_out)

    def path(self) -> core.Path:
        return self._path

    def keep_when_filtered_out(self) -> bool:
        return self._keep_when_filtered_out


class ValueLanguage:

    def __init__(self, path: core.Path, pipeline: typing.List[str],
                 prefix: str, suffix: typing.Optional[str] = "", default: typing.Optional[str] = None):
        """
        Defines a simple language that specifies a path and optionally
        a series of function names to call on the corresponding value from the
        path.
        """
        self._prefix = prefix
        self._suffix = suffix
        self._path = path
        self._pipeline = pipeline
        self._default = default

    @classmethod
    def _raise_invalid_func_form_error(cls, text: str, reason: str):
        raise LanguageSyntaxError("Value language '{}' does not match the "
                                  "form ':func_name(...)': {}".format(text, reason))

    @classmethod
    def _path_from_str(cls, path_str: str, parent_path: core.Path):
        path_str = path_str.strip()
        is_absolute = not path_str.startswith(".")
        path = core.Path(path_str)
        if not is_absolute:
            path = parent_path + path

        return path

    @classmethod
    def _skip_while(cls, text_iter, continue_func) -> str:
        content = ""
        while True:
            try:
                ch = text_iter.peek()
            except StopIteration:
                return content

            if not continue_func(ch):
                break

            next(text_iter)
            content += ch

        return content

    @classmethod
    def _skip_whitespace(cls, text_iter) -> str:
        return cls._skip_while(text_iter, str.isspace)

    @classmethod
    def _skip_identifier(cls, text_iter) -> str:
        after_first = False

        def is_identifier(s):
            nonlocal after_first
            if not after_first:
                return s.isdigit() or s.isidentifier()
            after_first = True
            return s.isidentifier()

        return cls._skip_while(text_iter, is_identifier)

    @classmethod
    def _skip_identifier_or_num(cls, text_iter) -> str:
        return cls._skip_while(text_iter, lambda s: s.isdigit() or s.isidentifier() or s == '.')

    @classmethod
    def _skip_quote(cls, text_iter) -> str:
        first_ch = text_iter.peek(default="")
        if first_ch == "":
            return ""

        assert first_ch == "'"
        next(text_iter)

        content = ""
        while True:
            try:
                ch = next(text_iter)
            except StopIteration:
                raise ValueError("Unterminated single quote after '{}'".format(content))

            if ch == "'":
                break

            content += ch

        return content

    @classmethod
    def _parse_path(cls, text_iter, stop_chars, parent_path):
        is_part_of_path = lambda s: (core.is_valid_path_part(s) or s == ".") and s not in stop_chars
        path_text = cls._skip_while(text_iter, is_part_of_path)
        path = _parse_relative_path("." + path_text, parent_path)
        return path_text, path

    @classmethod
    def _try_parse_language(cls, text_iter, parent_path) \
            -> typing.Tuple[typing.List[core.Path], typing.List[str], str]:
        content = ""
        def get_stop_ch():
            nonlocal content
            try:
                _stop_ch = next(text_iter)
                content += _stop_ch
            except StopIteration:
                _stop_ch = ""
            return _stop_ch

        assert get_stop_ch() == "."

        pipeline = []
        stop_chars = ("|", "?", "")
        path_content, path = cls._parse_path(text_iter, stop_chars, parent_path)
        content += path_content

        stop_ch = get_stop_ch()
        while stop_ch == "|":
            identifier = cls._skip_identifier(text_iter)
            if identifier == "":
                raise LanguageSyntaxError("Expected identifier for function, "
                                          "but got none: {}".format(content))

            content += identifier
            pipeline.append(identifier)
            stop_ch = get_stop_ch()

        return path, pipeline, stop_ch

    @classmethod
    def from_string(cls, text: str, parent_path: core.Path) -> typing.List[ValueLanguage]:
        """
        A value language is of the form:
        part = /[a-zA-Z_-0-9:]/
        path = '.' :part ('.' :part)*
        func_name = /[a-zA-Z_][a-zA-Z0-9_]*/
        pipeline = '|' :func_name ('|' :func_name)*
        lang = :path :pipeline?

        If may be contained within another string. Notably, each path must
        be relative (start with a '.'). To escape a dot, use a backslash.

        e.g. '.prometheus:cpu_usage|to_color'
             '.pcp:network-in-bytes|rate'
             'Usage: .usage_bytes bytes'
        """
        if text == "":
            raise LanguageSyntaxError("Empty string for a binding.")

        path = None
        langs = []
        text_iter = more_itertools.peekable(text)
        prefix = ""
        prev_ch = ""
        while True:
            try:
                ch = text_iter.peek()
            except StopIteration:
                break

            if ch == "." and prev_ch != "\\" and not prev_ch.isdigit():
                path, pipeline, stop_ch = cls._try_parse_language(text_iter, parent_path)

                default = None
                has_default = stop_ch == "?"
                if has_default:
                    if text_iter.peek(default="") == "'":
                        default = cls._skip_quote(text_iter)
                    else:
                        default = cls._skip_identifier_or_num(text_iter)

                    stop_ch = default[-1] if default != "" else stop_ch

                lang = ValueLanguage(
                    path,
                    pipeline,
                    prefix=prefix,
                    default=default,
                )
                langs.append(lang)

                prefix = "" if has_default else stop_ch
                prev_ch = stop_ch
            else:
                if prev_ch == "\\" and ch == "n":
                    prev_ch = "\n"
                    prefix = prefix[:-1]  # remove newline
                    prefix += "\n"
                else:
                    prev_ch = ch
                    prefix += ch

                next(text_iter)

        if not langs:
            raise LanguageSyntaxError("No path exists within text: {}".format(text))

        langs[-1].add_suffix(prefix)
        return langs

    @staticmethod
    def looks_valid(text: str) -> bool:
        """
        Returns whether the text is a value language.
        """
        return ":" in text or "(" in text or ")" in text

    def prefix(self) -> str:
        """
        Returns the string before the pipeline.
        """
        return self._prefix

    def add_suffix(self, suffix) -> str:
        self._suffix += suffix
        return self._suffix

    def suffix(self) -> str:
        """
        Returns the string after the pipeline.
        """
        return self._suffix

    def path(self) -> core.Path:
        """
        Returns the data path (e.g. viz3.core.Path(.data) of func(.data)) found
        in the language.
        """
        return self._path

    def pipeline(self) -> typing.List[str]:
        """
        Returns the pipeline (e.g. ["tr"] of .data|func) found in the language.
        """
        return self._pipeline

    def default(self) -> typing.Optional[str]:
        """
        Returns the default value of the pipeline.
        """
        if not self._default:
            return self._default
        return self.formatted_value(self._default)

    def formatted_value(self, value: typing.Any) -> str:
        return self.prefix() + str(value) + self.suffix()

    def __str__(self):
        if not self._pipeline:
            return self.formatted_value(self._path)

        s = str(self._path)
        if len(self._pipeline) > 1:
            s += "|" + "|".join(self._pipeline)
        if self.default() is not None:
            s += "?"

        return self.formatted_value(s)


class FilterLanguage:

    def __init__(self, path: core.Path, selector: typing.Set[typing.Optional[str]], is_negative: bool, is_regex: bool):
        """
        Defines a simple query language.
        """
        self._path = path
        self._selector = selector
        self._is_negative = is_negative
        self._is_regex = is_regex

    @classmethod
    def _parse_selector(self, text: str) -> typing.Set[typing.Optional[str]]:
        if text.startswith("{"):
            if not text.endswith("}"):
                raise LanguageSyntaxError("Started to apply set match "
                                          "'{value,...}', but no '}' at the end!")

            # FIXME: If ',' appears in a part, things will be parsed incorrectly!
            parts = text.lstrip("{").rstrip("}").split(",")
        else:
            parts = [text]

        selector = set()
        for part in parts:
            if part.lower() == "null":
                selector.add(None)
            elif part == "":  # erroneous; ignore
                continue
            else:
                selector.add(part.strip("'").strip())

        return selector

    @classmethod
    def from_string(cls, text: str, parent_path: core.Path) -> FilterLanguage:
        """
        A value language is of the form:
        :path :equality :selector

        where:
            :path = :identifier
                  | '.' :path
            :equality = '='
                      | '!='
                      | '~'     # Regex
                      | '!~'    # Regex
            :value = "'" :string "'"
            :list = :value
                  | ',' :list
            :selector = :value
                      | '{' :list '}'

        Examples:
            "bar='string'" or just "='string'"
            ".path.to={1,2}"
            "~{'^foo', 'bar$'}"
        """
        text = text.strip()
        if not cls.looks_valid(text):
            raise LanguageSyntaxError("Could not find '=' nor '~' in filter "
                                      "language: '{}'".format(text))

        split_char = "="
        if "~" in text and split_char not in text:
            split_char = "~"

        is_negative = False
        path_specifier, selector_text = text.split(split_char, maxsplit=1)
        path_specifier = path_specifier.strip()
        selector = cls._parse_selector(selector_text.strip())

        if path_specifier.endswith("!"):
            path_specifier = path_specifier.rstrip("!")
            path_specifier = path_specifier.rstrip()
            is_negative = True

        if path_specifier == "":
            path = parent_path
        else:
            path = _parse_relative_path(path_specifier, parent_path)

        return cls(
            path,
            selector,
            is_negative=is_negative,
            is_regex=split_char == "~",
        )

    @staticmethod
    def looks_valid(text: str) -> bool:
        """
        Returns whether the text is a filter language.
        """
        return "=" in text or "~" in text or ("{" in text and "}" in text)

    def path(self) -> core.Path:
        """
        Returns the data path (e.g. viz3.core.Path(.data) of .data=foo) found
        in the language.
        """
        return self._path

    def selector(self) -> typing.Set[typing.Optional[str]]:
        """
        Returns the selector (e.g. {"foo"} of .data=foo, or {None} of .data=null
        or {1,2} of .data={1,2}) found in the language.
        """
        return self._selector

    def is_negative(self) -> bool:
        """
        Whether the selector should NOT be matched against.
        """
        return self._is_negative

    def is_regex(self) -> bool:
        """
        Whether the selector should NOT be matched against.
        """
        return self._is_regex
