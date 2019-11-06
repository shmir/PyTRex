#!/usr/bin/python3

import sys

# from text_opts import format_text

from texttable import Texttable


class TRexTextTable(Texttable):

    def __init__(self):
        Texttable.__init__(self)
        # set class attributes so that it'll be more like TRex standard output
        self.set_chars(['-', '|', '-', '-'])
        self.set_deco(Texttable.HEADER | Texttable.VLINES)


class TRexTextInfo(Texttable):

    def __init__(self):
        Texttable.__init__(self)
        # set class attributes so that it'll be more like TRex standard output
        self.set_chars(['-', ':', '-', '-'])
        self.set_deco(Texttable.VLINES)


def generate_trex_stats_table():
    pass


def print_table_with_header(texttable_obj, header="", untouched_header="",
                            buffer=sys.stdout):
    header = header.replace("_", " ").title() + untouched_header
    # print(format_text(header, 'cyan', 'underline') + "\n", file=buffer)
    print(header)

    # print((texttable_obj.draw() + "\n"), file=buffer)
    print((texttable_obj.draw()))


if __name__ == "__main__":
    pass
