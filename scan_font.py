#!/usr/bin/python3
# coding=UTF-8

import collections
from collections import defaultdict
import glob
import itertools
import os
import os.path
import shutil
import subprocess
import sys

from typing import Any, DefaultDict, Dict, Iterable, List, NamedTuple, Union

ENCODING = sys.getdefaultencoding()
FIELD_SEPARATOR = '###___###'
POSTSCRIPT_STYLE_NAME = '__PostScript__'


class FontChoice(NamedTuple):
    filename: str
    index: int
    family: str
    style: str


class FontInfo(NamedTuple):
    # From lang to list of families
    families: Dict[str, List[str]]

    # From lang to list of styles
    styles: Dict[str, List[str]]

    # PostScript names, without language mapping
    postscript_names: List[str]


class FontLocation(NamedTuple):
    filename: str
    index: int


class ValueWithLang(NamedTuple):
    location: FontLocation
    lang: str
    value: str


class ValueWithoutLang(NamedTuple):
    location: FontLocation
    value: str


class IllegalStyleError(ValueError):
    def __init__(self, message) -> None:
        super().__init__(message)


def parse_value_with_lang(line: str):
    fields = line.split(FIELD_SEPARATOR)
    filename = fields[0]
    index = int(fields[1])
    value = fields[2]
    lang = fields[3]
    return ValueWithLang(FontLocation(filename, index), lang, value)


def parse_lang_map(root_path: str, fc_format: str) \
    -> DefaultDict[FontLocation, DefaultDict[str, List[str]]]:
    fc_result = subprocess.run([
        'fc-scan', '-f', fc_format, root_path
    ], capture_output=True)
    fc_result.check_returncode()
    location_lang_value: DefaultDict[FontLocation, DefaultDict[str, List[str]]]
    location_lang_value = defaultdict(lambda: defaultdict(list))
    for line in fc_result.stdout.decode(ENCODING).splitlines():
        entry = parse_value_with_lang(line)
        location_lang_value[entry.location][entry.lang].append(entry.value)
    return location_lang_value


def parse_value_without_lang(line: str):
    fields = line.split(FIELD_SEPARATOR)
    filename = fields[0]
    index = int(fields[1])
    value = fields[2]
    return ValueWithoutLang(FontLocation(filename, index), value)


def parse_name_array(root_path: str, fc_format: str) \
    -> DefaultDict[FontLocation, List[str]]:
    fc_result = subprocess.run([
        'fc-scan', '-f', fc_format, root_path
    ], capture_output=True)
    fc_result.check_returncode()
    location_to_names: DefaultDict[FontLocation, List[str]]
    location_to_names = defaultdict(list)
    for line in fc_result.stdout.decode(ENCODING).splitlines():
        entry = parse_value_without_lang(line)
        location_to_names[entry.location].append(entry.value)
    return location_to_names


def verify_fonts(location_to_font: Dict[FontLocation, FontInfo]):
    for _, font in location_to_font.items():
        family_lens = [len(families) for families in font.families.values()]
        style_lens = [len(styles) for styles in font.styles.values()]
        if len(set(family_lens + style_lens)) != 1 and not font.postscript_names:
            raise ValueError(
                "Element numbers don't match in a FontInfo: {}".format(font))


def parse_fonts(root_path: str):
    location_lang_family = parse_lang_map(
        root_path,
        r'%{[]family,familylang{%{file}###___###%{index}###___###%{family}###___###%{familylang}\n}}'
    )
    location_lang_style = parse_lang_map(
        root_path,
        r'%{[]style,stylelang{%{file}###___###%{index}###___###%{style}###___###%{stylelang}\n}}'
    )
    location_to_postscript_names = parse_name_array(
        root_path,
        r'%{[]postscriptname{%{file}###___###%{index}###___###%{postscriptname}\n}}')
    assert location_lang_family.keys() == location_lang_style.keys() \
        and location_lang_family.keys() == location_to_postscript_names.keys()
    location_font: Dict[FontLocation, FontInfo]
    location_font = {
        key: FontInfo(location_lang_family[key], location_lang_style[key], location_to_postscript_names[key])
        for key in location_lang_family
    }
    verify_fonts(location_font)
    return location_font


def find_style_lang(styles: Dict[str, Any], preferred_langs: List[str]) -> Union[str, None]:
    if len(styles) == 1:
        return next(iter(styles.keys()))
    for lang in preferred_langs:
        if lang in styles:
            return lang
    return None


def expand_families_with_styles(
    location: FontLocation,
    font: FontInfo,
    preferred_style_langs: List[str]) -> List[FontChoice]:
    result = []
    style_lang = find_style_lang(font.styles, preferred_style_langs)
    if not style_lang:
        raise ValueError(
            'Cannot select a font style language with preferred_style_langs'
            ' = {} and styles = {}'.format(
                preferred_style_langs, font.styles))
    styles = font.styles[style_lang]
    for _, families in font.families.items():
        if len(families) == len(styles):
            result += [
                FontChoice(location.filename, location.index, family, style)
                for family, style in zip(families, styles)
            ]
        else:
            raise IllegalStyleError("The number of families doesn't match the number of styles. families = {}, styles = {}".format(families, styles))
    return result


def expand_fonts(fonts: Dict[FontLocation, FontInfo], preferred_style_langs: List[str]):
    result: List[FontChoice] = []
    for location, font in fonts.items():
        try:
            result += expand_families_with_styles(
                location, font, preferred_style_langs)
        except IllegalStyleError as e:
            print(str(e), 'Trying PostScript names')
            assert font.postscript_names
            result += [
                FontChoice(
                    location.filename,
                    location.index,
                    name,
                    POSTSCRIPT_STYLE_NAME)
                for name in font.postscript_names
            ]
    return result


def collect_files(paths: Iterable[str], destination_dir: str):
    os.mkdir(destination_dir)
    for path in paths:
        destination_path = os.path.join(
            destination_dir, os.path.basename(path))
        with open(path, 'rb') as src_file:
            with open(destination_path, 'xb') as dst_file:
                shutil.copyfileobj(src_file, dst_file)
        shutil.copystat(path, destination_path)


# Never include these font families in the collection
IGNORED_FONTS = set(['微软雅黑'])

# Only allow regular or bold styles to match. Font weight is not supported.
PREFERRED_STYLES = set(['Regular', 'Bold', POSTSCRIPT_STYLE_NAME])

# Allow all styles when processing these font families
# Some fonts don't have a "Regular" style option
FONT_FAMILIES_IGNORING_STYLE = set([
    'HYQiHei-35S',
    '汉仪旗黑-35S',
    'HYQiHei-65S',
    '汉仪旗黑-65S',
    'HYQiHei-80S',
])

PREFERRED_STYLE_LANG = 'en'

if __name__ == '__main__':
    root_path = sys.argv[1]
    fonts = expand_fonts(parse_fonts(root_path), [PREFERRED_STYLE_LANG])
    family_to_font: DefaultDict[str, List[FontChoice]]
    family_to_font = collections.defaultdict(list)
    for font in fonts:
        if font.style in PREFERRED_STYLES or font.family in FONT_FAMILIES_IGNORING_STYLE:
            family_to_font[font.family].append(font)
    missing_fonts = []
    collected_paths = set()
    for required_family in sys.stdin.read().splitlines():
        if required_family in IGNORED_FONTS:
            continue
        paths = set(
            [font.filename for font in family_to_font[required_family]])
        if len(paths) == 0:
            print('Missing: {}'.format(required_family))
            missing_fonts.append(required_family)
        elif len(paths) != 1:
            print('Duplicated: {} provided by {}'.format(required_family, paths))
            exit(1)
        else:
            path = next(iter(paths))
            print('Choosing {} for {} because it provides {}'.format(
                path, required_family, ['{}, {}'.format(font.family, font.style) for font in family_to_font[required_family]]))
            collected_paths.add(path)

    if missing_fonts:
        print('Font collection is not generated because there are missing fonts')
        exit(1)

    print('Selected font files:')
    for path in sorted(collected_paths):
        print(path)

    collect_files(collected_paths, 'collected')

    exit(0)
