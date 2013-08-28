import os
import hashlib
import subprocess
import json
import codecs
import phpcoder

class Parser:
    PHP_INTEL_PATH = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + '/../phpintel')
    CACHE_VERSION = '1.0.6' + phpcoder.__version__
    cache = {}

    def __init__(self, cachePath):
        self.path = os.path.abspath(os.path.expanduser(cachePath))
        if not os.path.isdir(self.path):
            os.makedirs(self.path)

    def _hash(self, file):
        key = file + self.CACHE_VERSION
        return hashlib.md5(key.encode('utf-8')).hexdigest()

    def _getCachedFile(self, file):
        return self.path + os.sep + self._hash(file) + '.json'

    def parse(self, file):
        file = os.path.abspath(os.path.expanduser(file))
        cachedFile = self._getCachedFile(file)
        if (not os.path.isfile(cachedFile)) or os.path.getmtime(file) > os.path.getmtime(cachedFile):
            print(" [parse] " + file)
            parsed = self._parse(file)
            f = codecs.open(cachedFile, 'w', 'utf-8')
            f.write(parsed)
            f.close()
        else:
            try:
                ret = Parser.cache[cachedFile]
                print(" [cached] " + file)
                return ret
            except KeyError:
                print(" [load] " + file)
                f = codecs.open(cachedFile, 'r', 'utf-8')
                parsed = f.read()
                f.close()

        ret = json.loads(parsed)
        Parser.cache[cachedFile] = ret
        return ret

    def _parse(self, file):
        os.chdir(self.PHP_INTEL_PATH)
        ret = subprocess.check_output(
            ['php', 'phpintel.php', file],
            stderr = open('/dev/null', 'w')
        ).decode('utf-8')
        return ret