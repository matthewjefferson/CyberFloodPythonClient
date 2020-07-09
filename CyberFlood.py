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
    def __init__(self, username, password, controller_address, perform_commands=True, log_level="INFO", log_path=None):

        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

        arguments = locals()

        self.username = username
        self.password = password
        self.controller_address = "https://" + controller_address + "/api/v2"

        # Enabling the "Perform Commands" adds a fixed amount initialization overhead (time) for the CyberFlood API.
        self.perform_commands = perform_commands

        self.__bearerToken = None
        #self.__isLogged = False
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

        logging.basicConfig(filename=self.log_file, filemode="w", level=self.log_level, format="%(asctime)s %(message)s")

        # The logger is now ready.        
        logging.info("Executing __init__: " + str(arguments))

        # logging.basicConfig()
        # logging.getLogger().setLevel(logging.DEBUG)
        requests_log = logging.getLogger("requests.packages.urllib3")
        # requests_log.setLevel(logging.DEBUG)
        requests_log.propagate = True

        # Authenticate. This will allow all subsequent calls to use the token.
        response = self.__session.post(self.controller_address + '/token', data={'email': self.username, 'password': self.password})

        if response.status_code == 201:
            self.__bearerToken = json.loads(response.text)['token']
            self.__session.headers.update(Authorization='Bearer ' + self.__bearerToken)
            #self.__isLogged = True

        if self.perform_commands:
            # Perform Commands are enabled. We need to download the OpenAPI.yaml file and 
            # generate the class objects for each command.

            # Download the ReST API specification for the controller.
            specfilename = self.get("/documentation/openapi.yaml")
            self.api_spec = self._convert_yaml_to_dict(specfilename)
            # We don't need the openapi.yaml file after this point.
            os.remove(specfilename)

            self._generate_classes()   

        return    

    @logging_decorator
    def post(self, url, payload=None):
        result = self.exec("post", url, payload)
        return result

    @logging_decorator
    def delete(self, url, payload=None):
        result = self.exec("delete", url, payload)
        return 

    @logging_decorator
    def put(self, url, payload=None):              
        result = self.exec("put", url, payload)
        return result

    @logging_decorator
    def get(self, url, payload=None):
        result = self.exec("get", url, payload)
        return result

    @logging_decorator
    def perform(self, command_name, command_type=None, payload=None, **kwargs):        

        if not self.perform_commands:
            raise Exception("Perform Commands are not enabled. Use the perform_commands=True argument when initializing the CyberFlood client.")        

        if command_name not in self.commands.keys():
            raise Exception("The command '" + command_name + "' is not valid.")        

        command_list = list(self.commands[command_name].keys())

        if len(command_list) > 1:
            if not command_type:
                raise Exception("You must specify the type for this command.")                    
        else:            
            command_type = command_list[0]

        command = self.commands[command_name][command_type]

        result = command.perform(payload, **kwargs)            

        return result

    #def exec(self, httpverb, url, *args):        
    def exec(self, httpverb, url, payload=None, filters=None, *args):        

        url = self.controller_address + url

        # Extract any filters and add them to the URL.
        url, args = self._get_filters(url, args)

        payload = {}
        if args:
            payload = json.dumps(args[0])

        httpverb = httpverb.lower()

        if httpverb == "get":
            response = self.__session.get(url)
        elif httpverb == "post":            
            response = self.__session.post(url, data=payload, headers={'Content-Type': 'application/json'}, verify=False)
        elif httpverb == "put":
            response = self.__session.put(url, data=payload, headers={'Content-Type': 'application/json'}, verify=False)            
        elif httpverb == "delete":
            response = self.__session.delete(url)
        else:
            raise Exception("ERROR: The command '" + httpverb + "' is not valid.")

        if not response.ok:
            self._process_error(response)
        
        return_value = None

        content_disposition = response.headers.get("content-disposition")

        if response.headers.get("content-type") == "application/json":
            return_value = response.json()
        elif content_disposition and re.match("attachment", content_disposition, flags=re.I):
            # The content-disposition will look something like this:
            # attachment; filename="event.log"
            match = re.search("filename=\"(.+)\"", content_disposition, flags=re.I)            
            filename = match.group(1)
            return_value = self._save_file(response, filename)
        elif response.headers.get("content-type") == "application/octet-stream":
            # This is likely a file that needs to be downloaded.
            if url.find('/'):
                # Extract the filename from the URL.
                filename = url.rsplit('/', 1)[1]
            else:
                filename = "unknown_file"
            
            return_value = self._save_file(response, filename)
        else:
            logging.debug(str(response.headers.get))
            raise Exception("ERROR: Unknown response type (" + response.headers.get("content-type") + ").")

        return return_value

    def _save_file(self, response, filename, directory=None):        
        # Save the attached file to the current directory (or possibly a subdirectory).

        if directory:
            filename = os.path.join(directory, filename)

        filename = os.path.abspath(filename)
        path = os.path.dirname(filename)

        if not os.path.exists(path):
            os.makedirs(path) 

        file_size_dl = 0
        try:
            with open(filename, 'wb') as f:
                for buff in response.iter_content(chunk_size=16384):
                    f.write(buff)
        except Exception as e:
            raise RuntimeError("Could not download file: " + str(e))
        finally:
            response.close()

        return filename     

    def _get_filters(self, url, args):
        newurl = url

        global pp
        pp.pprint(args)

        newargs = None

        return newurl, newargs


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

                # Some command names are used by more than one object type (key).
                if command.name not in self.commands.keys():
                    self.commands[command.name] = {}

                self.commands[command.name][command.tag] = command

        return         

class CfCommand:    
    """This class is used to store
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

        return

    @logging_decorator
    def perform(self, payload=None, filters=None, **kwargs):
        path = self.resolve_path(**kwargs)

        result = self.cf.exec(self.httpverb, path, payload, filters)

        return result

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

