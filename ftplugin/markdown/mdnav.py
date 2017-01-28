from __future__ import print_function

import os.path
import re
import sys
import subprocess
import webbrowser

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse


class FakeLogger(object):
    def __init__(self, active=False):
        self.active = active

    def info(self, fmt, *args):
        if not self.active:
            return

        print(fmt % args)


_logger = FakeLogger()


def plugin_entry_point():
    import vim

    if int(vim.eval("exists('g:mdnav#Extensions')")):
        extensions = vim.eval('g:mdnav#Extensions')
        extensions = [ext.strip() for ext in extensions.split(',')]

    else:
        extensions = []

    if int(vim.eval("exists('g:mdnav#DebugMode')")):
        _logger.active = vim.eval('g:mdnav#DebugMode') == 'true'

    row, col = vim.current.window.cursor
    cursor = (row - 1, col)
    lines = vim.current.buffer

    target = parse_link(cursor, lines)
    action = open_link(
        target,
        current_file=vim.eval("expand('%:p:h')"),
        open_in_vim_extensions=extensions,
    )
    action()


def open_link(target, current_file, open_in_vim_extensions=set()):
    """
    :returns: a callable that encapsulates the action to perform
    """
    if target is not None:
        target = target.strip()

    if not target:
        _logger.info('no target')
        return NoOp(target)

    if not has_extension(target, open_in_vim_extensions):
        _logger.info('has no extension for opening in vim')
        return OSOpen(target)

    if has_scheme(target):
        _logger.info('has scheme -> open in browser')
        return BrowserOpen(target)

    if target.startswith('|filename|'):
        target = target[len('|filename|'):]

    if os.path.isabs(target):
        _logger.info('is an absolute path')
        return VimOpen(target)

    _logger.info('anchor path relative to %s', current_file)
    rel_target = os.path.join(os.path.dirname(current_file), target)
    return VimOpen(rel_target)


def has_extension(path, extensions):
    if not extensions:
        return True

    _, ext = os.path.splitext(path)
    return ext in extensions


def has_scheme(target):
    return bool(urlparse(target).scheme)


class Action(object):
    def __init__(self, target):
        self.target = target

    def __eq__(self, other):
        return type(self) == type(other) and self.target == other.target

    def __repr__(self):
        return '{}({!r})'.format(type(self).__name__, self.target)


class NoOp(Action):
    def __call__(self):
        print('<mdnav: no link>')


class BrowserOpen(Action):
    def __call__(self):
        print('<mdnav: open browser tab>')
        webbrowser.open_new_tab(self.target)


class OSOpen(Action):
    def __call__(self):
        if sys.platform.startswith('linux'):
            subprocess.call(['xdg-open', self.target])

        elif sys.platform.startswith('darwin'):
            subprocess.call(['open', self.target])

        else:
            os.startfile(self.target)


class VimOpen(Action):
    def __call__(self):
        import vim
        vim.command('e {}'.format(self.target))


def parse_link(cursor, lines):
    row, column = cursor
    line = lines[row]

    _logger.info('handle line %s (%s, %s)', line, row, column)
    link_text = select_from_start_of_link(line, column)

    if not link_text:
        _logger.info('could not find link text')
        return None

    m = link_pattern.match(link_text)

    if not m:
        _logger.info('does not match link pattern')
        return None

    _logger.info('found match: %s', m.groups())
    assert (m.group('direct') is None) != (m.group('indirect') is None)

    if m.group('direct') is not None:
        _logger.info('found direct link: %s', m.group('direct'))
        return m.group('direct')

    _logger.info('follow indirect link %s', m.group('indirect'))
    indrect_link_pattern = re.compile(
        r'^\[' + re.escape(m.group('indirect')) + r'\]:(.*)$'
    )

    for line in lines:
        m = indrect_link_pattern.match(line)

        if m:
            return m.group(1).strip()

    return None


link_pattern = re.compile(r'''
    ^
    \[                  # start of link text
        [^\]]*          # link text
    \]                  # end of link text
    (?:
        \(                  # start of target
            (?P<direct>
                [^\)]*
            )
        \)                  # collect
        |
        \[
            (?P<indirect>
                [^\]]*
            )
        \]
    )
    .*                  # any non matching characters
    $
''', re.VERBOSE)


def select_from_start_of_link(line, pos):
    start = line[:pos].rfind('[')
    # TODO: handle escapes

    if start < 0:
        return None

    return line[start:]


if __name__ == "__main__":
    plugin_entry_point()
