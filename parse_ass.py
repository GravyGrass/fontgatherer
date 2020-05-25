#!/usr/bin/python3

import ass
import os
import re
import sys

encoding = sys.argv[1]
ass_root_dir = sys.argv[2]
fonts = set()
fonts_requiring_bold = set()
fonts_requiring_weight = set()

FONT_NAME_REGEX = re.compile(r'\\fn([^\\}]+)')
BOLD_REGEX = re.compile(r'\\b([0-9]+)')
ITALICS_REGEX = re.compile(r'\\i[0-9]+')

def trim_font(font):
    if font.startswith('@'):
        return font[1:]
    else:
        return font

for dirpath, dirnames, filenames in os.walk(ass_root_dir):
    for filename in filenames:
        if filename.endswith('.ass'):
            with open(os.path.join(dirpath, filename), 'r', encoding=encoding) as f:
                doc = ass.parse(f)
                for style in doc.styles:
                    fonts.add(trim_font(style.fontname))
                for event in doc.events:
                    fonts_in_event = set()
                    if ITALICS_REGEX.search(event.text):
                        raise NotImplementedError('Italic font is not supported: {}'.format(event.text))
                    for font_match in FONT_NAME_REGEX.finditer(event.text):
                        fonts_in_event.add(trim_font(font_match.group(1)))
                    for bold_match in BOLD_REGEX.finditer(event.text):
                        font_weight = int(bold_match.group(1))
                        if font_weight > 0:
                            if font_weight == 1:
                                fonts_requiring_bold.update(fonts_in_event)
                            else:
                                fonts_requiring_weight.update(fonts_in_event)
                    fonts.update(fonts_in_event)

if fonts_requiring_bold:
    sys.stderr.write('Fonts may require bold:\n{}\n'.format('\n'.join(fonts_requiring_bold)))

if fonts_requiring_weight:
    sys.stderr.write('Fonts may require custom weight:\n{}\n'.format('\n'.join(fonts_requiring_weight)))

for font in sorted(fonts):
    print(font)
