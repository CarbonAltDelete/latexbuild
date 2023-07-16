"""Build Jinja2 latex template, compile latex, and clean up environment

This module contains one class, Latex Build, which builds latex documents
from Jinja2 templates. The most useful, dynamic method is run_latex,
which handles the complex process of building a latex document
with any available system binary. All methods in the class may
be considered public. Two helper methods, build_pdf, and build_html,
are provided to handle the common build case of a PDF and an HTML
file for the common case builds with the texlive builds.
"""

import logging
import os
import shutil
from typing import Callable

from . import assertions
from .jinja2_extension import render_latex_template
from .subprocess_extension import check_output_cwd
from .utils import (
    random_str_uuid,
    random_name_filepath,
    read_file,
    list_filepathes_with_predicate,
)

LOGGER = logging.getLogger(__name__)


class LatexBuild(object):
    """Latex build base class

    :att path_jinja2: the root directory for latex jinja2 templates
    :att template_name: the relative path, to path_jinja2, to the desired
        jinja2 Latex template
    :att template_kwargs: a dictionary of key/values for jinja2 variables
        defaults to None for case when no values need to be passed
    :att path_template: the full path to the jinja2 template for rendering
    """

    def __init__(
        self,
        path_jinja2,
        template_name,
        template_kwargs=None,
        filters: dict[str, Callable] = None,
        cmd_latex: str = "pdflatex",
    ):
        # Initialize attributes
        self.path_jinja2 = path_jinja2
        self.template_name = template_name
        self.template_kwargs = template_kwargs
        self.path_template = os.path.join(path_jinja2, template_name)

        self.filters = filters

        self.cmd_latex = cmd_latex

        # Ensure attributes conform to appropriate type, raising error
        # as soon as possible
        if self.template_kwargs:
            assert isinstance(self.template_kwargs, dict)
        assert os.path.isdir(self.path_jinja2)
        assert os.path.isfile(self.path_template)

    def get_text_template(self):
        """Return the text rendered by the desired jinja2 template"""
        return render_latex_template(
            self.path_jinja2,
            self.template_name,
            self.template_kwargs,
            filters=self.filters,
        )

    def run_latex(self, cmd_wo_infile, path_outfile):
        """Main runner for latex build

        Should compile the object's Latex template using a list of latex
        shell commands, along with an output file location. Runs the latex
        shell command until the process's .aux file remains unchanged.

        :return: STR template text that is ultimately rendered

        :param cmd_wo_infile: a list of subprocess commands omitting the
            input file (example: ['pdflatex'])
        :param path_outfile: the full path to the desired final output file
            Must contain the same file extension as files generated by
            cmd_wo_infile, otherwise the process will fail
        """
        # Generate path variables
        text_template = self.get_text_template()
        path_template_random = random_name_filepath(self.path_template)
        path_template_dir = os.path.dirname(path_template_random)
        path_template_random_no_ext = os.path.splitext(path_template_random)[0]
        path_template_random_aux = path_template_random_no_ext + ".aux"
        ext_outfile = os.path.splitext(path_outfile)[-1]
        path_outfile_initial = "{}{}".format(
            path_template_random_no_ext,
            ext_outfile,
        )

        # Handle special case of MS Word
        if cmd_wo_infile[0] == "latex2rtf" and len(cmd_wo_infile) == 1:
            cmd_docx = cmd_wo_infile + ["-o", path_outfile_initial]
            # Need to run pdf2latex to generate aux file
            cmd_wo_infile = [self.cmd_latex]
        else:
            cmd_docx = None

        try:
            # Write template variable to a temporary file
            with open(path_template_random, "w") as temp_file:
                temp_file.write(text_template)
            cmd = cmd_wo_infile + [path_template_random]
            old_aux, new_aux = random_str_uuid(1), random_str_uuid(2)
            while old_aux != new_aux:
                # Run the relevant Latex command until old aux != new aux
                stdout = check_output_cwd(cmd, path_template_dir)
                LOGGER.debug("\n".join(stdout))
                old_aux, new_aux = new_aux, read_file(path_template_random_aux)

            # Handle special case of MS Word
            if cmd_docx:
                cmd_word = cmd_docx + [path_template_random]
                stdout = check_output_cwd(cmd_word, path_template_dir)
                LOGGER.debug("\n".join(stdout))

            shutil.move(path_outfile_initial, path_outfile)
            LOGGER.info(
                "Built {} from {}".format(
                    path_outfile,
                    self.path_template,
                ),
            )
        except Exception:
            LOGGER.exception("Failed during latex build")
        finally:
            # Clean up all temporary files associated with the
            # random file identifier for the process files
            path_gen = list_filepathes_with_predicate(
                path_template_dir,
                path_template_random_no_ext,
            )
            for path_gen_file in path_gen:
                os.remove(path_gen_file)
        return text_template

    def build_pdf(self, path_outfile):
        """Helper function for building a basic pdf file

        Raises ValueError if outfile type is not PDF
        :return: STR template text that is ultimately rendered
        """
        assertions.has_file_extension(path_outfile, ".pdf")
        return self.run_latex(
            [self.cmd_latex, "-interaction", "nonstopmode"],
            path_outfile,
        )

    def build_html(self, path_outfile):
        """Helper function for building a basic html file

        Raises ValueError if outfile type is not HTML
        :return: STR template text that is ultimately rendered
        """
        assertions.has_file_extension(path_outfile, ".html")
        return self.run_latex(["htlatex"], path_outfile)

    def build_docx(self, path_outfile):
        assertions.has_file_extension(path_outfile, ".docx")
        return self.run_latex(["latex2rtf"], path_outfile)
