from requests.packages.urllib3.exceptions import InsecureRequestWarning
import requests
import json
import re
import logging
import os
import sys
import datetime
import ast
import inspect
import functools
import pickle
import yaml

import pprint
pp = pprint.PrettyPrinter(indent=2)

def logging_decorator(func):
    @functools.wraps(func)
    def wrapper_decorator(*args, **kwargs):
        logging.debug("ENTER=" + str(func) + " args=" + str(args) + " kwargs=" + str(kwargs))        

        value = func(*args, **kwargs)

        logging.debug("LEAVE=" + str(func) + " returns=" + str(value))

        return value
    return wrapper_decorator 

class CyberFlood:    
    def __init__(self, userName, userPassword, controllerAddress, loglevel="INFO", logpath=None):

        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

        arguments = locals()

        self.userName = userName
        self.userPassword = userPassword
        self.controllerAddress = "https://" + controllerAddress + "/api/v2"
        self.__bearerToken = None
        self.__isLogged = False
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
        self.logpath = os.getenv("CF_LOG_OUTPUT_DIRECTORY", defaultlogpath)

        # The logpath argument will override everything.
        if logpath:
            self.logpath = logpath

        self.logpath = os.path.abspath(self.logpath)
        self.logfile = os.path.join(self.logpath, "cf_restapi.log")        

        if not os.path.exists(self.logpath):
            os.makedirs(self.logpath)

        if loglevel.upper() == "ERROR":
            self.loglevel = logging.ERROR
        elif loglevel.upper() == "WARNING":
            self.loglevel = logging.WARNING
        elif loglevel.upper() == "INFO":
            self.loglevel = logging.INFO
        elif loglevel.upper() == "DEBUG":
            self.loglevel = logging.DEBUG
        else:
            self.loglevel = logging.INFO

        logging.basicConfig(filename=self.logfile, filemode="w", level=self.loglevel, format="%(asctime)s %(message)s")

        # The logger is now ready.        

        #print("DEBUG: Using PPRINT")
        #self.pp = pprint.PrettyPrinter(indent=2)

        logging.info("Executing __init__: " + str(arguments))

        # logging.basicConfig()
        # logging.getLogger().setLevel(logging.DEBUG)
        requests_log = logging.getLogger("requests.packages.urllib3")
        # requests_log.setLevel(logging.DEBUG)
        requests_log.propagate = True

        # Authenticate.
        response = self.__session.post(self.controllerAddress + '/token',
                                       data={'email': self.userName,
                                             'password': self.userPassword})

        if response.status_code == 201:
            self.__bearerToken = json.loads(response.text)['token']
            self.__session.headers.update(Authorization='Bearer ' + self.__bearerToken)
            self.__isLogged = True

        # Download the ReST API specification.
        specfilename = self.download_file("/documentation/openapi.yaml", save_path=self.logpath)
        self.api_spec = self._convert_yaml_to_dict(specfilename)
        os. remove(specfilename)

        self._generate_classes()            

        return    

    @logging_decorator
    def post(self, url, payload=None):
        result = self.command("post", url, payload)
        return result.json()

    @logging_decorator
    def delete(self, url, payload=None):
        result = self.command("delete", url, payload)
        return 

    @logging_decorator
    def put(self, url, payload=None):              
        result = self.command("put", url, payload)
        return result.json()

    @logging_decorator
    def get(self, url, payload=None):
        result = self.command("get", url, payload)
        return result.json()

    @logging_decorator
    def exec(self, command_name, payload=None, **kwargs):

        command = self.commands.get(command_name, None)

        if not command:
            raise Exception("The command '" + command_name + "' is not valid.")        

        result = command.exec(payload, **kwargs)            

        return result

    def command(self, action, url, *args):

        url = self.controllerAddress + url

        payload = {}
        if args:
            payload = json.dumps(args[0])

        action = action.lower()
        if action == "get":
            response = self.__session.get(url)
        elif action == "post":            
            response = self.__session.post(url, data=payload, headers={'Content-Type': 'application/json'}, verify=False)
        elif action == "put":
            response = self.__session.put(url, data=payload, headers={'Content-Type': 'application/json'}, verify=False)            
        elif action == "delete":
            response = self.__session.delete(url)
        else:
            raise Exception("ERROR: The command '" + action + "' is not valid.")

        if not response.ok:
            self._process_error(response)

        return response 

    def download_file(self, source, save_path=None):
        """Download a file.

        If a timeout defined, it is not a time limit on the entire download;
        rather, an exception is raised if the server has not issued a response
        for timeout seconds (more precisely, if no bytes have been received on
        the underlying socket for timeout seconds). If no timeout is specified
        explicitly, requests do not time out.

        """
        url = self.controllerAddress + source

        try:
            response = self.__session.get(url, stream=True, verify=False, timeout=10)

            # print(rsp.request.headers)
            # print(rsp.headers)
        except requests.exceptions.ConnectionError as e:
            raise Exception("Connection error during download.")

        if response.status_code >= 300:
            self._process_error(response)

        if os.path.isabs(source):
            # The source needs to be a relative path.
            source = "." + source

        save_file = os.path.abspath(os.path.join(save_path, source))
        os.makedirs(os.path.dirname(save_file))

        file_size_dl = 0
        try:
            with open(save_file, 'wb') as f:
                for buff in response.iter_content(chunk_size=16384):
                    f.write(buff)
        except Exception as e:
            raise RuntimeError("Could not download file: " + str(e))
        finally:
            response.close()

        return save_file


    def _process_error(self, response):
        if response.text != "":

            # The error details should be a dictionary.
            errordetails = ast.literal_eval(response.text)
            # {"type":"validation",
            #  "message":"Validation failed, config subnets client vlans id must be an integer",
            #  "errors":{"config":{"subnets":{"client":{"1":{"vlans":{"0":{"id":["must be an integer","must be greater than or equal to 0","must be less than or equal to 4094"]}}}}}}}}

            errmsg = errordetails.get("message", "No message")        

            additionaldetails = errordetails.get("errors", None)
            if additionaldetails:
                errmsg += "\n" + str(additionaldetails)
        else:
            errmsg = "An unspecified error occurred (" + response.status_code + ")"
        
        logging.error(errmsg)
        raise Exception(errmsg)

    def _convert_yaml_to_dict(self, inputfilename):        

        # Open and read the YAML input file.
        yamldict = {}

        try:
            with open(inputfilename, "r", encoding="utf-8") as yaml_file:
                yamldict = yaml.load(yaml_file)
        except yaml.YAMLError as exc:
            if hasattr(exc, 'problem_mark'):
                mark = exc.problem_mark
                print("Error position: (%s:%s)" % (mark.line+1, mark.column+1))
            else:
                errmsg = "Unexpected error while parsing the YAML:", sys.exc_info()[1]
                logging.error(errmsg)
                raise Exception(errmsg)

        return yamldict

    def _generate_classes(self):        
        self.commands = {}

        for path in self.api_spec["paths"].keys():
            for verb in self.api_spec["paths"][path].keys():
                command = CfCommand(self, path, verb, self.api_spec["paths"][path][verb])

                self.commands[command.name] = command

        return         

class CfCommand:    
    """This class is used to store
    """
    def __init__(self, cyberfloodobject, path, httpverb, definition):
        self.cf = cyberfloodobject
        self.path = path
        self.httpverb = httpverb
        self.definition = definition

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

        return

    @logging_decorator
    def exec(self, payload=None, **kwargs):
        path = self.resolve_path(**kwargs)

        result = self.cf.command(self.httpverb, path, payload)

        return result.json()        

    def resolve_path(self, **kwargs):
        """Generate the command path by replacing the parameter "placeholders" names with 
        the user-specified values for each parameter.
        e.g. path = '/tests/{testId}/results/{testResultId}'
             returns = '/tests/lkj43lkjfi34flklksflkji43jlfrl2/results/b5fb4a9e322c4333805aa9e13c433f85'
        """

        path = self.path
        for key in kwargs.keys():
            path = re.sub("{" + key + "}", kwargs[key], path)        

        return path

