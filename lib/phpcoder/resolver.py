import re

class Resolver:
    ARRAY_ACCESS = '->__array_access()'
    ARRAY_CREATE = '->__array_create()'
    
    expressions = {
        '^::([a-zA-Z_][a-zA-Z0-9_]*)$'      : 'class_constant',
        '^->([a-zA-Z_][a-zA-Z0-9_]*)\(\)$'  : 'class_method',
        '^->([a-zA-Z_][a-zA-Z0-9_]*)$'      : 'class_property',
        '^::([a-zA-Z_][a-zA-Z0-9_]*)\(\)$'  : 'class_static_call',
        '^::\\$([a-zA-Z_][a-zA-Z0-9_]*)$'   : 'class_static_property',
        '^([a-zA-Z_][a-zA-Z0-9_]*)\(\)$'    : 'function',
        '^\\$([a-zA-Z_][a-zA-Z0-9_]*)$'     : 'variable',
        '^\\$([a-zA-Z_][a-zA-Z0-9_]*)\[\]$'     : 'array',
        '^([a-zA-Z_][a-zA-Z0-9_]*)$'        : 'class',
        '^new ([a-zA-Z_][a-zA-Z0-9_]*)\(\)$' : 'object',
    }
    def __init__(self, editor):
        self.editor = editor

    def parseExpression(self, expr):
        expr = expr.replace(self.ARRAY_CREATE + self.ARRAY_ACCESS, '');
        expr = expr.replace(self.ARRAY_ACCESS + self.ARRAY_CREATE, '');
        ret = []
        for symbol in re.sub(r'(::|->)', r'|\1', expr).split('|'):
            name = None
            type = None
            for (regex, type) in self.expressions.items():
                m = re.match(regex, symbol)
                if m:
                    name = m.group(1)
                    break
            if name is None:
                raise Exception("Could not understand expression " + repr(symbol))
            ret.append({'name': name, 'type': type, 'symbol': symbol})
        return ret

    def recursiveLookup(self, klass, depth = 0):
        if depth > 5:
            return []
        lookup = self.editor.lookup(klass)
        ret = []
        for loc in lookup:
            try:
                loc['ast']['classes'][klass]['path'] = loc['path']
                loc['ast']['classes'][klass]['fullpath'] = loc['fullpath']
                if depth >= 0:
                    ret.append(loc['ast']['classes'][klass])
                if 'extends' in loc['ast']['classes'][klass] and loc['ast']['classes'][klass]['extends']:
                    for r in self.recursiveLookup(loc['ast']['classes'][klass]['extends'], depth + 1):
                        ret.append(r)
            except (KeyError, TypeError) as ee:
                pass
        return ret

    def resolve(self, expr, depth = 0):
        if depth > 10:
            return []
        expr = self.parseExpression(expr)
        name = expr[0]['name'];
        ret = []
        recursiveLookupDepth = 0
        if expr[0]['name'] in ['this', 'parent', 'self']:
            # resolve class locals
            name = self.editor.findMyClass()
            if expr[0]['name'] == 'parent':
                recursiveLookupDepth = -1
        elif expr[0]['type'] == 'variable':
            # resolve variables
            types = []
            try:
                # check whether this variable is globally defined
                me = self.editor.parseMe()
                types = me['globals'][name]
            except Exception:
                # check for function scope variables
                klass = self.editor.findMyClass()
                method = self.editor.findMyMethod()
                for location in self.editor.lookup(klass):
                    try:
                        for type in location['ast']['classes'][klass]['methods'][method]['locals'][name]:
                            types.append(type)
                    except Exception:
                        pass
            for type in types:
                newExpr = type
                for e in range(1, len(expr)):
                    newExpr += expr[e]['symbol']
                children = self.resolve(newExpr, depth + 1)
                if children:
                    for c in children:
                        ret.append(c)
            return ret
        if len(expr) == 0:
            return None
        if len(expr) == 1:
            return self.recursiveLookup(name, recursiveLookupDepth)

        attr = expr[1]['name'];
        
        for location in self.recursiveLookup(name, recursiveLookupDepth):
            types = None
            try:
                types = location['properties'][attr]['type']
            except KeyError:
                try:
                    types = location['methods'][attr]['type']
                except KeyError:
                    pass
            if types:
                for type in types:
                    resolvedExpr = type
                    for e in range(2, len(expr)):
                        resolvedExpr += expr[e]['symbol']
                    children = self.resolve(resolvedExpr, depth + 1)
                    if children:
                        for c in children:
                            ret.append(c)
        return ret
