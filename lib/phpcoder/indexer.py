import sublime
import os, codecs, re, time

class Indexer:
    def __init__(self):
        self.index = {}
        self.folders = {}

    def indexFile(self, path):
        if not path:
            return
        if path in self.index:
            if self.index[path]['mtime'] == os.path.getmtime(path):
                return
        f = codecs.open(path, 'r', 'utf-8', errors = 'ignore')
        code = f.read()
        f.close()
        classes = re.findall(r'^\s*class\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:\{|extends|implements)', code, re.MULTILINE)
        self.index[path] = {'mtime': os.path.getmtime(path), 'classes': classes}

    def getClasses(self, folders, mode = 'lookup'):
        ret = []
        for (path, data) in self.index.items():
            if not data['classes']:
                continue
            for folder in folders:
                if path.startswith(folder):
                    for klass in data['classes']:
                        if mode == 'lookup':
                            ret.append([klass, path])
                        else:
                            ret.append([klass, klass + '(${1})'])
        return ret

    def update(self, folders, refresh = False):
        indent = (12 * ' ') + 'PHP Coder: '
        # TODO: also index stubs
        todo = []
        for folder in folders:
            if refresh or not (folder in self.folders):
                sublime.status_message(indent + "indexing " + folder)
                for dirname, dirs, files in os.walk(folder):
                    for name in files:
                        path = os.path.join(dirname, name)
                        if path[-4:] == '.php':
                            todo.append(path)
                self.folders[folder] = True

        if len(todo) > 0:
            done = 0
            start = time.time()
            for path in todo:
                self.indexFile(path)
                done += 1
                if done % 10 == 0:
                    progress = int(round(done / len(todo) * 100.0, 0));
                    sublime.status_message(indent + "indexing files " + str(progress) + '% ')
            sublime.status_message(indent + 'indexing took ' + str(round(time.time() - start, 3)) + ' seconds')
