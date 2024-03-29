from __future__ import absolute_import, division, print_function, unicode_literals
# This may help with Python 2/3 compatibility.

# The next line is intentionally blank.

__author__ = "Matthew Jefferson"
__version__ = "1.4.3"

# The previous line is intentionally blank.

"""
     Spirent CyberFlood Python Client
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    This module provides a Python front-end for the CyberFlood ReST API.
    There are two, non-exclusive ways to execute commands: HTTP verbs and Perform Commands.
    The supported HTTP verbs are "post", "put", "get" and "delete". The syntax for these commands
    matches the API documentation exactly.
    Perform Commands use the "perform" method, and are also listed in the API documentation.
    These include commands such as "listHttpConnectionsPerSecondTests", "listTests" and "startTest".
    Perform Commands are built from an OpenAPI.yaml file downloaded from the controller during instantiation.
    These commands can be turned off, saving some start-up time. All functionality can still be accessed
    via the HTTP verb methods.

    Command Examples:
        1. List all tests:
            # HTTP Verb Method
            cf.get("/tests")

            # Perform Method
            cf.perform("listTests")

        2. List the tests named "Matt Test":
            # HTTP Verb Method
            cf.get("/tests?filter[name]=Matt Test")

            # Perform Method
            cf.perform("listTests", filters={"name": "Matt Test"})

        3. Change the duration of the LoadSpec for an EMix test:
            # HTTP Verb Method #1
            cf.put("/tests/emix/" + testid, config={'loadSpecification': {'duration': 500}})
            # HTTP Verb Method #2
            cf.put("/tests/emix/" + testid, {"config": {'loadSpecification': {'duration': 600}}})

            # Perform Method #1
            cf.perform("updateEmixTest", testId=testid, config={'loadSpecification': {'duration': 700}})
            # Perform Method #2
            cf.perform("updateEmixTest", {"config": {'loadSpecification': {'duration': 800}}}, testId=testid)

        4. Get all Test Run Results:
            # HTTP Verb Method
            cf.get("/test_runs/" + testrun["id"] + "/results/")

            # Perform Method (Notice that we need to specify the "command_type" argument)
            cf.perform("listTestRuns", command_type="Test Runs")

        5. Get a Test Run Result:
            # HTTP Verb Method
            cf.get("/test_runs/" + testrun["id"] + "/results/" + testrunresults["id"])

            # Perform Method
            cf.perform("getTestRunResult", testRunId=testrun["id"], testRunResultsId=testrunresults["id"])

    Modification History:
    1.4.3 : 01/18/2023 - Matthew Jefferson
        -Now raising an exception if the user authorization fails. It was failing silently before.

    1.4.2 : 09/15/2022 - Matthew Jefferson
        -Reworked the use_yaml_cache option. It now works much better than before.

    1.4.1 : 09/12/2022 - Matthew Jefferson
        -Added the CyberFlood Class variable "object_types". This dictionary contains a list of all
         CyberFlood object types (e.g. "Subnet", "Traffic Mixes", etc), and their corresponding perform commands.
         This is only applicable when perform commands are enabled.

    1.4.0 : 08/15/2022 - Matthew Jefferson
        -Added the use_yaml_cache flag when initializing the CyberFlood class. This allow you to
         explicitly specify if you want to download the OpenApi.yaml file, or just use a cached copy.

    1.3.0 : 06/08/2022 - Matthew Jefferson
        -Added support for importing test cases with the "createTestImport" command.
         Use the "upload_filename" argument for the archive.
         e.g. cf.perform("createTestImport", type="avn", upload_filename="test.zip")

    1.2.1 : 02/10/2022 - Matthew Jefferson
        -Fixed a exception that triggered when deleting anything.

    1.2.0 : 05/17/2021 - Matthew Jefferson
        -You can now specify multi-key filters with a "dash" delimiter.
         e.g. "duration-lt" translates to "filter[duration][lt]".

    1.1.2 : 05/04/2021 - Matthew Jefferson
        -Now able to download the openapi.yaml file again. Just using a new URL.

    1.1.1 : 07/28/2020 - Matthew Jefferson
        -Using safe_load() for YAML. The old load() method has been depricated.

    1.1.0 : 07/28/2020 - Matthew Jefferson
        -CyberFlood version 20.4.3829 appears to break the dynamic download of the openapi.yaml file.
         I've resolved this by allowing the user to download the file on their own and save it in the same
         directory as the CyberFlood.py file.
         To download the openapi.yaml file:
            1. Go to the CyberFlood GUI
            2. Click on the ? at the top-right
            3. Select "RESTful API Help"
            4. Click on "Download OpenAPI specification: Download" and save the file in the
               same directory as CyberFlood.py

    1.0.0 : 07/16/2020 - Matthew Jefferson
        -The code should be stable enough for release.

    0.0.1 : 07/10/2020 - Matthew Jefferson
        -The initial code.

    :copyright: (c) 2020 by Matthew Jefferson.
"""

import os
import sys
import json
import re
import logging
import datetime
# Required for processing error messages from the ReST API.
import ast
#  import inspect
import functools
# Copy is require for the deepcopy function.
import copy
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import requests


# pickle and yaml are required for processing the OpenAPI yaml file.
#  import pickle
#  import pylibyaml
import yaml

LOGGER = logging.getLogger(__name__)


# =============================================================================
def logging_decorator(func):
    """This decorator is used to populate the logs with the Python client commands as they are executed.
    """
    @functools.wraps(func)
    def wrapper_decorator(*args, **kwargs):
        LOGGER.debug("ENTER=%s args=%s kwargs=%s", str(func), str(args),
                     str(kwargs))

        value = func(*args, **kwargs)

        LOGGER.debug("LEAVE=%s returns=%s", str(func), str(value))

        return value
    return wrapper_decorator


# Copyright Ferry Boender, released under the MIT license.
def deepupdate(target, src):
    """Deep update target dict with src
    For each k,v in src: if k doesn't exist in target, it is deep copied from
    src to target. Otherwise, if v is a list, target[k] is extended with
    src[k]. If v is a set, target[k] is updated with v, If v is a dict,
    recursively deep-update it.

    Examples:
    >>> t = {'name': 'Ferry', 'hobbies': ['programming', 'sci-fi']}
    >>> deepupdate(t, {'hobbies': ['gaming']})
    >>> print t
    {'name': 'Ferry', 'hobbies': ['programming', 'sci-fi', 'gaming']}
    """
    for k, v in src.items():
        if isinstance(v, list):
            if k not in target:
                target[k] = copy.deepcopy(v)
            else:
                target[k].extend(v)
        elif isinstance(v, dict):
            if k not in target:
                target[k] = copy.deepcopy(v)
            else:
                deepupdate(target[k], v)
        elif isinstance(v, set):
            if k not in target:
                target[k] = v.copy()
            else:
                target[k].update(v.copy())
        else:
            target[k] = copy.copy(v)


# =============================================================================
class CyberFlood:
    def __init__(self, username, password, controller_address, perform_commands=True, use_yaml_cache=True, log_level="INFO", log_path=None):

        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

        arguments = locals()

        self.username = username
        self.password = password
        self.controller_address = "https://" + controller_address + "/api/v2"

        # Enabling the "Perform Commands" adds a fixed amount initialization overhead (time) for the CyberFlood API.
        self.perform_commands = perform_commands

        # This dictionary contains an entry for each perform command, if "perform_commands" is True.
        self.commands = {}
        # This dictionary contains an entry for each CyberFlood object type, and a list of each command that can be used with that object.
        self.object_types = {}

        self.__bearerToken = None
        #  self.__isLogged = False
        self.__session = requests.session()
        self.__session.verify = False

        defaultlogpath = os.path.join(os.getcwd(), "logs")

        now = datetime.datetime.now()
        tempdir = now.strftime("%Y-%m-%d-%H-%M-%S")
        tempdir += "_PID"
        tempdir += str(os.getpid())
        defaultlogpath = os.path.join(defaultlogpath, tempdir)
        defaultlogpath = os.path.expanduser(defaultlogpath)

        # The STC_LOG_OUTPUT_DIRECTORY will override the default path.
        self.log_path = os.getenv("CF_LOG_OUTPUT_DIRECTORY", defaultlogpath)

        # The log_path argument will override everything.
        if log_path:
            self.log_path = log_path

        self.log_path = os.path.abspath(self.log_path)
        self.log_file = os.path.join(self.log_path, "cf_restapi.log")

        if not os.path.exists(self.log_path):
            os.makedirs(self.log_path)

        if log_level.upper() == "ERROR":
            self.log_level = logging.ERROR
        elif log_level.upper() == "WARNING":
            self.log_level = logging.WARNING
        elif log_level.upper() == "INFO":
            self.log_level = logging.INFO
        elif log_level.upper() == "DEBUG":
            self.log_level = logging.DEBUG
        else:
            self.log_level = logging.INFO

        ##
        # Create stream and file logger assuming this class will be treated
        # as a singleton.
        #
        # log to stream
        LOGGER.setLevel(self.log_level)
        formatter = logging.Formatter("%(asctime)s %(message)s")

        stream_logger = logging.StreamHandler()
        stream_logger.setLevel(self.log_level)
        stream_logger.setFormatter(formatter)
        LOGGER.addHandler(stream_logger)

        # log to file
        file_logger = logging.FileHandler(self.log_file, mode="w")
        file_logger.setLevel(self.log_level)
        file_logger.setFormatter(formatter)
        LOGGER.addHandler(file_logger)
        ##

        # The logger is now ready.
        LOGGER.info("Executing __init__: %s", str(arguments))

        requests_log = logging.getLogger("requests.packages.urllib3")
        requests_log.propagate = True

        # Authenticate. This will allow all subsequent calls to use the token.
        response = self.__session.post(self.controller_address + '/token', data={'email': self.username, 'password': self.password})

        if response.status_code == 201:
            self.__bearerToken = json.loads(response.text)['token']
            self.__session.headers.update(Authorization='Bearer ' + self.__bearerToken)
        else:
            errmsg = "Authorization failed. Please check user credentials."
            LOGGER.error(errmsg)
            raise Exception(errmsg)

        if self.perform_commands:
            # Perform Commands are enabled. We need to download the OpenAPI.yaml file and
            # generate the class objects for each command.
            self._enable_perform_commands(use_cached_commands=use_yaml_cache)

    @logging_decorator
    def post(self, url, *args, **kwargs):
        result = self.exec("post", url, *args, **kwargs)
        return result

    @logging_decorator
    def delete(self, url, *args, **kwargs):
        result = self.exec("delete", url, *args, **kwargs)
        return result

    @logging_decorator
    def put(self, url, *args, **kwargs):
        result = self.exec("put", url, *args, **kwargs)
        return result

    @logging_decorator
    def get(self, url, *args, **kwargs):
        result = self.exec("get", url, *args, **kwargs)
        return result

    @logging_decorator
    def perform(self, command_name, *args, command_type=None, **kwargs):
        """This method is used to execute "Perform Commands". These are the commands that are listed
        in the CyberFlood API documentation. This method uses the CfCommand objects.
        e.g.
            getEmixTest
            listTests
            listTestRunResults
        """
        if not self.perform_commands:
            raise Exception("Perform Commands are not enabled. Use the perform_commands=True argument when initializing the CyberFlood client.")

        # Determine which command is being invoked.
        if command_name not in self.commands.keys():
            raise Exception("The command '" + command_name + "' is not valid.")

        command_list = list(self.commands[command_name].keys())

        if len(command_list) > 1:
            # There is more than one command with this command_name. The user must specify the command_type.
            if not command_type:
                raise Exception("You must specify the type for this command.")
        else:
            command_type = command_list[0]

        command = self.commands[command_name][command_type]

        result = command.perform(*args, **kwargs)

        return result

    def exec(self, httpverb, url, *args, filters=None, upload_filename=None, **kwargs):
        """Send the specified HTTP request to the CyberFlood ReST API.
        The filter argument is special. It is a dictionary of filters that must be added to the URL.

        Use the "upload_filename" argument to upload files to the server.
        """

        # Construct the complete URL.
        url = self.controller_address + url
        url += self._add_filters(filters)

        # Construct the json_payload, which can be a combination of args and kwargs.
        payload = {}
        json_payload = {}

        if args:
            # Only one positional arg is supported, and it must be a dictionary.
            payload = args[0]

        # Merge the kwargs into the payload dictionary.
        deepupdate(payload, kwargs)

        if len(list(payload.keys())) > 0:
            json_payload = json.dumps(payload)

        httpverb = httpverb.lower()

        if upload_filename:
            filedata = open(upload_filename, "rb")
            filejson = {"file": filedata}
            response = self.__session.post(url, files=filejson, data=payload, verify=False)

        elif httpverb == "get":
            response = self.__session.get(url, data=json_payload, headers={'Content-Type': 'application/json'}, verify=False)
        elif httpverb == "post":
            response = self.__session.post(url, data=json_payload, headers={'Content-Type': 'application/json'}, verify=False)
        elif httpverb == "put":
            response = self.__session.put(url, data=json_payload, headers={'Content-Type': 'application/json'}, verify=False)
        elif httpverb == "delete":
            response = self.__session.delete(url)
        else:
            raise Exception("ERROR: The command '" + httpverb + "' is not valid.")

        if not response.ok:
            self._process_error(response)

        return_value = None

        # print("HERE")
        # import pprint
        # pp = pprint.PrettyPrinter(indent=2)
        # # pp.pprint(response.url)
        # pp.pprint(response.status_code)
        # # pp.pprint(response.encoding)
        # pp.pprint(response.headers)
        # pp.pprint(response)
        # pp.pprint("Content=")
        # print(response.content)

        # print("======")
        # print("Text:")
        # print(response.text)

        # Process the response.
        content_disposition = response.headers.get("content-disposition")

        if response.status_code == 204:
            # This happens with DELETE.
            return_value = None
        elif response.headers.get("content-type") == "application/json":
            return_value = response.json()
        elif content_disposition and re.match("attachment", content_disposition, flags=re.I):
            # The response contained an attachment.
            # The content-disposition will look something like this: attachment; filename="event.log"
            match = re.search("filename=\"(.+)\"", content_disposition, flags=re.I)
            filename = match.group(1)
            return_value = self._save_file(response, filename)
        elif response.headers.get("content-type") == "application/octet-stream":
            # This is probably a file as well. The last part of the URL should be the filename.
            # e.g. "https://1.1.1.1/api/v2/documentation/openapi.yaml"
            if url.find('/'):
                # Extract the filename from the URL.
                filename = url.rsplit('/', 1)[1]
            else:
                filename = "unknown_file"

            return_value = self._save_file(response, filename)
        else:
            # Whoops...looks like we got a response that wasn't anticipated.
            LOGGER.debug(str(response.headers.get))
            raise Exception("ERROR: Unknown response type (" + str(response.headers.get("content-type")) + ").")

        return return_value

    def _save_file(self, response, filename, directory=None):
        """ Save a file attachment from a response to the current directory (or possibly a subdirectory).
        """

        if directory:
            filename = os.path.join(directory, filename)

        filename = os.path.abspath(filename)
        path = os.path.dirname(filename)

        if not os.path.exists(path):
            os.makedirs(path)

        try:
            with open(filename, 'wb') as f:
                for buff in response.iter_content(chunk_size=16384):
                    f.write(buff)
        except Exception as e:
            raise RuntimeError("Could not download file: " + str(e))
        finally:
            response.close()

        return filename

    def _add_filters(self, filters):
        """Convert any filters, specified as a dictionary by the user, into a string for a URL.
        """
        filtersurl = ""
        if filters:
            # The user may specify a multi-key filter with a "dash" delimiter.
            # e.g. duration-lt translates to filter[duration][lt].

            for key in filters.keys():
                if filtersurl != "":
                    filtersurl += "&"

                filtersurl += "filter"
                for subfilter in key.split("-"):
                    filtersurl += "[" + subfilter + "]"

                #  value = requests.utils.quote(filters[key])
                value = filters[key]
                filtersurl += "=" + str(value)

            filtersurl = "?" + filtersurl

        return filtersurl

    def _process_error(self, response):
        """Handle error responses from the CyberFlood ReST API.
        """
        if response.text != "":
            # The error details should be a dictionary.
            # e.g.
            # {"type":"validation",
            #  "message":"Validation failed, config subnets client vlans id must be an integer",
            #  "errors":{"config":{"subnets":{"client":{"1":{"vlans":{"0":{"id":["must be an integer","must be greater than or equal to 0","must be less than or equal to 4094"]}}}}}}}}
            errordetails = ast.literal_eval(response.text)
            errmsg = errordetails.get("message", "No message")

            additionaldetails = errordetails.get("errors", None)
            if additionaldetails:
                errmsg += "\n" + str(additionaldetails)
        else:
            errmsg = "An unspecified error occurred (" + str(response.status_code) + ")"

        LOGGER.error(errmsg)
        raise Exception(errmsg)

    def _enable_perform_commands(self, use_cached_commands):
        """Generate CyberFlood "Perform" command classes, based on the OpenAPI.yaml spec.
           There is an option to use the "cached" version of these commands, because parsing the YAML
           file is pretty slow.
           When caching is enabled, the dictionary that is generated from the OpenAPI.yaml file is saved
           to disk as a JSON file.
        """

        path = os.path.dirname(__file__)
        path = os.path.abspath(path)

        # Only use the cached commands if they match CyberFlood controller version.
        controller = self.get("/system/version")
        # "version": "22.4.1030"

        cached_commands_filename = os.path.join(path, "perform_commands_cache_" + controller["version"] + ".json")
        cached_commands_filename = os.path.abspath(cached_commands_filename)

        api_spec = None
        if use_cached_commands:
            LOGGER.info("Attempting to use the cached OpenAPI.yaml file....")

            if os.path.isfile(cached_commands_filename):
                # Okay, the file exists, so load the cached api_spec dictionary.
                with open(cached_commands_filename) as f:
                    api_spec = json.load(f)
            else:
                # The cached commands were not found. This means we'll need to attempt to download the OpenAPI.yaml file.
                errmsg = "Unable to locate the cached commands file: " + cached_commands_filename
                LOGGER.warning(errmsg)

        if not api_spec:
            # Download the OpenAPI.yaml file.
            try:
                # Download the ReST API specification for the controller.
                # specfilename = self.get("/documentation/openapi.yaml")
                spec_filename = self.get("/client/openapi.yaml")

            except Exception as e:
                raise Exception("Unable to download the OpenAPI.yaml file from the controller. This file is required for 'perform' commands.\n" + str(e))

            if os.path.isfile(spec_filename):
                # print("DEBUG ONLY!!!!!!")
                # print("Start=", datetime.datetime.now().strftime("%H:%M:%S"))
                api_spec = self._convert_yaml_to_dict(spec_filename)
                # print("Generate=", datetime.datetime.now().strftime("%H:%M:%S"))

                if use_cached_commands:
                    # NOTE: I'm a bit torn here. I could always save the cached commands to disk, but that might be
                    #       a problem for logistics. Instead, I'm only saving it to disk if the user is using cached commands.
                    with open(cached_commands_filename, 'w') as f:
                        json.dump(api_spec, f)
            else:
                errmsg = "Unable to locate the OpenAPI.yaml file " + spec_filename + ". This file is required for 'perform' commands."
                LOGGER.error(errmsg)
                raise Exception(errmsg)

        if api_spec:
            self._generate_classes(api_spec)
        else:
            errmsg = "Unable to obtain the CyberFlood API specification. Try disabling perform_commands."
            LOGGER.error(errmsg)
            raise Exception(errmsg)

    def _convert_yaml_to_dict(self, inputfilename):
        """Open and convert the OpenAPI.yaml file to a Python dictionary.
        """
        yamldict = {}

        try:
            with open(inputfilename, "r", encoding="utf-8") as yaml_file:
                # The load() method has be deprecated.
                # yamldict = load(yaml_file, Loader=Loader)

                # NOTE: If you are unsatisfied with the speed of this method, consider using the LibYAML parser instead.
                #       The code here doesn't change. You just need to import the LibYAML parser instead.
                #       The trick is that you'll likely need to download and build from source. I don't think pip will work.
                #       https://pypi.org/project/pylibyaml/
                yamldict = yaml.safe_load(yaml_file)

        except yaml.YAMLError as exc:
            if hasattr(exc, 'problem_mark'):
                mark = exc.problem_mark
                print("Error position: (%s:%s)" % (mark.line + 1, mark.column + 1))
            else:
                errmsg = "Unexpected error while parsing the YAML:", sys.exc_info()[1]
                LOGGER.error(errmsg)
                raise Exception(errmsg)

        return yamldict

    def _generate_classes(self, api_spec):
        """The method instantiates the perform commands, based on the OpenAPI.yaml file from the controller.
        """
        self.commands = {}

        # Keep track of the commands available for each object type.
        # e.g. 'Subnets': { 'createIpv4Subnet': <CyberFlood.CfCommand object at 0x103659250>,
        #                   'createIpv6Subnet': <CyberFlood.CfCommand object at 0x103659190>,
        #                   'deleteIpv4Subnet': <CyberFlood.CfCommand object at 0x103659370>,
        #                   'deleteIpv6Subnet': <CyberFlood.CfCommand object at 0x1036591f0>,
        #                   'getIpv4Subnet': <CyberFlood.CfCommand object at 0x103659130>,
        #                   'getIpv6Subnet': <CyberFlood.CfCommand object at 0x103659430>,
        #                   'ipV4Replicate': <CyberFlood.CfCommand object at 0x103659340>,
        #                   'listIpv4Subnets': <CyberFlood.CfCommand object at 0x1036592b0>,
        #                   'listIpv6Subnets': <CyberFlood.CfCommand object at 0x103659670>,
        #                   'updateIpv4Subnet': <CyberFlood.CfCommand object at 0x103659100>,
        #                   'updateIpv6Subnet': <CyberFlood.CfCommand object at 0x1036593d0>},
        self.object_types = {}

        for path in api_spec["paths"].keys():
            for verb in api_spec["paths"][path].keys():
                command = CfCommand(self, path, verb, api_spec["paths"][path][verb])

                # Some command names are used by more than one object type (key).
                if command.name not in self.commands.keys():
                    self.commands[command.name] = {}

                self.commands[command.name][command.tag] = command

                if command.tag not in self.object_types:
                    self.object_types[command.tag] = {}

                self.object_types[command.tag][command.name] = command


# =============================================================================
class CfCommand:
    """This class defines each of the perform commands for CyberFlood.
    A perform command is an command that is used with the perform method.
    e.g.
        getEmixTest
        listTests
        listTestRunResults

    These commands are grouped by type (tag), such as "HTTP Throughput Tests", "Devices" and "Subnets".
    Some commands are found in more than one group, requiring the type also be specified with the command.
    """
    def __init__(self, cyberfloodobject, path, httpverb, definition):
        self.cf = cyberfloodobject
        self.path = path
        self.httpverb = httpverb
        self.definition = definition

        # The "tags" differentiate the various commands with the same name:
        # e.g. There is a "reboot" command for the "System" and "Devices".
        #      /system/reboot
        #      /devices/{deviceId}/reboot
        self.tag = definition["tags"][0]

        self.name = definition["operationId"]

        self.path_parameters = []
        self.query_parameters = []
        self.header_parameters = []
        for parameter in definition.get("parameters", []):
            if parameter["in"] == "path":
                self.path_parameters.append(parameter["name"])
            elif parameter["in"] == "query":
                self.query_parameters.append(parameter["name"])
            elif parameter["in"] == "header":
                self.header_parameters.append(parameter["name"])
            else:
                print("Unknown parameter in=" + parameter["in"])

    @logging_decorator
    def perform(self, *args, **kwargs):
        # Generate the resolvedpath by replacing the path argument names with
        # the user-specified values for each argument.
        # All arguments found in the path are required.
        # e.g. path = '/tests/{testId}/results/{testResultId}'
        #     returns = '/tests/lkj43lkjfi34flklksflkji43jlfrl2/results/b5fb4a9e322c4333805aa9e13c433f85'
        resolvedpath = self.path
        for arg in re.findall("{.+?}", self.path):
            # remove the brackets for the arg to find the dictionary key.
            key = re.sub("[{}]", "", arg)
            if key not in kwargs.keys():
                raise Exception("The argument '" + key + "' is required for the command " + self.name + " (" + self.tag + ").")

            resolvedpath = re.sub(arg, kwargs[key], resolvedpath)

            # Remove this key, so that it doesn't get added to the HTTP payload.
            kwargs.pop(key)

        result = self.cf.exec(self.httpverb, resolvedpath, *args, **kwargs)

        return result
