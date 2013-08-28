import sys, os
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib'))

import sublime, sublime_plugin, re, codecs
import phpcoder.parser, phpcoder.resolver, phpcoder.editor, phpcoder.indexer
import json, threading, time

'''

TODO:
    [ ] doc info etc (add to completion list)
    # update index on on_post_save_async
    # keep mapping of files, classes, mtime
    # on app start, only index files that are needed
    [ ] fix isEnabled on commands

'''

class PhpCoder(object):
    __instance = None
    def __new__(cls):
        if PhpCoder.__instance is None:
            PhpCoder.__instance = object.__new__(cls)
            PhpCoder.__instance._init()
        return PhpCoder.__instance

    def _init(self):
        parserCache = sublime.packages_path() + os.sep + 'User' + os.sep + 'phpcoder-cache' + os.sep + 'parser'
        self.parser = phpcoder.parser.Parser(parserCache)
        self.indexer = phpcoder.indexer.Indexer()

    def editor(self, view):
        return phpcoder.editor.Editor(view, self.parser)


class PhpCoderComplete(sublime_plugin.EventListener):
    def on_query_completions(self, view, prefix, locations):
        if sublime.score_selector(view.scope_name(view.sel()[0].b), 'source.php') == 0:
            return
        editor = PhpCoder().editor(view)
        resolver = phpcoder.resolver.Resolver(editor)
        line = editor.before()
        if re.match(r'.*[,\(]\s*$', line):
            return self._completeParams(editor, resolver)
        if re.match(r'.*new [a-zA-Z0-9_]*$', line):
            return self._completeNew(view)
        if line[-1] == '$':
            return editor.findLocals()
        expr = editor.expr()
        if expr:
            return self._completeExpr(expr, editor, resolver)
        return []

    def on_modified(self, view):
        if sublime.score_selector(view.scope_name(view.sel()[0].b), 'source.php') == 0:
            return
        editor = PhpCoder().editor(view)
        doComplete = False
        line = editor.before()
        if re.match(r'.*[,\(]\s*$', line) or line[-1] == '$' or re.match(r'.*new [a-zA-Z0-9_]*$', line):
            doComplete = True
        else:
            expr = editor.expr()
            if expr and expr['prefix'][:2] in ['::', '->']:
                doComplete = True
        if doComplete:
            view.run_command('auto_complete', {
                'disable_auto_insert': True,
                'api_completions_only': True,
                'next_completion_if_showing': False,
                'auto_complete_commit_on_tab': True,
            })

    def _completeNew(self, view):
        return PhpCoder().indexer.getClasses(view.window().folders(), mode = 'complete')
        
    def _completeExpr(self, expr, editor, resolver):
        prev = expr['prefix'][:2]
        if prev in ['::', '->']:
            if re.match(r'^(parent)', expr['expr']):
                prev = '->'
            ret = resolver.resolve(expr['expr'])
            if ret:
                return editor.getCompletions(ret,
                    includeDefault = prev == '->',
                    includeStatic = prev == '::',
                    includePrivate = re.match(r'^(\$this|self|parent)', expr['expr']),
                    includeConstructor = False,
                )
        return ret

    def _completeParams(self, editor, resolver):
        offset = 0
        pos = editor.getPosition() - 1
        open = 0
        loop = 0
        commas = 0
        while not(open == 1 or pos == offset):
            c = editor.substr(pos - offset, pos - offset + 1)
            if c == '(':
                open += 1
            elif c == ')':
                open -= 1
            elif open == 0 and c == ',':
                commas += 1
            offset += 1
        m = re.match(r'.*new\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\($', editor.substr(0, pos - offset + 2), re.DOTALL)
        if m:
            klass = m.group(1)
            expr = {'expr': m.group(1), 'prefix': '->__construct()'}
        else:
            expr = editor.expr(-1 * offset)
        ret = []
        if expr and expr['expr'] and expr['prefix']:
            parsedPrefix = resolver.parseExpression('Dummy' + expr['prefix'])
            if parsedPrefix and len(parsedPrefix) > 1:
                prefix = parsedPrefix[1]['name']
                completions = []
                for r in resolver.resolve(expr['expr']):
                    try:
                        method = r['methods'][prefix]
                        name = ''
                        value = ''
                        if commas > 0:
                            value = ' '
                        if 'params' in method:
                            p = 1
                            for param in method['params']:
                                if p > commas:
                                    if 'initial' in param:
                                        # Fix default values refering to self with correct class name
                                        initial = param['initial']
                                        initial = re.sub(r'^self', r['name'], initial)
                                        name += '$' + param['name'] + ' = ' + initial
                                        value += '${' + str(p) + ':/* \\$' + param['name'] + ' = */ ' + initial + '}, '
                                    else:
                                        name += '$' + param['name'];
                                        value += '${' + str(p) + ':\\$' + param['name'] + '}, '
                                    name += ', '
                                    ret.append([name.rstrip(', '), value.rstrip(', ')])
                                p += 1
                    except (Exception, ) as e:
                        print(e)
        return ret
                    


class PhpCoderLookup(sublime_plugin.TextCommand):

    def run_(self, args1, args2):
        if 'event' in args2:
            self.fromMouseEvent = args2['event']
        else:
            self.fromMouseEvent = None
        sublime_plugin.TextCommand.run_(self, args1, args2)

    def run(self, edit):
        if sublime.score_selector(self.view.scope_name(self.view.sel()[0].b), 'source.php') == 0:
            return
        if self.fromMouseEvent:
            old_sel = [r for r in self.view.sel()]
            self.view.run_command("drag_select", {'event': self.fromMouseEvent})
            new_sel = self.view.sel()[0]
        editor = PhpCoder().editor(self.view)
        offset = 0
        pos = editor.getPosition()
        while re.match(r'[a-zA-Z_][a-zA-Z0-9_]*', editor.substr(pos + offset, pos + offset + 1)):
            offset += 1
        expr = editor.expr()
        
        if expr:
            expr['prefix'] += editor.substr(pos, pos+offset)
            if editor.substr(pos + offset, pos + offset + 1) == '(':
                expr['prefix'] += '()'
        else:
            wordRegion = self.view.word(self.view.sel()[0])
            expr = {'prefix': '', 'expr': self.view.substr(wordRegion)}
            if editor.substr(wordRegion.begin() - 1, wordRegion.begin()) == '$':
                expr['expr'] = '$' + expr['expr']

        if expr['expr']:
            resolver = phpcoder.resolver.Resolver(editor)
            self.prefix = None
            if expr['prefix']:
                parsedPrefix = resolver.parseExpression('Dummy' + expr['prefix'])
                if parsedPrefix and len(parsedPrefix) > 1:
                    self.prefix = parsedPrefix[1]['name']
            self.matches = []
            for r in resolver.resolve(expr['expr']):
                if self.prefix == None or \
                    ('properties' in r and self.prefix in r['properties']) or \
                    ('methods' in r and self.prefix in r['methods']):
                    self.matches.append(r)

            results = []
            for r in self.matches:
                results.append([
                    r['name'] + expr['prefix'],
                    r['path'], 
                ])
            if len(results) == 1:
                self.panel_on_select(0)
            elif len(results) > 0:
                self.view.window().show_quick_panel(results, self.panel_on_select, on_highlight = self.panel_on_highlight)

    def getPath(self, x):
        path = self.matches[x]['fullpath']
        line = self.matches[x]['line']
        if self.prefix:
            try:
                line = self.matches[x]['properties'][self.prefix]['line']
            except KeyError:
                try:
                    line = self.matches[x]['methods'][self.prefix]['line']
                except KeyError:
                    pass
        path += ":" + str(line)
        path += ":1"
        return path

    def panel_on_select(self, x):
        if x >= 0:
            self.view.window().open_file(self.getPath(x), sublime.ENCODED_POSITION)

    def panel_on_highlight(self, x):
        if x >= 0:
            self.view.window().open_file(self.getPath(x), sublime.ENCODED_POSITION | sublime.TRANSIENT)


class PhpCoderIndex(sublime_plugin.WindowCommand):      
    def run(self):
        threading.Thread(target = PhpCoder().indexer.update, args=(self.window.folders(),)).start()

class PhpCoderIndexUpdater(sublime_plugin.EventListener):
    def on_post_save_async(self, view):
        PhpCoder().indexer.indexFile(view.file_name())

    def on_activated_async(self, view):
        if view and view.window():
            threading.Thread(target = PhpCoder().indexer.update, args=(view.window().folders(),)).start()

class PhpCoderIndexLookup(sublime_plugin.WindowCommand):
    def run(self):
        results = PhpCoder().indexer.getClasses(self.window.folders())
        self.window.show_quick_panel(results, on_select = None)


