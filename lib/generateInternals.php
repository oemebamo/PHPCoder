<?php

function test($a, $b, $c = array('x' => false, 'y' => 'boo', 9), $d = false) {

}

class InternalsGenerator {
    public function generateFunctions() {
        $functions = get_defined_functions();
        $functions = $functions['internal'];
        foreach ($functions as $func) {
            $obj = new ReflectionFunction($func);
        }
    }

    public function processFunction($functionName) {
        $function = new ReflectionFunction($functionName);
        foreach ($function->getParameters() as $p) {
            $param = array('name' => $p->getName());
            if ($p->isOptional()) {
                $param['initial'] = var_export($p->getDefaultValue(), true);
                $param['initial'] = preg_replace('/\s*\n\s*/', ' ', $param['initial']);
            }
            print_r($param);
        }
    }
}

$gen = new InternalsGenerator();
$gen->processFunction('preg_match');

