from __future__ import absolute_import, division, print_function, unicode_literals
# This may help with Python 2/3 compatibility.

# The next line is intentionally blank.

__author__ = "Matthew Jefferson"
__version__ = "0.0.1"

# The previous line is intentionally blank.

"""
    CyberFlood Throughput with Mixed Traffic Example from Scratch              
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    This is an example of how to create a CyberFlood Throughput with
    mixed traffic test from scratch using the CyberFlood Python client.

    Modification History:
    0.0.1 : 08/15/2022 - Matthew Jefferson
              The initial code.
    

    :copyright: (c) 2022 by Matthew Jefferson.
"""

import sys
import time
import CyberFlood
import pprint


#=============================================================================
# Functions
#=============================================================================
def run_test(test):

    testrun = None

    if test and test["id"]:         
        
        print("Starting Test '" + test["name"] + "'' (" + test["type"] + ")...")                

        #testrun = cf.put("/tests/" + test["id"] + "/start")
        #testrun = cf.exec("startTest", testId=test["id"])
        testrun = cf.perform("startTest", testId=test["id"])

        time.sleep(1)

        testrunid = testrun.get("id", None)
        
        if testrunid:
            # Wait for the test to finish.
            stop = False
            currentsubstatus = ""
            while not stop:
                #testrun = cf.get("/test_runs/" + testrunid)
                #testrun = cf.exec("getTestRun", testRunId=testrunid)
                testrun = cf.perform("getTestRun", testRunId=testrunid)

                # pp.pprint(testrun)

                stop = True
                status = testrun.get("status", None)

                if status == "running" or status == "waiting":
                    substatus = testrun.get("subStatus", "")

                    if substatus == "":
                        # It's annoying that the substatus goes away when the test is actually running.
                        if status == "running":                            
                            substatus = "running"
                        else:
                            substatus = "waiting"

                    if substatus != currentsubstatus:
                        # Update the current status.
                        currentsubstatus = substatus
                        print(currentsubstatus)

                    if currentsubstatus == "running":
                        timeremaining = testrun.get("timeRemaining", "N/A")

                        print(str(timeremaining) + " seconds remaining...")

                    stop = False

                    if currentsubstatus == "running":
                        time.sleep(4)
                    else:
                        time.sleep(1)

    return testrun

def get_results(testrun):
    # Return a dictionary containing the results for the given testrun.
    results = {}

    testrunid = testrun.get("id", None)

    if testrunid:
        #resultlist = cf.get("/test_runs/" + testrunid + "/results")
        #resultlist = cf.exec("listTestRunResults/", testRunId=testrunid)
        resultlist = cf.perform("listTestRunResults", testRunId=testrunid)
        for result in resultlist:
            # I'm assuming that there is only one result per test run.
            results = result
            break

    return results

def get_all_test_results(testid):
    # Same as the get_results function, but returns a list of results
    # for a given Test ID.
    results = []

    if testid:
        # First, you need to find the test run.
        #results = cf.get("/tests/" + testid + "/results")        
        #results = cf.exec("listTestResults", testId=testid)        
        results = cf.perform("listTestResults", testId=testid)        

    return results    

def get_profile_id(name):

    profile_id = None
    for profile in cf.perform("listAppProfiles", filters={"name": name}):
        profile_id = profile['id']
        
    return profile_id

def add_protocol_to_traffic_mix(config, protocol_name, percentage): 
    # Add (or modify) a built-in traffic protocol to the traffic mix.

    # Find the specified protocol.    
    found = False
    for protocol in cf.perform("trafficMixesDefaults"):
        if protocol['name'] == protocol_name:

            mix_entry = {}
            mix_entry['name'] = protocol['name']
            mix_entry['config'] = protocol['config']
            mix_entry['percentage'] = percentage
            mix_entry['type'] = protocol['type']

            # Determine if this protocol is already in the mix.
            not_found = True
            for entry in config['config']["trafficMix"]['mixer']:
                if entry['name'] == mix_entry['name']:
                    entry['config'] = mix_entry['config']
                    entry['percentage'] = mix_entry['percentage']

                    not_found = False
                    break

            if not_found:
                config['config']["trafficMix"]['mixer'].append(mix_entry)            

            found = True

    if not found:
        raise Exception("The protocol '" + protocol_name + "' is not valid.")

    return config

def add_profile_to_traffic_mix(config, profile_name, percentage):
    # Add (or modify) a traffic profile to the traffic mix.

    mix_entry = {}
    mix_entry['name'] = profile_name
    mix_entry['percentage'] = percentage
    mix_entry['type'] = "profile"

    # Determine if this protocol is already in the mix.
    not_found = True
    for entry in config['config']["trafficMix"]['mixer']:
        if entry['name'] == mix_entry['name']:
            entry['percentage'] = mix_entry['percentage']
            not_found = False
            break

    if not_found:
        config['config']["trafficMix"]['mixer'].append(mix_entry)                  
 
    return config

def get_subnet_id(config, side, subnet_name):

    subnet_id = None
    for subnet in config['config']['subnets'][side]:
        subnet_id = subnet['id']
        break

    return subnet_id

def map_subnet_to_interface(config, side, subnet_name, location):

    subnet_id = get_subnet_id(config, side, subnet_name)

    if side not in config['config']['interfaces']:
        config['config']['interfaces'][side] = []

    # You can have more than one subnet per interface.
    interface_already_added = False
    for interface in config['config']['interfaces'][side]:
        if interface['portSystemId'] == location:
            interface_already_added = True

            # Only add the subnet if it's not already in the list.
            if subnet_id not in interface['subnetIds']:
                interface['subnetIds'].append(subnet_id)
            break

    if not interface_already_added:
        mapping = {'portSystemId': location, 'subnetIds': [subnet_id]}

        config['config']['interfaces'][side].append(mapping)

    return config

def get_port_id(location):
    # Return the ID for the specified port location (e.g. 10.140.99.10/1/2).

    port_id = None
    for device in cf.perform("listDevices"):
        deviceinfo = cf.perform("getDevice", deviceId=device['id'])

        for slot in deviceinfo['slots']:
            for cg in slot['computeGroups']:
                for port in cg['ports']:
                    if port['systemId'] == location:
                        port_id = port['id']
                        break

    return port_id

def reserve_ports(config, queue_name="Temp-Automation-Queue"):
    # Ports must be added to a queue before the test can be run.
    # If the ports already belong to a queue, then just determine the queue name and add it to the config.
    # If the ports are not part of a queue, create the queue and add the ports.

    # The port locations should already be part of the configuration.
    # If not, use map_subnet_to_interface() first.
    port_locations = []
    for side in config['config']['interfaces']:
        for interface in config['config']['interfaces'][side]:
            port_locations.append(interface['portSystemId'])

    if not port_locations:
        raise Exception("There are no ports specified in the configuration.")

    # Determine if the ports are already part of a queue.
    found_queue = False    
    for queue in cf.perform("listQueues"):
        queue_info = cf.perform("getQueue", queueId=queue["id"])

        # Virtual ports are found under the "computeGroups" key.
        for cg in queue_info['computeGroups']:
            for port in cg['ports']:
                if port['systemId'] in port_locations:
                    found_queue = True
                    break

        # None-virtual ports are found under the "ports" key.
        for port in queue['ports']:
            if port['systemId'] in port_locations:
                found_queue = True
                break

        if found_queue:
            break

    if not found_queue:
        # We need to create a queue for the ports.
        port_ids = []
        for location in port_locations:
            port_ids.append(get_port_id(location))

        # NOTE: The user must have permission to create a queue.
        queue_info = cf.perform("createQueue", name=queue_name, portIds=port_ids)

    config['config']['queue'] = {}
    config['config']['queue']['id'] = queue_info['id']
    config['config']['queue']['name'] = queue_info['name']    

    return queue_info

#=============================================================================
# Global Variables
#=============================================================================
cfcontroller = "cyberflood.controller.gigacorp.com"
username = "john.smith@gigacorp.com"
password = "<insert your password here>"
test_name = "From Scratch"
port1_location = "10.141.49.19/1/1"
port2_location = "10.141.49.19/1/2"
bandwidth = 250000
client_subnet = "10.1.1.1"
server_subnet = "10.1.1.150"

#=============================================================================
# Main
#=============================================================================

pp = pprint.PrettyPrinter(indent=2)


print("Initializing the CyberFlood object...")
cf = CyberFlood.CyberFlood(username=username, password=password, controller_address=cfcontroller, log_level="DEBUG")

# Check to see if the named test already exists.
test_info = None
for test in cf.perform("listTests", filters={"name": test_name}):    
    test_id = test['id']
    test_info = cf.perform("getEmixTest", testId=test_id)
    print("Found test " + test_info['name'])

if not test_info:
    # The test doesn't already exist, so create it.
    test_info = cf.perform("createEmixTest", name=test_name, description="This test was built from scratch using the API.")
    test_id = test_info['id']

# Change various settings.
test_info['config']['loadSpecification']['bandwidth'] = bandwidth
test_info['config']['networks']['client']['ipV4SegmentSize'] = 1400
test_info['config']['networks']['server']['delayedAcks']['bytes'] = 2920
test_info['config']['networks']['server']['ipV4SegmentSize'] = 1460

# Add the client and server subnets.
client_subnet = None
for subnet in cf.perform("listIpv4Subnets", filters={"name": "scratch_client_b2b_1"}):
    client_subnet = cf.perform("getIpv4Subnet", profileId=subnet['id'])

if not client_subnet:
    client_subnet = cf.perform("createIpv4Subnet", name="scratch_client_b2b_1", 
                                                   randomize=False, 
                                                   mac={'enabled': False}, 
                                                   addressing={'address': client_subnet,
                                                               'count': 100,
                                                               'forceIpAllocation': False,
                                                               'netmask': 24,
                                                               'type': 'custom'})

server_subnet = None
for subnet in cf.perform("listIpv4Subnets", filters={"name": "scratch_server_b2b_1"}):
    server_subnet = cf.perform("getIpv4Subnet", profileId=subnet['id'])

if not server_subnet:
    server_subnet = cf.perform("createIpv4Subnet", name="scratch_server_b2b_1", 
                                                   randomize=False, 
                                                   mac={'enabled': False}, 
                                                   addressing={'address': server_subnet,
                                                               'count': 100,
                                                               'forceIpAllocation': False,
                                                               'netmask': 24,
                                                               'type': 'custom'})

test_info['config']['subnets']['client'] = [client_subnet]
test_info['config']['subnets']['server'] = [server_subnet]

# Configure the traffic mix.
test_info['config']["trafficMix"]['mixer'] = []
add_profile_to_traffic_mix(test_info, "BGP_VF", 4)
add_profile_to_traffic_mix(test_info, "Linkedin_VF", 5)
add_profile_to_traffic_mix(test_info, "RDP_VF", 10)
add_profile_to_traffic_mix(test_info, "Webex_VF", 10)

add_protocol_to_traffic_mix(test_info, "Telnet", 5)
add_protocol_to_traffic_mix(test_info, "SIP", 65)
add_protocol_to_traffic_mix(test_info, "FTP", 1)

# Map the subnets to the CyberFlood ports.
map_subnet_to_interface(test_info, "client", "scratch_client_b2b_1", port1_location)
map_subnet_to_interface(test_info, "server", "scratch_server_b2b_1", port2_location)
queue_info = reserve_ports(test_info)

# This command "saves" the modified configuration to the controller.
cf.perform("updateEmixTest", test_info, testId=test_id)

# Execute the test and wait for it to complete.
testrun = run_test(test)        

if queue_name == "Temp-Automation-Queue":
    # We created a temporary queue, so we need to clean up afterwards.
    cf.perform("deleteQueue", queueId=queue_info["id"])

results = get_results(testrun)

pp.pprint(results["raw"]["Summary"])
pp.pprint(results["raw"]["Connections"]["Successful Transactions/Second"])

print("Done!")

exit()