import re, os
import sublime
import hashlib
import codecs

class Editor:

    def __init__(self, view, parser):
        self.view = view
        self.pos = 0
        self.reset()
        self.parser = parser

    def getCursorPosition(self):
        return self.view.sel()[0].begin()

    def getPosition(self):
        return self.pos

    def reset(self):
        self.pos = self.getCursorPosition()

    def substr(self, begin, end):
        return self.view.substr(sublime.Region(begin, end))

    def line(self, pos):
        return self.view.substr(self.view.line(sublime.Region(pos, pos)))

    def before(self):
        pos = self.getCursorPosition()
        lineRegion = self.view.line(sublime.Region(pos, pos));
        return self.view.substr(sublime.Region(lineRegion.begin(), pos))

    def lookup(self, symbols, includePartialMatches = False, recursive = False):
        if isinstance(symbols, str):
            symbols = (symbols,)
        locations = {}
        for symbol in symbols:
            index = self.view.window().lookup_symbol_in_index(symbol)
            stubFile = os.path.dirname(os.path.abspath(__file__)) + os.sep + '..' + os.sep + 'stubs' + os.sep + symbol + '.php'
            if os.path.isfile(stubFile):
                index.append([stubFile, stubFile, [0,0]])
            for loc in self.view.window().lookup_symbol_in_index(symbol):
                path = loc[1]
                if path[-3:] != 'php':
                    continue
                if path in locations:
                    if symbol not in locations[path]['symbols']:
                        locations[path]['symbols'].append(symbol)
                        locations[path]['pos'] = loc[2]
                        locations[path]['name'] += '::' + symbol
                else:
                    locations[path] = {
                        'path': path,
                        'fullpath': loc[0],
                        'pos': loc[2],
                        'symbols': [symbol],
                        'name': symbol
                    }
        locations = list(locations.values())
        locations.sort(key=lambda x: len(x['symbols']), reverse = True)
        results = []
        exactMatch = False
        for loc in locations:
            if len(loc['symbols']) == len(symbols):
                exactMatch = True
            if  (includePartialMatches and not exactMatch) or len(loc['symbols']) == len(symbols):
                loc['ast'] = self.parser.parse(loc['fullpath'])
                results.append(loc)
        return results

    def parseMe(self):
        return self.parser.parse(self.view.file_name())

    def findMyClass(self):
        lineRegion = self.view.line(self.view.sel()[0])
        while lineRegion.begin() > 0:
            lineRegion = self.view.line(sublime.Region(lineRegion.begin() - 1, lineRegion.begin()))
            m = re.match(r'.*class\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:\{|extends|implements)', self.view.substr(lineRegion))
            if m:
                return m.group(1)

    def findMyMethod(self):
        lineRegion = self.view.line(self.view.sel()[0])
        while lineRegion.begin() > 0:
            lineRegion = self.view.line(sublime.Region(lineRegion.begin() - 1, lineRegion.begin()))
            m = re.match(r'.*function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', self.view.substr(lineRegion))
            if m:
                return m.group(1)

    def findLocals(self):
        lineRegion = self.view.line(self.view.sel()[0])
        ret = []
        while lineRegion.begin() > 0:
            lineRegion = self.view.line(sublime.Region(lineRegion.begin() - 1, lineRegion.begin()))
            line = self.view.substr(lineRegion);
            m = re.match(r'.*function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', line)
            if m:
                if not re.match(r'.*static.*', line):
                    ret.append(['$this', '\\$this->'])
                    ret.append(['parent', 'parent::'])
                break;
            m = re.match(r'\s*\$([a-zA-Z0-9_]+)\s*=.*', line)
            if m:
                ret.append(['$' + m.group(1), '\\$' + m.group(1)])
        return ret

    def expr(self, relativePos = 0):
        self.reset()
        self.pos = self.pos + relativePos
        text = self.substr(0, self.pos)
        m = re.match('.*?((::|\->)(\$?[a-zA-Z_]?[a-zA-Z0-9_]*))$', text, re.DOTALL)
        if m:
            prefix = m.group(1)
            ret = {'prefix': prefix, 'expr': '', 'end': self.pos}
            start = self.pos - len(prefix)
            text = self.substr(0, start);
            while len(text) > 0:
                # Fix brackets
                if text[-1] == ')':
                    end = len(text) - 2
                    open = 1
                    while end >= 0:
                        if text[end] == ')':
                            open += 1
                        if text[end] == '(':
                            open -= 1
                        if open == 0:
                            break
                        end -= 1;
                    start = start - (len(text) - end) + 2
                    text = text[:end] + '()'

                m = re.match(r'.*?((::|\->)?\$?[a-zA-Z_][a-zA-Z0-9_]*(\(\))?)$', text, re.DOTALL)
                if m:
                    ret['expr'] = m.group(1) + ret['expr']
                    start = start - len(m.group(1))
                    text = text[:-len(m.group(1))]
                    continue
                break
            if ret['expr'][:2] in ['::', '->']:
                return None
            ret['start'] = start
            return ret
        return None

    def getCompletions(self, classes, includePrivate = False, includeStatic = True, includeDefault = True, includeConstructor = True):
        ret = []
        for ast in classes:
            if 'methods' in ast:
                for (name, method) in ast['methods'].items():
                    if name == '__construct' and not includeConstructor:
                        continue
                    if 'modifiers' in method:
                        if includeStatic == False and 'static' in method['modifiers']:
                            continue
                        if includeDefault == False and not('static' in method['modifiers']):
                            continue
                        if includePrivate == False and 'private' in method['modifiers']:
                            continue
                    name = method['name'] + '('
                    value = method['name'] + '('
                    if 'params' in method:
                        p = 1
                        for param in method['params']:
                            name += '$' + param['name'];
                            if 'initial' in param:
                                name += ' = ' + param['initial']
                            else:
                                value += '${' + str(p) + ':\\$' + param['name'] + '}, '
                            name += ', '
                            p += 1
                    name = name.rstrip(', ') + ')'
                    value = value.rstrip(', ') + ')'
                    ret.append([name, value])

            if 'properties' in ast:
                for (name, prop) in ast['properties'].items():
                    if 'modifiers' in prop:
                        if includeStatic == False and 'static' in prop['modifiers']:
                            continue
                        if includeDefault == False and not('static' in prop['modifiers'] or 'const' in prop['modifiers']):
                            continue
                        if includePrivate == False and 'private' in prop['modifiers']:
                            continue
                    orig = name
                    value = name
                    if not('modifiers' in prop and 'const' in prop['modifiers']):
                        name = '$' + name
                    if 'modifiers' in prop and 'static' in prop['modifiers']:
                        value = '\\$' + orig
                    ret.append([name, value])
        return ret

