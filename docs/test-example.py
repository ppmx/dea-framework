#!/usr/bin/env python3

from sputnik import runner
from sputnik import TestHarness

# This example is built for version 0.2
class name_of_test:
    def configure(self):
        """ This function may set configuration for a special test case. """
        raise NotImplementedError

    def prepare(self):
        """
        Set the configuration for this test.

        Can be overloaded. This function is called after self.load_general_config()
        and prepares the test by setting all relevant screws. It should at least consider
        to edit every configuration variable that is listed in the proper section in __init__().
        """

        self.configure()

        # do post configuration:
        if not self.signature:
            self.signature = language.function_signature_raw(self.function) + ';'

        raise NotImplementedError

    def generate_variables(self):
        """
        Generate list of C code that can be used to declare the arguments and other stuff
        that should be inserted before the entry calls.

        Returns:
            Return list with lines of valid C code.
        """

        raise NotImplementedError

    def generate_entry_calls(self):
        """
        Returns:
            A list of C code lines representing calls to the entry points
        """
        raise NotImplementedError

    def generate_verification_code(self):
        """
        Returns:
            A list of C code lines representing the verification part.
        """
        raise NotImplementedError

    def get_assumtions(self):
        """
        Returns:
            A list of C code lines representing assumptions made for the symbolic
            execution engine.
        """
        raise NotImplementedError

    def generate_header(self):
        """
        Returns:
            A list of C code lines representing the header lines (like includes or defines..)
        """
        raise NotImplementedError

    def get_property_space(self):
        """
        Returns:
            A list of C code lines that are added in the global space of the test harness. It
            can hold an array storing informations for every library and can (or is intended to)
            be used by the equal function.
        """
        raise NotImplementedError

    def generate_eval_function(self):
        """
        Returns:
            A list of C code holding at least a function with signature int lib_eval(int i, int j).
            This eval function can do whatever it want's to do but it should return 0 if and
            only if the libraries represented by identifiers i and j are equal.
        """
        raise NotImplementedError

    def prepare_verify_call(self):
        """
        Returns:
            A list of C code added before the call to verifier(). It can adjust all relevant
            informations especially for the equal functions.
        """
        raise NotImplementedError

    def generate_test_harness(self):
        """
        Returns:
            Return C code that implements the test harness.
        """
        raise NotImplementedError


implemented_tests = [name_of_test]

if __name__ == "__main__":
    runner(name_of_test)
