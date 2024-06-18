#!/usr/bin/env python3
import ast
import csv
import errno
import gzip
import json
import logging
import os
import re
import shutil
import tarfile
import zipfile
from typing import Dict, List, Optional

import pkg_resources

from autoval.lib.utils.autoval_exceptions import TestError
from autoval.lib.utils.autoval_log import AutovalLog


# pyre-fixme[3]: Return type must be annotated.
# pyre-fixme[2]: Parameter must be annotated.
def log(func):
    # pyre-fixme[53]: Captured variable `func` is not annotated.
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def wrap(*args, **kwargs):
        # Call the original function
        ret_val = func(*args, **kwargs)
        # Log the function name, arguments and return value
        logging.info(
            f"Method: {func.__name__}, \nargs: {args}, kwargs: {kwargs}\n Return: {ret_val}"
        )
        # Return the result
        return ret_val

    return wrap


class GenericUtils:
    @staticmethod
    def extract(
        # pyre-fixme[2]: Parameter must be annotated.
        file_path_to_extract,
        # pyre-fixme[2]: Parameter must be annotated.
        directory_to_extract_to,
        omit_archive_top_directory: bool = False,
    ) -> None:
        """
        This method is used to extract files with .tar.gz .zip and .tar.bz2
        extensions and save to the directory_to_extract folder
        Arguments:
        file_path_to_extract : the archived file path
        directory_to_extract_to : directory path to which the unarchived content
                                  has to be saved
        omit_archive_top_directory : if user wants to omit the top directory of
                                     archived data and copy contents below it to
                                     directory_to_extract_to
        """
        # traceback.print_stack()
        file_opener = None
        if file_path_to_extract.endswith(".zip"):
            file_handle, mode = zipfile.ZipFile, "r"
        elif file_path_to_extract.endswith(".tar.gz") or file_path_to_extract.endswith(
            ".tgz"
        ):
            file_handle, mode = tarfile.open, "r:*"
        elif file_path_to_extract.endswith(".tar.bz2") or file_path_to_extract.endswith(
            ".tbz"
        ):
            file_handle, mode = tarfile.open, "r:bz2"
        else:
            raise TestError(
                "Could not extract `%s` as no appropriate extractor is found"
                % file_path_to_extract
            )

        GenericUtils.create_dir(directory_to_extract_to)
        try:
            # pyre-fixme[6]: For 2nd param expected
            #  `Union[typing_extensions.Literal['a'], typing_extensions.Literal['r'],
            #  typing_extensions.Literal['w'], typing_extensions.Literal['x']]` but got
            #  `typing_extensions.LiteralString`.
            file_opener = file_handle(file_path_to_extract, mode)
            file_opener.extractall(directory_to_extract_to)
            if omit_archive_top_directory:
                archived_file = os.path.basename(file_path_to_extract)
                unarchived_root_dir = os.path.join(
                    directory_to_extract_to, os.path.splitext(archived_file)[0]
                )
                files_list = os.listdir(unarchived_root_dir)
                file_paths = [
                    os.path.join(unarchived_root_dir, filename)
                    for filename in files_list
                ]
                for each_file in file_paths:
                    _path, _file = os.path.split(each_file)
                    _file = os.path.join(directory_to_extract_to, _file)
                    if os.path.exists(_file):
                        GenericUtils.delete_file(_file)
                    shutil.move(each_file, directory_to_extract_to)
                shutil.rmtree(unarchived_root_dir)
        except Exception as _e:
            raise TestError("Unable to Extract file (%s) " % str(_e))
        finally:
            if file_opener:
                file_opener.close()

    @staticmethod
    # pyre-fixme[2]: Parameter must be annotated.
    def gzip_file(source, target_file) -> None:
        # traceback.print_stack()
        with open(source, "rb") as orig_file:
            with gzip.open(target_file, "wb") as zipped_file:
                zipped_file.writelines(orig_file)

    @staticmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def create_dir(path, force_recreate: bool = False):
        """
        Create directory path.
        @param path: Path to create
        @return: None. Throws exception on error. Ignores error if directory
        already exists.
        """
        # traceback.print_stack()
        try:
            os.umask(0)
            os.makedirs(path)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise
            elif force_recreate:
                shutil.rmtree(path)
                os.mkdir(path)
        return path

    @staticmethod
    # pyre-fixme[2]: Parameter must be annotated.
    def delete_file(path) -> None:
        """
        @param path: Path to delete
        """
        # traceback.print_stack()
        if os.path.isfile(path):
            os.remove(path)  # remove the file
        elif os.path.isdir(path):
            shutil.rmtree(path)  # remove dir and all contains
        else:
            # pyre-fixme[48]: Expression `"file {} is not a file or
            #  dir.".format(path)` has type `str` but must extend BaseException.
            raise ("file {} is not a file or dir.".format(path))

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def convert_to_ascii(cls, dic):
        """Removes all special characters from the provided nested structure
        and return the structure which is safe to perform json.dump.
        Return Empty dictionary if nothing to convert. Fix for T19755704."""
        # traceback.print_stack()
        if isinstance(dic, dict):
            for k in dic:
                dic[k] = cls.convert_to_ascii(dic[k])
            return dic
        elif isinstance(dic, list):
            for i, k in enumerate(dic):
                dic[i] = cls.convert_to_ascii(k)
            return dic
        else:
            try:
                return dic.decode("ascii", "ignore")
            except Exception:
                return dic

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def flatten_dict(cls, d, prefix: str = ""):
        """
        Transform a nested dict of lists into a flat dict
        """
        # traceback.print_stack()
        values = {}
        for k, v in d.items():
            if isinstance(v, list):
                values.update(cls.flatten_dict(v[0], prefix))
            elif isinstance(v, dict):
                if prefix:
                    _prefix = "%s%s_" % (prefix, k)
                else:
                    _prefix = "%s_" % (k)
                values.update(cls.flatten_dict(v, _prefix))
            else:
                values["%s%s" % (prefix, k)] = v
        return values

    @classmethod
    # pyre-fixme[2]: Parameter must be annotated.
    def csv_to_json(cls, file_path) -> str:
        # traceback.print_stack()
        json_dump = {}
        with open(file_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            json_dump = json.dumps(rows)
        return json_dump

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def parse_csv(cls, file_paths):
        # traceback.print_stack()
        results = {}
        for f in file_paths:
            AutovalLog.log_info("Parsing results from %s" % (f))
            """
            CSV file expected to have 1 header row with column names, first
            column of other rows is the job name. Example:
            Jobname,Read_IOPS,Read_BW,Write_IOPS,Write_BW,Mean_Read_Latency
            RandomRead_QD1_run1,30302.4,121209,0.0,0
            RandomRead_QD2_run1,54747.1,218988,0.0,0
            """
            with open(f, "r") as csvfile:
                reader = csv.reader(csvfile)
                found_headers = False
                for row in reader:
                    if not found_headers:
                        found_headers = True
                        headers = row
                        continue
                    # Start at row[1] to skip job name, which we use as the key
                    for i, item in enumerate(row[1:]):
                        # pyre-fixme[61]: `headers` is undefined, or not always defined.
                        key = row[0] + ":" + headers[i + 1]
                        results[key] = item
        return results

    @staticmethod
    # pyre-fixme[24]: Generic type `dict` expects 2 type parameters, use
    #  `typing.Dict[<key type>, <value type>]` to avoid runtime subscripting errors.
    def read_resource_cfg(file_path: str, module: str = "autoval") -> Dict:
        """This function reads the resource json config file and returns the dictionary.
        If the file does not exist, it raises FileNotFoundError

        Assume that we want to read a file located at autoval/cfg/site_settings/site_settings.json,
        To read this file, caller can call this API as below
        read_resource_file(file_path="cfg/site_settings/site_settings.json", module="autoval")

        Args:
            file_path: The relative file path from the module directory
            module: The module name. It must be a valid python package. Default Value :autoval

        Returns:
            Resource config file content

        Raises:
            FileNotFoundError: If resource config file does not exist
        """
        # traceback.print_stack()
        absolute_file_path = pkg_resources.resource_filename(module, file_path)
        AutovalLog.log_debug(
            f"Relative path from {module}: {file_path}, Resolved absolute resource cfg file path: {absolute_file_path}"
        )
        if os.path.exists(absolute_file_path):
            with open(absolute_file_path) as cfg_file:
                return json.load(cfg_file)
        else:
            raise FileNotFoundError(f"Config file {absolute_file_path} does not exist")

    @staticmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def recursive_file_list(root):
        """
        Method to walk over the root directory hierarchy and return the
        list of absolute paths for each file in the directory tree.
        """
        # traceback.print_stack()
        path_list = []
        for root, _dirs, files in os.walk(root):
            for name in files:
                path_list.append(os.path.join(root, name))
        return path_list

    @staticmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def strtobool(val):
        """Convert a string representation of truth to true (1) or false (0).

        True values are 'y', 'yes', 't', 'true', 'on', and '1'; false values
        are 'n', 'no', 'f', 'false', 'off', and '0'.  Raises ValueError if
        'val' is anything else.
        """
        # traceback.print_stack()
        val = val.lower()
        if val in ("y", "yes", "t", "true", "on", "1"):
            return 1
        elif val in ("n", "no", "f", "false", "off", "0"):
            return 0
        else:
            raise ValueError("invalid truth value %r" % (val,))

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def loads_json(cls, _str, msg=None):
        """
        Wrapper for json.loads
        @param:
            _str: string  to convert
            msg: message to raise on failure
        """
        # traceback.print_stack()
        try:
            out = json.loads(_str)
            return out
        except Exception as e:
            msg = "Message: {}. ".format(msg) if msg else ""
            raise TestError("JSON load failed. {}Error: {}".format(msg, e))

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def read_file(cls, file_path):
        """
        Reads a .gz (gzip) or regular file and returns its content as a string
        """
        # traceback.print_stack()

        if file_path.endswith(".gz"):
            with gzip.open(file_path, "rb") as f:
                content = f.read()
        else:
            with open(file_path, "r") as f:
                content = f.read()

        return content

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def match_in_file(cls, file_path, regex_dict):
        """
        Returns a dictionary of matched values in a file.
        @param file
        @param regex_dict: a dictionary of tuples (regex expression, option)
        """
        # traceback.print_stack()
        f_str = cls.read_file(file_path)
        return cls.match_string(f_str, regex_dict)

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def match_string(cls, string, regex_dict):
        """
        Returns a dictionary of matched values in a string
        @param string
        @param regex_dict: a dictionary of tuples (regex expression, option)
        """
        # traceback.print_stack()
        retDict = {}
        for key in regex_dict.keys():
            regex, option = regex_dict[key]
            try:
                m = re.findall(regex, string)
                if option is None:
                    retDict[key] = "\n".join(m)
                elif option == "unique":
                    # Get unique items
                    m = list(set(m))
                    retDict[key] = " ".join(m)
                elif option == "groupbycount":
                    # Get count of unique items
                    unique_m = list(set(m))
                    tmp = {}
                    for i in unique_m:
                        tmp[i] = 0
                    for i in m:
                        tmp[i] += 1
                    # Generate string
                    value = ""
                    for i in tmp:
                        value += "(%sx)%s " % (tmp[i], i)
                    value = value.strip()
                    retDict[key] = value
                elif option == "count":
                    # Get count of items
                    retDict[key] = len(m)
                elif option == "countunique":
                    # Returns the number of unqiue entries
                    retDict[key] = len(set(m))
            except Exception:
                retDict[key] = None
        return retDict

    @classmethod
    # pyre-fixme[24]: Generic type `dict` expects 2 type parameters, use
    #  `typing.Dict[<key type>, <value type>]` to avoid runtime subscripting errors.
    # pyre-fixme[24]: Generic type `list` expects 1 type parameter, use
    #  `typing.List[<element type>]` to avoid runtime subscripting errors.
    def filter_dict_keys(cls, data: Dict, keys: List) -> Dict:
        """
        Created a sub dictionary from a given nested dict,
        based on the list of keys given.
        """
        # traceback.print_stack()
        data_copy = data.copy()
        for key, value in data_copy.items():
            if isinstance(value, list):
                for v in value:
                    cls.filter_dict_keys(v, keys)
            if isinstance(value, dict):
                cls.filter_dict_keys(value, keys)
            if (
                key not in keys
                and not isinstance(value, dict)
                and not isinstance(value, list)
            ):
                del data[key]
        return data

    @classmethod
    def strip_special_chars(cls, hostname: str) -> str:
        """
        This function replaces special characters (anything that is not a letter, number, .,-,_) in hostname string with '_'.
        Args:
            hostname (str): a string.

        Returns:
            str: copy of hostname string with special characters replaced.
        """
        # traceback.print_stack()
        return re.sub(r"[^a-zA-Z0-9\.\-\_]", "_", hostname)

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[24]: Generic type `dict` expects 2 type parameters, use
    #  `typing.Dict[<key type>, <value type>]` to avoid runtime subscripting errors.
    def evaluate_expression(cls, expr: str, expr_args: Optional[dict] = None):
        """Takes expression string, converts to AST
        and evaluates the ast nodes
        """
        # traceback.print_stack()
        ast_node = ast.parse(expr, mode="eval")
        try:
            value = cls.ast_expr_evaluate(ast_node, expr_args)
            if value is not None:
                return value
            raise TestError("Invalid Expression %s" % expr)
        except Exception:
            raise

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    # pyre-fixme[24]: Generic type `dict` expects 2 type parameters, use
    #  `typing.Dict[<key type>, <value type>]` to avoid runtime subscripting errors.
    def ast_expr_evaluate(cls, ast_node, expr_args: Optional[dict] = None):
        """Takes abstract syntax tree of an expression, evaluates and returns the value
        Sample tree inside an ast node for an expression 10+2*8
        'Expression(body=BinOp(left=Constant(value=10, kind=None), op=Add(), right=BinOp(left=Constant(value=2, kind=None), op=Mult(), right=Constant(value=8, kind=None))))'

        The function processes the ast nodes that are of types Expression(body), BinOp(left, op, right), and Num(n)

        The function recurses until it finds numbers in the BinOp nodes and apply the operands.
        The function understands the basic arithemetic operands


        """
        # traceback.print_stack()
        if isinstance(ast_node, ast.Name):
            if expr_args and str(ast_node.id) in expr_args:
                return expr_args[str(ast_node.id)]
            raise TestError("% is required in the expr_args" % str(ast_node.id))

        if isinstance(ast_node, ast.Expression):
            return cls.ast_expr_evaluate(ast_node.body, expr_args)
        elif isinstance(ast_node, ast.Num):
            return ast_node.n
        elif isinstance(ast_node, ast.BinOp):
            operand = ast_node.op
            left = cls.ast_expr_evaluate(ast_node.left, expr_args)
            right = cls.ast_expr_evaluate(ast_node.right, expr_args)
            if isinstance(operand, ast.Add):
                return left + right
            if isinstance(operand, ast.Sub):
                return left - right
            elif isinstance(operand, ast.Mult):
                return left * right
            elif isinstance(operand, ast.Div):
                return left / right
        else:
            return None

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    def is_float(cls, _str):
        # traceback.print_stack()
        try:
            float(_str)
            return True
        except ValueError:
            return False

    @classmethod
    def add_priority_to_cmd(cls, cmd: str, priority: int) -> str:
        # traceback.print_stack()
        return f"nice -n {priority} {cmd}"
