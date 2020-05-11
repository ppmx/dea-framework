#!/usr/bin/env python3

import json
import os
import logging
import itertools

from sputnik import language
from sputnik import library
from sputnik import tools
from sputnik import compiler
from sputnik import rename

from sputnik.tools import indent

class TestHarness:
    """ This class describes the complete build process in order to generate
    an LLVM-Bitcode blob that can be put into KLEE. This blob is expected to contain
    the test harness as well as the blobs for the requested libraries and the semantic
    wrapper.

    This class is also expected to be used as basis for every specific test so some
    tests can overload some methods to generate a blob that fits all challenges for that
    specific test.
    """

    # 0.2 add verify() and equal() functions
    # 0.3 implement two kinds of test harnesses (symex and fuzzing test harness)
    VERSION = "TestHarness 0.3"

    CFLAGS_SEMANTIC_WRAPPER = "-S -emit-llvm -g {lib_cflags}"

    # List of library.Library instances that should be included in the build of this
    # test harness:
    libs = list()


    config = {
        'symex': {
            # String storing the path of the klee headers (set in load_general_config())
            'klee_headers': str()
        }
    }

    general_max_array_width = int()

    @classmethod
    def load_general_config(cls, configfile):
        """ Set the test-unrelated config for test harnesses in general. This
        method should not be called after settings of a specific test.

        Raises:
            FileNotFoundError: if configfile is an invalid path
            json.decoder.JSONDecodeError: if configfile is broken
        """

        with open(configfile) as f:
            config = json.load(f)

        # some general settings:
        cls.libs = [library.Library.load(p) for p in config['libs']]
        cls.general_max_array_width = config['general_max_array_width']
        cls.wordsize = config['wordsize']
        cls.verifier = config['verifier']

        # configuration for symex engine:
        cls.config['symex'] = config['symex'].copy()

        # configuration for fuzzing engine:
        cls.config['fuzzing'] = config['fuzzing'].copy()

    def __init__(self):
        """ TODO: Add some fancy architecture description here
        """

        # Mapping from lib.name to a Function() instance that defines the entry point
        # of that library call. This may be the real function (like 'isdigit') or the
        # name of the semantic wrapper function.
        self.entries = {lib.name: None for lib in self.libs}

        # storing width of arrays in general
        self.array_width = self.general_max_array_width

        # holding signature object
        self.__signature = None

        # used in build_target
        self.tmp = None

        # Configuration for that specific test: This attributes are set by self.configure().
        self.function = '<insert name of function here (not really HERE)'
        self.signature = None
        self.description = '<insert some poetic description here>'
        self.semantic_wrappers = list()

        # self.engine should be in ['symex', 'fuzzing']
        self.engine = None

        self.clean_state()

    def clean_state(self):
        self.arguments_cache = dict()
        self.testcases_fuzzing = {'default': ''}

        # holding strings of boolean expressions like 'x <= 3'
        self.assumptions = list()

    def set_engine_symex(self):
        self.engine = 'symex'

    def set_engine_fuzzing(self):
        self.engine = 'fuzzing'

        # per default there is one testcase. These strings are written in toolset generation inside
        # build_target_fuzzing():
        self.testcases_fuzzing = {'default': ''}

    @property
    def signature(self):
        """ Getter for signature object """
        return self.__signature

    @signature.setter
    def signature(self, sgn):
        """ A signature change may lead to a change in the function names of the entry points.

        Args:
            sgn: a C declaration describing the signature of the entry point
        """

        if not sgn:
            self.__signature = None
            return

        self.__signature = language.Signature.parse(sgn, self.array_width)

        for lib in self.libs:
            try:
                name = lib.build.resolve_function(self.signature.name)
            except KeyError:
                # this line is catched at least if self.signature.name points to a macro like 'fdim'
                name = f"{self.signature.name}"

            self.entries[lib.name] = self.signature.fork(name)

    def _configure(self):
        """ This method is used to set configuration for the test case. This includes at least
        the correct setting of self.signature. This is a backend function that gets called by
        self.prepare().
        """

        # by default: no setting here. please overload this method :)
        return

    def prepare(self):
        """ Set the configuration for this test.

        Can be overloaded. This function is called after self.load_general_config()
        and prepares the test by setting all relevant screws. It should at least consider
        to edit every configuration variable that is listed in the proper section in __init__().
        """

        self.clean_state()
        self._configure()

        # do post configuration depending on the settings done in self._configure()

        # if there is no given signature (e.g. because we don't want to call a semantic wrapper)
        # then we fetch the signature automatically..
        if not self.signature:
            self.signature = language.function_signature_raw(self.function) + ';'

            for lib in self.libs:
                self.entries[lib.name].name = f"{lib.name}_lib_entry_{self.function}"

        self.generate_arguments()
        self.define_assumptions()

    def engine_wrapper(self, method):
        # Note: Because I maybe want to switch the engine on the fly I don't use
        # something like builtin decorators. Unfortunately: https://stackoverflow.com/a/5067661.
        #
        # The disadvantage of that kind of wrapping is that we need to have a function implementation
        # for the requested engine if this method is called. Otherwise an exception will be raised.
        new_method = f"{method}_{self.engine}"
        return getattr(self, new_method)

    def generate_header(self):
        return list() + self.engine_wrapper("generate_header")()

    def generate_header_symex(self):
        return ["#include <klee/klee.h>"]

    def generate_header_fuzzing(self):
        return ["#include <stdio.h>", "void abort(void);"]

    def generate_return_values(self):
        code = list()

        for function in self.entries.values():
            if function.ret.type == "void" and function.ret.ptr_depth == 0:
                continue

            code.append(f"{function.ret};")

        return code

    def get_arguments(self):
        code = list()

        for arg in self.arguments_cache.values():
            vs = f" = {arg.value}" if arg.value else ""

            if arg.isptr:
                if arg.value:
                    # this is for things like 'char *ptr = dest;'
                    code.append(f"{arg.type_str()} {arg.name}{vs};")
                elif arg.type in ["void", "char"]:
                    # here we build an array of size self.array_width
                    # and add the null-limitation if it should be a C string:
                    code.append(f"{arg.type} {arg.name}[{arg.array_size}]{vs};")
                else:
                    # Note: at this point we have to keep in mind that we call the function
                    # not with {arg.name} as argument but with &{arg.name}!
                    code.append(f"{arg.type} {arg.name}{vs};")
            else:
                code.append(f"{arg.type} {arg.name}{vs};")

        return code

    def generate_arguments(self):
        for arg in self.signature.args:
            self.generate_argument(arg)

    def generate_argument(self, arg):
        self.arguments_cache[arg.name] = arg

    def define_input_space(self):
        """ This method defines the 'variable' or 'symbolic' input values. """

        code = list()

        for arg in self.arguments_cache.values():
            if not arg.value:
                code += self.define_input(arg)

        return code

    def define_input(self, variable):
        return self.engine_wrapper("define_input")(variable)

    def define_input_symex(self, variable):
        """ By default we define arguments only symbolic. The calls to make_symbolic
        are according to generate_arguments(). Expected pointers are therefore generated as
        arrays if and only if they are of type void or char.

        Be careful while overwriting this method: be aware that you need to specify the fuzzing
        testcase input.
        """

        code = list()

        if variable.isptr:
            if variable.type in ["void", "char"]:
                #size = f"{self.array_width} * sizeof({variable.type})"
                size = f"{variable.array_size} * sizeof({variable.type})"
                code.append(f"klee_make_symbolic({variable.name}, {size}, \"{variable.name}\");")
            else:
                code.append(f"klee_make_symbolic(&{variable.name}, sizeof({variable.name}), \"{variable.name}\");")
        else:
            code.append(f"klee_make_symbolic(&{variable.name}, sizeof({variable.name}), \"{variable.name}\");")

        return code

    def define_input_fuzzing(self, variable):
        """ Generates code to receive test input from afl-fuzz via stdin and generates
        test input simultaniously """

        arg = variable.name if variable.isptr else f"&{variable.name}"

        if variable.type == "int":
            fmtstr = "%d"
            testcase = "1234\n"
        elif variable.type == "size_t":
            fmtstr = "%zu"
            testcase = "1234\n"
        elif variable.type == "char" and variable.isptr:
            fmtstr = f"%{variable.array_size - 1}s"
            testcase = "A" * variable.array_size + '\n'
        elif variable.type == "char" and not variable.isptr:
            fmtstr = "%c"
            testcase = "A\n"
        elif variable.type == "long int":
            fmtstr = "%ld"
            testcase = "1234\n"
        elif variable.type == "long long int":
            fmtstr = "%lld"
            testcase = "1234\n"
        elif variable.type == "long":
            fmtstr = "%l"
            testcase = "1234\n"
        elif variable.type == "long long":
            fmtstr = "%ll"
            testcase = "1234\n"
        elif variable.type == 'wint_t':
            # this is a special variant:
            testcase = 'AA\n'
            self.testcases_fuzzing = {k: v + testcase for k, v in self.testcases_fuzzing.items()}
            return [f"read(0, {arg}, 4);"]
        else:
            raise Exception()

        self.testcases_fuzzing = {k: v + testcase for k, v in self.testcases_fuzzing.items()}

        return [f"scanf(\"{fmtstr}\", {arg});"]

    def generate_environment(self):
        # like global variables...
        return list()

    def generate_variables(self):
        """ Generate list of C code that can be used to declare the arguments
        and other stuff that should be inserted before the entry calls.

        Returns:
            Return list with lines of valid C code.
        """

        code = list()

        # auto-generate return values:
        code.append("// code from generate_return_values():")
        code += self.generate_return_values()
        code.append("")

        code.append("// code from get_arguments():")
        code += self.get_arguments()
        code.append("")

        code.append("// code from generate_environment():")
        code += self.generate_environment()
        code.append("")

        return code

    def generate_entry_declaration(self):
        code = list()

        for lib_name, entry in self.entries.items():
            code.append(entry.declaration())

        return code

    def generate_entry_calls(self):
        """ Generate lines of C code that call the functions of each library. """

        code = list()

        for lib_name, entry in self.entries.items():
            code.append(entry.call())

        return code

    def add_assumption(self, assumption):
        """
        Args:
            assumptions: string that specify a valid C espression like 'var_x <= 10'
        """

        self.assumptions.append(assumption)

    def define_assumptions(self):
        """ If this method is not overloaded in the test we try to make
        some clever assumptions on our own.
        """

        for name, arg in self.arguments_cache.items():
            if arg.isptr and arg.type == 'char':
                if self.array_width:
                    #self.add_assumption(f"{arg.name}[{self.array_width - 1}] == '\\0'")
                    self.add_assumption(f"{arg.name}[{arg.array_size - 1}] == '\\0'")
                else:
                    self.add_assumption(f"{arg.name}[0] == '\\0'")

    def generate_assumptions(self):
        """ This method generates C code and returns the lines of code as list. The
        generated code should implement the code that assumes all taken assumptions
        in self.assumptions.

        Return:
            A list of C code lines making calls to some assumtion function
        """

        code = list()

        for expr in self.assumptions:
            code.append(self.engine_wrapper("generate_assumption")(expr))

        return code

    def generate_assumption_symex(self, expr):
        #return f"klee_assume({expr});"
        return f"if (!({expr})) return 0;"

    def generate_assumption_fuzzing(self, expr):
        return f"if (!({expr})) return 0;"

    def generate_verify_function(self):
        if self.verifier == "new":
            return self.new_generate_verify_function()
        else:
            return self.traditional_generate_verify_function()

    def traditional_generate_verify_function(self):
        code = []
        code.append("void verifier()")
        code.append(f"{{")
        code.append(f"\tfor (size_t i = 0; i < {len(self.libs)}; i++) {{")
        code.append(f"\t\tfor (size_t j = 0; j < {len(self.libs)}; j++) {{")
        code.append(f"\t\t\tif (lib_eval(i, j) != 0)")
        code.append(f"\t\t\t\tsputnik_abort(\"assertion error\");")
        code.append(f"\t\t}}")
        code.append(f"\t}}")
        code.append(f"}}")
        return code

    def new_generate_verify_function(self):
        return [f"""
void verifier()
{{
    #define UNALLOCATED -1

    /* Initialization
     *
     * We use an array called mapping, to keep the index of the cluster that the proper
     * library is assigned to. At the beginning every lib (that means every place in mapping)
     * is set to UNALLOCATED.
     */
    int mapping[{len(self.libs)}];
    int count_cluster = 0;

    for (size_t i = 0; i < {len(self.libs)}; i++)
        mapping[i] = UNALLOCATED;

    /* Clustering step
     *
     * In this outer loop we consider every library represented by index i related to
     * the array mapping. Inside that loop we try to find an equivalence class for
     * library i, that means we want to find a library with index j that is assigned to
     * a cluster and is equal to the library indexed by i. As a consequence we can follow
     * that library i holds the same cluster index as library j.
     */
    for (size_t i = 0; i < {len(self.libs)}; i++) {{
        // continue if the current library is also assigned to a cluster
        if (mapping[i] != UNALLOCATED)
            continue;

        // check if library j can be clustered with library i
        for (size_t j = 0; j < {len(self.libs)}; j++) {{
            if (j == i || mapping[j] == UNALLOCATED)
                continue;

            // if they are considered as equivalent by lib_eval then we add lib i
            // to the cluster of lib j
            if (lib_eval(i, j) == 0) {{
                mapping[i] = mapping[j];
                break;
            }}
        }}

        // At this point we wasn't able to find an already existing and proper
        // equivalence class. So lib i builds an own cluster and we have to create a new
        // cluster index.
        if (mapping[i] == UNALLOCATED) {{
            mapping[i] = i + 1;
            count_cluster++;
        }}
    }}


    // Abort if there are more than one cluster.

    if (count_cluster > 1) {{
        // 1024 wird wohl reichen. famous last words :>
        // Schreibe für jede Lib eine Zeile mit: 'libname: clusterindex'
        char message[1024];
        char *message_ptr = message;

        for (size_t i = 0; i < 1024; i++)
            message[i] = '\\0';
 
        for (size_t i = 0; i < {len(self.libs)}; i++) {{
            // now emulate strcpy(message_ptr, libs_identifier[i]);
            for (char *li_ptr = libs_identifier[i]; *li_ptr != '\\0'; li_ptr++)
                *message_ptr++ = *li_ptr;

            *message_ptr++ = ':';

            // Process individual digits
            while (mapping[i] != 0)
            {{
                int rem = mapping[i] % 10;
                *message_ptr++ = (rem > 9) ? (rem - 10) + 'a' : rem + '0';
                mapping[i] = mapping[i] / 10;
            }}

            *message_ptr++ = (char) 0x0a;
        }}

        sputnik_abort(message);
    }}


}}
"""]

    def generate_evaluation_function(self):
        """ This method defines the used evaluation function expecting two
        indices representing the libraries that should be compared to
        equality. This method 'int lib_eval(int i, int j);' should return
        0 if the libraries are equal or any non zero value otherwise.
        
        Returns:
            A list of C code implementing the lib_eval function
        """

        code = list()
        code.append("int lib_eval(int i, int j)")
        code.append("{")
        code.append("   if (eval_return_values[i] == eval_return_values[j])")
        code.append("       return 0;")
        code.append("   return 1;")
        code.append("}")
        return code

    def get_property_space(self):
        """ This method generates lines of C code that are used in the global namespace
        part of a C program and it is intended to serve every variable that
        should be used in the verifier() or lib_eval() function.
        """

        code = list()
        code.append(f"{self.signature.ret.type} eval_return_values[{len(self.libs)}];")
        return code

    def prepare_verify_call(self):
        code = list()

        for i, lib in enumerate(self.libs):
            value = self.entries[lib.name].ret.name
            code.append(f"eval_return_values[{i}] = {value};")

        return code

    def generate_test_harness(self):
        """ This method is used to get the template of a test harness. It may be overloaded
        to implement an own scheme of the test harness but the overwritten template has
        to serve at least a main function in order to be able to generate a linkable blob
        that can be put into KLEE.

        Returns:
            Return C code that implements the test harness.
        """

        code = []

        code.append("/**")
        code.append(" * The following stuff is generated by generate_test_harness()")
        code.append(" * Version: {0}".format(TestHarness.VERSION))
        code.append(" */")
        code.append("")

        code.append("// code from generate_header():")
        code += self.generate_header()
        code.append("")

        code.append("// libs_identifier to map an index to a library name:")
        mop = ', '.join([f"\"{l.name}\"" for l in self.libs])
        code.append(f"const char *libs_identifier[{len(self.libs)}] = {{ {mop} }};")
        code.append("")

        if len(self.libs) > 1:
            code.append("// various helper functions:")
            code.append("void verifier();")
            code.append("int lib_eval(int i, int j);")
            code.append("void sputnik_abort(char *message);")
            code.append("")

        code.append("// code from get_property_space():")
        code += self.get_property_space()
        code.append("")

        code.append("// code from generate_entry_declaration():")
        code += self.generate_entry_declaration()
        code.append("")

        code.append("// code from generate_variables():")
        code += self.generate_variables()

        code.append("int main()")
        code.append("{")

        code += indent(self.generate_test_harness_body())
        code.append("")

        code.append("\treturn 0;")
        code.append("}")
        code.append("")

        if len(self.libs) > 1:
            code += self.generate_evaluation_function()
            code.append("")

            code += self.generate_verify_function()
            code.append("")

            code += self.generate_abort_function()
            code.append("")

        return '\n'.join(code)

    def generate_abort_function(self):
        code = list()

        code.append("void sputnik_abort(char *message)")
        code.append("{")
        code += indent(self.engine_wrapper("abort")())
        code.append("}")

        return code

    def abort_symex(self):
        # ... using klee_report_error according to klee/klee.h
        return ["""klee_report_error("", 0, message, "sputnik_error");"""]

    def abort_fuzzing(self):
        # TODO fuzzing afl abort with error message?!
        return ["abort();"]

    def generate_test_harness_body(self):
        code = list()

        code.append("// code from define_input_space():")
        code += self.define_input_space()
        code.append("")

        code.append("// code from generate_assumptions():")
        code += self.generate_assumptions()
        code.append("")

        code.append("// code from generate_entry_calls():")
        code += self.generate_entry_calls()
        code.append("")

        if len(self.libs) > 1:
            code.append("// code from prepare_verify_call()")
            code += self.prepare_verify_call()
            code.append("")

            code.append("verifier();")

        return code

    def generate_evaluation_function_array(self):
        """ This method generates code for an evaluation function
        that expects arrays of length self.array_width stored as pointers
        in eval_return_values.

        Returns:
            List of C code implementing the lib_eval() function.
        """

        code = ["int lib_eval(int i, int j) {"]

        code.append("\tchar *a = eval_return_values[i];")
        code.append("\tchar *b = eval_return_values[j];")
        code.append("")

        code.append(f"\tfor (size_t c = 0; c < {self.array_width}; c++)")
        code.append(f"\t\tif (a[c] != b[c]) return 1;")
        code.append("")

        code.append("\treturn 0;")
        code.append("}")
        return code

    def write_test_harness(self, filename):
        """ Writes the test harness into a file.

        Args:
            filename: path to file that gets filled with the generated test harness
        """

        th = self.generate_test_harness()

        with open(filename, 'w') as f:
            f.write(th)

        return filename

    #
    # BUILDER FUNCTIONS:
    #

    def build_semantic_wrappers(self, lib, target, tmp='/tmp/'):
        """
        Als Seiteneffekt dieser Funktion wird self.entries und self.links angepasst.

        Args:
            lib: Bibliothek, für die diese Wrapper gebaut werden sollen
            target: path where the blob should be stored
        """

        cflags = self.CFLAGS_SEMANTIC_WRAPPER.format(lib_cflags=lib.compiler_flags)

        local_tmp = tools.generate_tmp_dir(tmp, f"sputnik_tmp_semantics_{lib.name}_")

        # this list is used to store path of every built wrapper. These are the files
        # that needs to be linked together at the end.
        local_files = list()

        # Build every wrapper file specifically for that library:
        for wrapper in self.semantic_wrappers:
            dest = os.path.join(local_tmp, os.path.basename(wrapper).rsplit('.', 1)[0] + '.ll')
            src = os.path.abspath(wrapper)
            compiler.compile_file(dest, src, cflags, lib.directory)
            local_files.append(dest)

        # Link every built wrapper file together:
        blob = os.path.join(local_tmp, "blob.ll")
        compiler.link(blob, local_files, '-S')

        # Let the renamer run on this file and store the name of the renamed entry point:
        mapping = lib.load_rename_mapping()
        rename.substitute(blob, blob, mapping)

        mapping = rename.rename(target, blob, lib.name)

        # set the entry point to the new and renamed function (the semantic wrapper function)
        self.entries[lib.name].name = mapping['@' + self.entries[lib.name].name][1:]
        self.entries[lib.name].ret.rename("ret_" + lib.name)

        # compile the blob and update the list of linkable files:
        #compiler.assemble(target, blob)

        tools.cleanup_tmp_dir(local_tmp)

        return [target]

    def build_target(self, target_folder, test_harness=False, **kwargs):
        """ This method is the overall build process to generate a blob that is intended to put
        into the symbolic exection engine KLEE.

        Args:
            target: name of bitcode blob that should be generated
            keep_test_harness: string specifying path where generated test harness should be stored or None
        """

        # Create a temporary build directory:
        self.tmp = tools.generate_tmp_dir(add=f"sputnik_{self.function}_")

        links = [lib.target for lib in self.libs]

        # Build semantic wrapper for every included lib:
        if self.semantic_wrappers:
            for lib in self.libs:
                target_semwrapper = os.path.join(self.tmp, f"semantics_{lib.name}.ll")
                links += self.build_semantic_wrappers(lib, target_semwrapper)

        # write and compile test harness:
        source_test_harness = self.write_test_harness(os.path.join(self.tmp, "main.c"))
        target = self.engine_wrapper("build_target")(target_folder, source_test_harness, links)

        if test_harness:
            tools.copyfile(os.path.join(target_folder, f"test_harness.c"), source_test_harness)

        return target

    def build_target_symex(self, target_folder, source_test_harness, links):
        """ Hint: This method is called by build_target of a wrapper function """
        llvm_test_harness = source_test_harness.rsplit('.c', 1)[0] + '.ll'
        cflags = f"-S -emit-llvm -g -I{self.config['symex']['klee_headers']}"

        compiler.compile_file(llvm_test_harness, source_test_harness, cflags)

        # Link all together and finish build process:
        links.append(llvm_test_harness)

        # determine path of blob:
        target = os.path.join(target_folder, f"{self.function}.bc")

        #logging.debug("link %s to %s" % (local_links, target))
        compiler.link(target, links)

        return target

    def build_target_fuzzing(self, target_folder, source_test_harness, links):
        """ Hint: This method is called by build_target of a wrapper function """

        # .../clang -fPIC -c *.bc

        compiled_links = list()

        for src in links:
            dest = os.path.join(self.tmp, os.path.basename(src) + '.o')
            compiler.compile_file(dest, src, '-fPIC -c')
            compiled_links.append(dest)

        # invoke afl-gcc -o ./a.out main.c *.o
        ls = ' '.join(compiled_links)
        target = os.path.join(target_folder, f"{self.function}.afl")
        compiler.run_command(f"afl-gcc -o {target} {source_test_harness} {ls}")

        # create toolset inside that target folder
        self.generate_toolchain_fuzzing(target_folder, target)

        return target

    def generate_toolchain_fuzzing(self, target_folder, target):
        # 1. create run.sh for convenient starting of fuzzer
        # 2. create testcases and a findings folder
        with open(os.path.join(target_folder, "run.sh"), 'w') as f:
            f.write('\n'.join([
                '#!/bin/sh',
                'rm -rf findings/*',
                f"afl-fuzz -i testcases -o findings -- ./{os.path.basename(target)}"]
            ))

        os.makedirs(os.path.join(target_folder, "findings"), exist_ok=True)
        os.makedirs(os.path.join(target_folder, "testcases"), exist_ok=True)

        for name, data in self.testcases_fuzzing.items():
            with open(os.path.join(target_folder, "testcases", f"testcase_{name}"), 'w') as f:
                f.write(data)

        self.set_engine_fuzzing()

    def build_targets(self, folder_iter, test_harness=False, keep_folder=False):
        """ This method generates target blobs that implement different aspects.

        Wird überladen von Tests, die unter Umständen mehrere Blobs generieren.
        Dafür ist name_iter ein getter für namen von subfoldern. darin entsteht dann
        unter umständen eine description.txt und auf jeden fall
        {self.function}.bc

        Args:
            folder_iter: A name iterator yielding enough names for every blob.
            test_harness: A boolean saying if the test_harness should be kept in the folder

        Returns:
            A list of built blobs.
        """

        blob = self.build_target(next(folder_iter), test_harness)

        if not keep_folder:
            self.cleanup_all()

        return [blob]

    def build_targets_array(self, folder_iter, **kwargs):
        blobs = list()

        m = self.general_max_array_width

        for self.array_width in range(2, m + 1, max(int(m * 0.2), 1)):
            # especially: recover a clean state
            self.prepare()

            blobs.append(self.build_target(next(folder_iter), **kwargs))
            self.cleanup_all()

        return blobs

    def cleanup_all(self):
        """ This removes the temporary directory """
        tools.cleanup_tmp_dir(self.tmp)


