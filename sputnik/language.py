#!/usr/bin/env python3

import re
import copy

class Signature:
    @staticmethod
    def parse(line, default_array_size=-1):
        """ This method parses a function declaration in line and returns
        a Signature object.

        Example:

        >>> sgn = Signature.parse("struct field *solver(int max, int sp);")
        >>> sgn.name
        'solver'
        >>> sgn.ret.type
        'struct field'
        >>> sgn.ret.isptr
        True
        >>> sgn.args
        [<Variable object at 0x7f51cd4ac5c0>, <Variable object at 0x7f51cd4ac6a0>]
        >>> [arg.name for arg in sgn.args]
        ['max', 'sp']
        """

        # {return value}{maybe ptr}{function name}({arguments});
        # groups of that re are: (return type, '*' if ptr else '', funcname, arguments)
        func_decl = re.compile(r"(.*)\s([*]*)([^(]*)\(([^)]*)\);", re.DOTALL)

        # Debug log
        # Line: 'char *strcpy(char *dest, const char *src);'
        # Ret:  'char'
        # ptr:  '*'
        # name: 'strcpy'
        # args: 'char *dest, const char *src'

        ret, ptr, name, args = func_decl.match(line).groups()

        # Create Variable() instances:
        ret_var = Variable(ret, 'unnamed', len(ptr))
        args_vars = [Variable.parse(arg, default_array_size) for arg in args.split(', ')] if args else []

        return Signature(name, args_vars, ret_var)

    def __init__(self, name, args, ret):
        """ Initialize a Signature instance.

        Args:
            name: string holding name of function
            args: list of Variable instances
            ret: Variable instance defining the return value of that signature
        """

        self.name, self.args, self.ret = name, args, ret

    def __eq__(self, other):
        return self.name == other.name and self.ret == other.ret and all(x == y for x, y in zip(self.args, other.args))

    def fork(self, name):
        """ This method returns a Function() instance and renames that function and it's return value """
        #new_ret = Variable(self.ret.type, "return_" + name, self.ret.ptr_depth)

        new_ret = copy.copy(self.ret)
        new_ret.rename("ret_" + name)

        new_args = [copy.copy(arg) for arg in self.args]

        return Function(name, new_args, new_ret)

class Function(Signature):
    def __init__(self, name, args, ret, body=None):
        super(Function, self).__init__(name, args, ret)
        self.body = body

    def declaration(self):
        """ Generate declaration of that function.

        Returns:
            Returns a string that can be used as declaration in C.

        Example:

        >>> f.declaration()
        int isdigit(int c);
        """

        args = ', '.join([str(a) for a in self.args])

        if self.ret.isptr:
            return f"{self.ret.type_str()}{self.name}({args});"
        return f"{self.ret.type_str()} {self.name}({args});"

    def definition(self, body=''):
        """ Generate definition of that function.

        Returns:
            Returns a string that can be used as definition in C.

        Example:

        >>> f.definition("return c >= '0' && c <= '9';")
        int isdigit(int c)
        {
            return c >= '0' && c <= '9';
        }
        """

        lines = []

        args = ', '.join([str(a) for a in self.args])

        if self.ret.isptr:
            lines.append(f"{self.ret.type_str()}{self.name}({args})")
        else:
            lines.append(f"{self.ret.type_str()} {self.name}({args})")

        lines.append("{")
        lines += [f"\t{l}" for l in body.split('\n')]
        lines.append("}")
        return '\n'.join(lines)

    def call(self):
        """ Generate a function call of that function.

        Returns:
            Returns a string that can be used as function call in C.

        Example:

        >>> f.call()
        ret_isdigit = isdigit(c);
        """

        args = ', '.join(['&' * (a.ptr_depth - 1) + a.name for a in self.args])

        if self.ret.type == "void" and not self.ret.isptr:
            return f"{self.name}({args});"
        return f"{self.ret.name} = {self.name}({args});"

class Variable:
    """ This class is used to represent a used C code variable in python. It serves some
    useful code to apply the stored informations to C code.
    """

    @staticmethod
    def parse(line, array_size):
        """ This method constructs a Variable object by parsing the signature from a string and creating
        the proper object.

        Args:
            line: string describing the variable as(e.g. 'char x')

        Returns:
            Variable object related to line.
        """

        # expected line: 'int *x;'
        type, ptr, name = re.match(r"(?:const )?(.*)\s([*]*)([^;]*)[;]?", line).groups()
        return Variable(type, name, len(ptr), array_size if len(ptr) else -1)

    def __init__(self, type, name, ptr_depth=0, array_size=-1, value=None):
        """ Constructor for a Variable object.

        Args:
            type: type of variable as string
            name: name of variable as string
            ptr_depth: count of nested pointers
            array_size: size of array (need to have a ptr_depth > 0
            value: the value of the variable like '45'
        """

        self.type = type
        self.name = name
        self.ptr_depth = ptr_depth

        # -1 at array_size marks an unknown array_size
        self.array_size = array_size
        self.value = value

    @property
    def isptr(self):
        """
        Returns:
            Returns true if and only if self should be a pointer.
        """

        return self.ptr_depth > 0

    def rename(self, name):
        self.name = name

    def type_str(self):
        return f"{self.type}{(' ' + self.ptr_depth * '*') if self.ptr_depth else ''}"

    def __str__(self):
        if self.ptr_depth:
            return f"{self.type_str()}{self.name}"
        return f"{self.type_str()} {self.name}"

    def __eq__(self, other):
        return self.name == other.name and self.type == other.type and self.ptr_depth == other.ptr_depth and self.array_size == other.array_size

def function_signature_raw(fname):
    """ This method fetches the signature of a function from the man page.

    Returns:
        The proper signature as string.
    """

    from subprocess import run
    from subprocess import PIPE as pipe

    # fetch man page:
    cmd = r"man -P cat 3 {0} | grep -m 1 -o -P -z '\w(\w*\s)*[*]?{0}\([^)]*\);' | cut -d';' -f1"
    proc = run(cmd.format(fname), stdout=pipe, shell=True)
    content = proc.stdout.decode().strip()

    # remove trailing newlines of multi-line-signature and
    # replace newlines with spaces in order to make a one-liner:
    line = ' '.join([l.strip() for l in content.split('\n')])
    return line + ';'

def function_signature(fname):
    """ This method fetches the signature of a function from the man page.

    Returns:
        The proper signature as a Signature object.
    """

    line = function_signature_raw(fname)
    return Signature.parse(line + ';')

def __test_variable():
    """ Tests the implemenetation of the class Variable.

    Raises:
        AssertionError: An implemented test failed.
    """

    # check parsing routine...
    testcases = [
        ("void x", Variable("void", "x", 0)),
        ("unsigned int x", Variable("unsigned int", "x", 0)),
        ("struct foo *bar", Variable("struct foo", "bar", 1)),
        ("int *******x", Variable("int", "x", 7))
    ]

    for line, check in testcases:
        assert Variable.parse(line) == check

    # check pointer behaviour
    var = Variable("void", "x", 0)
    assert not var.isptr
    assert var.ptr_depth == 0

    var = Variable("void", "foo_bar", 2)
    assert var.isptr
    assert var.ptr_depth == 2

    # check rename method
    var = Variable("void", "foo_bar", 2)
    assert var.name == "foo_bar"
    var.rename("bar")
    assert var.name == "bar"

    # check string functions
    var = Variable("void", "foo_bar", 0)
    assert var.type_str() == "void"
    assert str(var) == "void foo_bar"

    var = Variable("void", "foo_bar", 2)
    assert var.type_str() == "void **"
    assert str(var) == "void **foo_bar"

def __test_signature():
    """ Tests the implementation of the class Signature.

    Raises:
        AssertionError: An implemented test failed.
    """

    # check parsing routine...
    testcases = [
        ("void foo();", Signature(name="foo", args=[], ret=Variable("void", "unnamed", 0))),

        ("void foo(int x);", Signature(
            name="foo",
            args=[Variable("int", "x", 0)],
            ret=Variable("void", "unnamed", 0)
        )),

        ("void foo(int x, unsigned int **y);", Signature(
            name="foo",
            args=[Variable("int", "x", 0), Variable("unsigned int", "y", 2)],
            ret=Variable("void", "unnamed", 0)
        )),

        ("unsigned long int _foo_bar(int x, unsigned int **y);", Signature(
            name="_foo_bar",
            args=[Variable("int", "x", 0), Variable("unsigned int", "y", 2)],
            ret=Variable("unsigned long int", "unnamed", 0)
        )),

        ("unsigned long int ****_foo_bar(int x, unsigned int **y);", Signature(
            name="_foo_bar",
            args=[Variable("int", "x", 0), Variable("unsigned int", "y", 2)],
            ret=Variable("unsigned long int", "unnamed", 4)
        )),
    ]

    for sgn, check in testcases:
        assert Signature.parse(sgn) == check

    # check other methods...
    func = Signature.parse("int isdigit(int c);").fork("isdigit")
    assert func.declaration() == "int isdigit(int c);"
    assert func.call() == "ret_isdigit = isdigit(c);"

    func = Signature.parse("void *memcpy(void *dest, const void *src, size_t n);").fork("foo")
    assert func.declaration() == "void *foo(void *dest, void *src, size_t n);"
    assert func.call() == "ret_foo = foo(dest, src, n);"

    func = Signature.parse("unsigned int ***bar(size_t *x);").fork("foo")
    assert func.declaration() == "unsigned int ***foo(size_t *x);"
    assert func.call() == "ret_foo = foo(x);"

def __test_signature_fetching():
    """ Tests implementation of signature fetching.

    Raises:
        AssertionError: An implemented test failed.
    """

    testcases = [
        ("isalnum", "int isalnum(int c);"),
        ("memcpy", "void *memcpy(void *dest, const void *src, size_t n);"),
        ("getaddrinfo", "int getaddrinfo(const char *node, const char *service, const struct addrinfo *hints, struct addrinfo **res);")
    ]

    for name, check in testcases:
        assert function_signature_raw(name) == check

def test():
    """ Run all tests.

    Raises:
        AssertionError: An implemented test failed.
    """

    print("[+] run tests.")

    __test_variable()
    print("[>] Variable class tests passed.")

    __test_signature()
    print("[>] Signature class tests passed.")

    __test_signature_fetching()
    print("[>] Signature fetching tests passed.")


    print("[+] all tests passed.")

if __name__ == "__main__":
    test()
