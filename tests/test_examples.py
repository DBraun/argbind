import glob
import pytest 
import pathlib
import subprocess
import os
from subprocess import PIPE
import tempfile
import yaml
import argbind

OVERWRITE = False

here = pathlib.Path(__file__).parent.resolve()
examples_path = here.parent / 'examples'
regression_path = (here / 'regression').resolve()
paths = glob.glob(str(examples_path) + '/*/*.py')

os.makedirs(regression_path, exist_ok=True)

def check(output, output_path):
    if not os.path.exists(output_path) or OVERWRITE:
        output_path.parent.mkdir(exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(output)
    else:
        with open(output_path, 'r') as f:
            reg_output = f.read()
        assert output == reg_output

@pytest.mark.parametrize("path", paths)
def test_example(path):
    # Get help text
    help_args = []

    if "groups" in path:
        help_args.append("evaluate")
    output = subprocess.run(["python", path] + help_args + ["-h"], 
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output = output.stdout.decode('utf-8')
    
    _path = path.split('examples/')[-1] + '.help'
    output_path = regression_path / _path
    # Ignore the bind_module ones for help text, as the PyTorch docstrings
    # might change on us, causing tests to fail.
    if "bind_module" not in path:
        check(output, output_path)
    
    # Execute it
    add_args = []
    if "groups" in path:
        add_args.append("train")
        
    if 'argparse' not in path:
        add_args.append("--args.debug=1")
        if 'mnist' in path:
            add_args.append("--main.epochs=0")
    elif 'mnist' in path:
        add_args.append("--epochs=0")
    
    if 'positional' in path:
        add_args.extend(["Bob", "bob@abc.com", "--hello.notes='Some notes about Bob'"])
    if 'subcommands' in path:
        add_args.append("download")
    if 'migration' in path:
        add_args.append("1")
    if "add_to_parser"in path:
        add_args.extend(["test", "test", "test"])
    

    print(f"python {path} " + " ".join(add_args))
    output = subprocess.run(["python", path] + add_args, 
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output = output.stdout.decode('utf-8')

    _path = path.split('examples/')[-1] + '.run'
    output_path = regression_path / _path
    check(output, output_path)

    # Test argbind with saving/loading args
    with tempfile.TemporaryDirectory() as tmpdir:
        if 'argparse' not in path:
            # Save args
            save_path = str(pathlib.Path(tmpdir) / 'args.yml')
            add_args = [f'--args.save={save_path}']
            if 'mnist' in path:
                add_args.append("--main.epochs=0")
            output = subprocess.run(["python", path] + add_args, 
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output1 = output.stdout.decode('utf-8')

            # Load args
            add_args[0] = f'--args.load={save_path}'
            output = subprocess.run(["python", path] + add_args, 
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output2 = output.stdout.decode('utf-8')

            assert output1 == output2        

def test_yaml_example():
    added_args = [
        {'env': {}, 'flags': ['--args.load=examples/yaml/conf/base.yml']},
        {'env': {}, 'flags': ['--args.load=examples/yaml/conf/exp1.yml']},
        {'env': {}, 'flags': ['--args.load=examples/yaml/conf/exp2.yml']},
        {'env': {}, 'flags': ['--args.load=examples/yaml/conf/exp3.yml']},
        {'env': {'ARGBIND_ENV_VAR': 'test'}, 'flags': ['--args.load=examples/yaml/conf/exp4.yml']},
        {'env': {}, 'flags': ['--args.load=examples/yaml/conf/exp4.yml']},
    ]

    path = str(examples_path / 'yaml' / 'main.py')
    for i, add_arg in enumerate(added_args):      
        cmd = [f"python", path] + add_arg['flags'] 

        environ = os.environ.copy()        
        environ.update(add_arg['env'])

        output = subprocess.run(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            env=environ
        )
        output = output.stdout.decode('utf-8')

        _path = path.split('examples/')[-1] + f'.run{i}'
        output_path = regression_path / _path
        check(output, output_path)

def test_nested_yaml_example():
    added_args = [
        {"flags": ["--args.load=examples/nested_yaml/conf/nested.yml"]},
    ]

    path = str(examples_path / 'nested_yaml' / 'main.py')
    for i, add_arg in enumerate(added_args):      
        cmd = [f"python", path] + add_arg['flags'] 
        output = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output = output.stdout.decode('utf-8')

        _path = path.split('examples/')[-1] + f'.run{i}'
        output_path = regression_path / _path
        check(output, output_path)

def test_typing_example():
    added_args = [
        [
            "--func.str_arg=test",
            "--func.int_arg=10",
            "--func.dict_arg=x=5 y=a",
            "--func.list_int_arg=1 2 3",
            "--func.list_str_arg=a b c",
            "--func.bool_arg",
            "--func.tuple_arg=1 1.0 number1"
        ]
    ]
    path = str(examples_path / 'typing' / 'with_argbind.py')
    for i, add_arg in enumerate(added_args):
        output = subprocess.run(["python", path] + add_arg, 
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output = output.stdout.decode('utf-8')

        _path = path.split('examples/')[-1] + f'.run{i}'
        output_path = regression_path / _path
        check(output, output_path)

def test_list_none_default():
    """Test that List arguments with None default stay None when not provided."""
    path = str(examples_path / 'typing' / 'with_argbind.py')

    test_cases = [
        {
            'name': 'no_list_args_provided',
            'args': [],
            'expected_in_output': [
                "List of ints argument - type: <class 'NoneType'>, val: None",
                "List of strings argument - type: <class 'NoneType'>, val: None"
            ]
        },
        {
            'name': 'only_list_int_provided',
            'args': ['--func.list_int_arg', '1 2 3'],
            'expected_in_output': [
                "List of ints argument - type: <class 'list'>, val: [1, 2, 3]",
                "List of strings argument - type: <class 'NoneType'>, val: None"
            ]
        },
        {
            'name': 'only_list_str_provided',
            'args': ['--func.list_str_arg', 'a b c'],
            'expected_in_output': [
                "List of ints argument - type: <class 'NoneType'>, val: None",
                "List of strings argument - type: <class 'list'>, val: ['a', 'b', 'c']"
            ]
        },
        {
            'name': 'both_lists_provided',
            'args': ['--func.list_int_arg', '10 20', '--func.list_str_arg', 'x y'],
            'expected_in_output': [
                "List of ints argument - type: <class 'list'>, val: [10, 20]",
                "List of strings argument - type: <class 'list'>, val: ['x', 'y']"
            ]
        },
    ]

    for test_case in test_cases:
        print(f"Testing: {test_case['name']}")
        cmd = ["python", path] + test_case['args']
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        output = result.stdout.decode('utf-8')

        for expected_line in test_case['expected_in_output']:
            assert expected_line in output, (
                f"Test '{test_case['name']}' failed:\n"
                f"  Command: {' '.join(cmd)}\n"
                f"  Expected line in output: {expected_line}\n"
                f"  Output:\n{output}\n"
                f"  Stderr: {result.stderr.decode('utf-8')}"
            )

def test_scoping_example():
    added_args = [
        [
            "--dataset.folder=newdefault",
        ],
        [
            "--dataset.folder=newdefault", 
            "--train/dataset.folder=train"
        ]
    ]

    path = str(examples_path / 'scoping' / 'with_argbind.py')
    for i, add_arg in enumerate(added_args):
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = str(pathlib.Path(tmpdir) / 'args.yml')
            add_args = [f'--args.save={save_path}'] + add_arg
            print(' '.join(["python", path] + add_args))
            output = subprocess.run(["python", path] + add_args, 
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            data = argbind.load_args(save_path)
            data = {key: val for key, val in data.items() if '/' not in key}
            argbind.dump_args(data, save_path)

            add_arg = [x for x in add_arg if '/' not in x]
            add_args = [f'--args.load={save_path}'] + add_arg
            
            output = subprocess.run(["python", path] + add_args, 
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output = output.stdout.decode('utf-8')

            _path = path.split('examples/')[-1] + f'.run{i}'
            output_path = regression_path / _path
            check(output, output_path)

def test_bool_flexibility():
    """Test that bool arguments support both flag-style and value-style syntax."""
    path = str(examples_path / 'booleans' / 'bool_example.py')

    test_cases = [
        {
            'name': 'no_arguments',
            'args': [],
            'expected': "Example(on=True, off=False)"
        },
        {
            'name': 'flag_style_on',
            'args': ['--Example.on'],
            'expected': "Example(on=True, off=False)"
        },
        {
            'name': 'flag_style_off',
            'args': ['--Example.off'],
            'expected': "Example(on=True, off=True)"
        },
        {
            'name': 'value_style_on_true',
            'args': ['--Example.on=1'],
            'expected': "Example(on=True, off=False)"
        },
        {
            'name': 'value_style_on_false',
            'args': ['--Example.on=0'],
            'expected': "Example(on=False, off=False)"
        },
        {
            'name': 'value_style_off_true',
            'args': ['--Example.off=1'],
            'expected': "Example(on=True, off=True)"
        },
        {
            'name': 'value_style_off_false',
            'args': ['--Example.off=0'],
            'expected': "Example(on=True, off=False)"
        },
        {
            'name': 'mixed_flag_and_value',
            'args': ['--Example.on', '--Example.off=0'],
            'expected': "Example(on=True, off=False)"
        },
        {
            'name': 'string_true_false',
            'args': ['--Example.on=true', '--Example.off=false'],
            'expected': "Example(on=True, off=False)"
        },
        {
            'name': 'flip_both_from_defaults',
            'args': ['--Example.on=0', '--Example.off'],
            'expected': "Example(on=False, off=True)"
        },
        {
            'name': 'capitalized_false_true',
            'args': ['--Example.on=False', '--Example.off=True'],
            'expected': "Example(on=False, off=True)"
        },
        {
            'name': 'capitalized_true_false',
            'args': ['--Example.on=True', '--Example.off=False'],
            'expected': "Example(on=True, off=False)"
        },
    ]

    for test_case in test_cases:
        print(f"Testing: {test_case['name']}")
        cmd = ["python", path] + test_case['args']
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        output = result.stdout.decode('utf-8').strip()
        expected = test_case['expected']

        assert output == expected, (
            f"Test '{test_case['name']}' failed:\n"
            f"  Command: {' '.join(cmd)}\n"
            f"  Expected: {expected}\n"
            f"  Got: {output}\n"
            f"  Stderr: {result.stderr.decode('utf-8')}"
        )

def test_default_factory_list():
    """Test that List fields with default_factory work correctly."""
    path = str(examples_path / 'default_factory' / 'list_example.py')

    test_cases = [
        {
            'name': 'default_list',
            'args': [],
            'expected': "Example(my_list=[1, 2, 3])"
        },
        {
            'name': 'override_list_with_space_separated',
            'args': ['--Example.my_list', '4 5 6'],
            'expected': "Example(my_list=[4, 5, 6])"
        },
        {
            'name': 'override_list_single_value',
            'args': ['--Example.my_list', '7 8'],
            'expected': "Example(my_list=[7, 8])"
        },
    ]

    for test_case in test_cases:
        print(f"Testing: {test_case['name']}")
        cmd = ["python", path] + test_case['args']
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        output = result.stdout.decode('utf-8').strip()
        expected = test_case['expected']

        assert output == expected, (
            f"Test '{test_case['name']}' failed:\n"
            f"  Command: {' '.join(cmd)}\n"
            f"  Expected: {expected}\n"
            f"  Got: {output}\n"
            f"  Stderr: {result.stderr.decode('utf-8')}"
        )

def test_yaml_type_casting():
    """Test that YAML values are cast to match function type annotations.

    This is a regression test for the issue where scientific notation like
    1e-4 in YAML files was kept as a string instead of being converted to float.
    """
    import tempfile

    # Create a test script
    test_script = """
import argbind

@argbind.bind()
def test_types(
    my_int: int = 0,
    my_float: float = 0.0,
    my_str: str = "",
):
    print(f"my_int={my_int},type={type(my_int).__name__}")
    print(f"my_float={my_float},type={type(my_float).__name__}")
    print(f"my_str={my_str},type={type(my_str).__name__}")

if __name__ == "__main__":
    args = argbind.parse_args()
    with argbind.scope(args):
        test_types()
"""

    test_cases = [
        {
            'name': 'scientific_notation_float',
            'yaml': 'test_types.my_float: 1e-4',
            'expected_in_output': [
                'my_float=0.0001,type=float',
            ]
        },
        {
            'name': 'string_to_int',
            'yaml': 'test_types.my_int: "42"',
            'expected_in_output': [
                'my_int=42,type=int',
            ]
        },
        {
            'name': 'int_to_str',
            'yaml': 'test_types.my_str: 123',
            'expected_in_output': [
                'my_str=123,type=str',
            ]
        },
        {
            'name': 'all_types_mixed',
            'yaml': '''test_types.my_int: "99"
test_types.my_float: 2.5e-3
test_types.my_str: 456''',
            'expected_in_output': [
                'my_int=99,type=int',
                'my_float=0.0025,type=float',
                'my_str=456,type=str',
            ]
        },
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        import os
        script_path = os.path.join(tmpdir, 'test_script.py')

        # Write the test script
        with open(script_path, 'w') as f:
            f.write(test_script)

        for test_case in test_cases:
            print(f"Testing: {test_case['name']}")

            # Write YAML file
            yaml_path = os.path.join(tmpdir, 'test.yml')
            with open(yaml_path, 'w') as f:
                f.write(test_case['yaml'])

            # Run the test
            cmd = ["python", script_path, f"--args.load={yaml_path}"]
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=tmpdir
            )

            output = result.stdout.decode('utf-8')

            # Check that all expected lines are in output
            for expected_line in test_case['expected_in_output']:
                assert expected_line in output, (
                    f"Test '{test_case['name']}' failed:\n"
                    f"  Command: {' '.join(cmd)}\n"
                    f"  Expected line in output: {expected_line}\n"
                    f"  Output:\n{output}\n"
                    f"  Stderr: {result.stderr.decode('utf-8')}"
                )

def test_yaml_bool_formats():
    """Test that booleans in YAML files work with all supported formats.

    This ensures that various YAML boolean representations (true, false, True,
    False, 0, 1, '0', '1', etc.) are correctly parsed as boolean values.
    """
    import tempfile

    # Create a test script
    test_script = """
import argbind
from dataclasses import dataclass

@argbind.bind()
@dataclass
class Example:
    on: bool = True
    off: bool = False

if __name__ == "__main__":
    args = argbind.parse_args()
    with argbind.scope(args):
        ex = Example()
        print(f"on={ex.on},off={ex.off}")
"""

    test_cases = [
        {
            'name': 'lowercase_true_false',
            'yaml': 'Example.on: false\nExample.off: true',
            'expected': 'on=False,off=True'
        },
        {
            'name': 'capitalized_True_False',
            'yaml': 'Example.on: False\nExample.off: True',
            'expected': 'on=False,off=True'
        },
        {
            'name': 'integer_0_1',
            'yaml': 'Example.on: 0\nExample.off: 1',
            'expected': 'on=False,off=True'
        },
        {
            'name': 'quoted_string_0_1',
            'yaml': "Example.on: '0'\nExample.off: '1'",
            'expected': 'on=False,off=True'
        },
        {
            'name': 'quoted_string_true_false',
            'yaml': "Example.on: 'false'\nExample.off: 'true'",
            'expected': 'on=False,off=True'
        },
        {
            'name': 'quoted_capitalized_True_False',
            'yaml': "Example.on: 'False'\nExample.off: 'True'",
            'expected': 'on=False,off=True'
        },
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        import os
        script_path = os.path.join(tmpdir, 'test_bool.py')

        # Write the test script
        with open(script_path, 'w') as f:
            f.write(test_script)

        for test_case in test_cases:
            print(f"Testing: {test_case['name']}")

            # Write YAML file
            yaml_path = os.path.join(tmpdir, 'test.yml')
            with open(yaml_path, 'w') as f:
                f.write(test_case['yaml'])

            # Run the test
            cmd = ["python", script_path, f"--args.load={yaml_path}"]
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=tmpdir
            )

            output = result.stdout.decode('utf-8').strip()
            expected = test_case['expected']

            assert output == expected, (
                f"Test '{test_case['name']}' failed:\n"
                f"  Command: {' '.join(cmd)}\n"
                f"  Expected: {expected}\n"
                f"  Got: {output}\n"
                f"  Stderr: {result.stderr.decode('utf-8')}"
            )
