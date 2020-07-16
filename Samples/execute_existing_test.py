"""
     Spirent CyberFlood Python Client
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    This is a simple example of how to execute an existing CyberFlood testcase, 
    using the CyberFlood Python Client.
    Before execution, the VLAN ID and the test execution duration are modified.

"""

import sys
import time
import pprint

sys.path.append("../CyberFloodPythonClient")
import CyberFlood


#==============================================================================
def execute_test(test):
    """Execute the specified test and wait until it has completed.
    """

    testrun = None

    if test and test["id"]:         
        
        print("Starting Test '" + test["name"] + "' (" + test["type"] + ")...")                

        testrun = cf.perform("startTest", testId=test["id"])

        time.sleep(1)

        testrunid = testrun.get("id", None)
        
        if testrunid:
            # Wait for the test to finish.
            stop = False
            currentsubstatus = ""
            while not stop:
                testrun = cf.perform("getTestRun", testRunId=testrunid)

                stop = True
                status = testrun.get("status", None)

                if status == "running" or status == "waiting":
                    substatus = testrun.get("subStatus", "")

                    if substatus == "":
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
        resultlist = cf.perform("listTestRunResults", testRunId=testrunid)
        for result in resultlist:
            # I'm assuming that there is only one result per test run.
            results = result
            break

    return results


#==============================================================================

pp = pprint.PrettyPrinter(indent=2)


# cfcontroller = "10.140.99.128"
# username = "matt.jefferson@spirent.com"
# password = "spirent"

cfcontroller = "americas-demo.appsec.spirent.com"
username = "matthew.jefferson@spirent.com"
password = "spirent"

print("Initializing the CyberFlood object...")
cf = CyberFlood.CyberFlood(username=username, password=password, controller_address=cfcontroller, log_level="DEBUG")

# Find the test named "Matt Test"...
for test in cf.perform("listTests", filters={"name": "Matt Test"}):
    testid = test["id"]

    # Get the test information as a dictionary. 
    # We'll modify the dictionary to make changes to the configuration.
    testconfig = cf.perform("getEmixTest", testId=testid)

    # pp.pprint(testconfig)    

    # Modify the VLAN IDs.
    testconfig["config"]["subnets"]["client"][0]["vlans"][0]["id"] = 400
    testconfig["config"]["subnets"]["client"][1]["vlans"][0]["id"] = 401

    # Modify the load specification.
    testconfig["config"]["loadSpecification"]["duration"] = 180
    testconfig["config"]["loadSpecification"]["rampup"]   = 10
    
    print("Updating the configuration...")
    cf.perform("updateEmixTest", testId=testid, config=testconfig["config"])

    testrun = execute_test(test)        
    pp.pprint(testrun)
    print()
    pp.pprint(get_results(testrun))

# This is a sample testconfig dictionary:
#
# { 'author': 'matthew.jefferson@spirent.com',
#   'config': { 'criteria': { 'enabled': False,
#                             'failureBandwidth': 3,
#                             'failureTransactions': 3},
#               'debug': { 'client': {'enabled': False, 'packetTrace': 5000000},
#                          'enabled': True,
#                          'logLevel': 3,
#                          'server': {'enabled': False, 'packetTrace': 5000000}},
#               'interfaces': { 'client': [ { 'portSystemId': '10.140.104.229/1/1',
#                                             'subnetIds': [ 'cb231f48fae31bbea7f06dbfe6c58622',
#                                                            '83086893bffdebd0a218a7e52e66652c']}],
#                               'server': [ { 'portSystemId': '10.140.104.229/1/2',
#                                             'subnetIds': [ 'd72739cb2173cef7affe44a9d67b95c3',
#                                                            'd72739cb2173cef7affe44a9d67ba21a']}]},
#               'loadSpecification': { 'bandwidth': 146000,
#                                      'constraints': {'enabled': False},
#                                      'duration': 225,
#                                      'rampdown': 18,
#                                      'rampup': 30,
#                                      'shutdown': 7,
#                                      'startup': 20,
#                                      'type': 'SimUsers'},
#               'nat': {'enabled': False},
#               'networks': { 'client': { 'closeWithFin': False,
#                                         'congestionControl': True,
#                                         'delayedAcks': { 'bytes': 2920,
#                                                          'enabled': True,
#                                                          'timeout': 200},
#                                         'fragmentReassemblyTimer': 30000,
#                                         'gratuitousArp': True,
#                                         'inactivityTimer': 0,
#                                         'initialCongestionWindow': 2,
#                                         'ipV4SegmentSize': 1460,
#                                         'ipV6SegmentSize': 1440,
#                                         'portRandomization': False,
#                                         'portRangeLowerBound': 1024,
#                                         'portRangeUpperBound': 65535,
#                                         'receiveWindow': 32768,
#                                         'retries': 2,
#                                         'sackOption': False,
#                                         'tcpVegas': False},
#                             'server': { 'congestionControl': True,
#                                         'delayedAcks': { 'bytes': 2920,
#                                                          'enabled': True,
#                                                          'timeout': 200},
#                                         'gratuitousArp': True,
#                                         'inactivityTimer': 0,
#                                         'initialCongestionWindow': 2,
#                                         'ipV4SegmentSize': 1460,
#                                         'ipV6SegmentSize': 1440,
#                                         'receiveWindow': 32768,
#                                         'retries': 2,
#                                         'sackOption': False,
#                                         'tcpVegas': False}},
#               'queue': {'id': 'Victor', 'name': 'Victor'},
#               'runtimeOptions': { 'contentFiles': [],
#                                   'customSamplingInterval': 4,
#                                   'jumboFrames': False,
#                                   'maintainTarget': False,
#                                   'statisticsLevel': 'Full',
#                                   'statisticsSamplingInterval': False,
#                                   'useRealMac': False},
#               'securityMix': {'profiles': [], 'volume': 1},
#               'subnets': { 'client': [ { 'addressing': { 'address': '2001::1:1',
#                                                          'count': 255,
#                                                          'forceIpAllocation': False,
#                                                          'netmask': 64,
#                                                          'type': 'static'},
#                                          'defaultGateway': {'enabled': False},
#                                          'description': '',
#                                          'id': 'cb231f48fae31bbea7f06dbfe6c58622',
#                                          'mld': 2,
#                                          'name': 'CUD-Subnet IPv6 Profile',
#                                          'routing': [],
#                                          'type': 'ipv6',
#                                          'vlans': [ { 'cfi': 0,
#                                                       'id': 102,
#                                                       'priority': 0,
#                                                       'tagIncrement': 0,
#                                                       'tagProtocolId': '0x8100'}]},
#                                        { 'addressing': { 'address': '7.16.41.1',
#                                                          'count': 253,
#                                                          'forceIpAllocation': False,
#                                                          'netmask': 16,
#                                                          'type': 'custom'},
#                                          'defaultGateway': {'enabled': False},
#                                          'description': 'C1Q1 ---VLAN101',
#                                          'id': '83086893bffdebd0a218a7e52e66652c',
#                                          'mac': {'enabled': False},
#                                          'name': 'C1-Q1_IPv4_CUD_Client',
#                                          'randomize': False,
#                                          'routing': [],
#                                          'type': 'ipv4',
#                                          'vlans': [ { 'cfi': 0,
#                                                       'id': 102,
#                                                       'priority': 0,
#                                                       'tagIncrement': 0,
#                                                       'tagProtocolId': '0x8100'}]}],
#                            'server': [ { 'addressing': { 'address': '2001::2',
#                                                          'count': 255,
#                                                          'forceIpAllocation': False,
#                                                          'netmask': 64,
#                                                          'type': 'static'},
#                                          'defaultGateway': {'enabled': False},
#                                          'description': '',
#                                          'id': 'd72739cb2173cef7affe44a9d67b95c3',
#                                          'mld': 2,
#                                          'name': 'CUD-SERVER IPv6 Profile',
#                                          'routing': [],
#                                          'type': 'ipv6',
#                                          'vlans': [ { 'cfi': 0,
#                                                       'id': 102,
#                                                       'priority': 0,
#                                                       'tagIncrement': 0,
#                                                       'tagProtocolId': '0x8100'}]},
#                                        { 'addressing': { 'address': '7.16.40.3',
#                                                          'count': 200,
#                                                          'forceIpAllocation': False,
#                                                          'netmask': 16,
#                                                          'type': 'custom'},
#                                          'defaultGateway': {'enabled': False},
#                                          'description': '',
#                                          'id': 'd72739cb2173cef7affe44a9d67ba21a',
#                                          'mac': {'enabled': False},
#                                          'name': 'C1-Q1_IPv4_ether1_Server52',
#                                          'randomize': False,
#                                          'routing': [],
#                                          'type': 'ipv4',
#                                          'vlans': [ { 'cfi': 0,
#                                                       'id': 102,
#                                                       'priority': 0,
#                                                       'tagIncrement': 0,
#                                                       'tagProtocolId': '0x8100'}]}]},
#               'trafficMix': { 'initialType': 'Custom',
#                               'mixer': [ { 'name': 'CUD-YouTube',
#                                            'percentage': 19.55,
#                                            'scenarioIds': [ '02.2011.05.streaming_media.youtube.youtube_com_youtube.login_and_play_video_and_pause_video-01',
#                                                             '02.2012.09.streaming_media.youtube.youtube_com.youtube.login_upload_video-01',
#                                                             '02.2012.09.streaming_media.youtube.youtube_com.youtube.watch_video-02'],
#                                            'scenarioNames': [ 'YouTube: Play '
#                                                               'and pause video',
#                                                               'YouTube: Login, '
#                                                               'upload video '
#                                                               '(01)',
#                                                               'YouTube: Watch '
#                                                               'video (2)'],
#                                            'type': 'profile'},
#                                          { 'name': 'CUD-Facebook',
#                                            'percentage': 22.72,
#                                            'scenarioIds': [ '02.2011.05.social_networking.facebook.facebook_com.facebook.find_friend-01',
#                                                             '02.2011.05.social_networking.facebook.facebook_com.facebook.logout-01',
#                                                             '02.2011.05.social_networking.facebook.facebook_com.facebook.send_message-01'],
#                                            'scenarioNames': [ 'Facebook: Login '
#                                                               'and search for '
#                                                               'new friends',
#                                                               'Facebook: Login '
#                                                               'and logout',
#                                                               'Facebook: Login '
#                                                               'and chat'],
#                                            'type': 'profile'},
#                                          { 'name': 'CUD-Eharmony',
#                                            'percentage': 19.44,
#                                            'scenarioIds': [ '02.2011.05.social_networking.eharmony.eharmony_com.eharmony.select_play_video-01',
#                                                             '02.2011.05.social_networking.eharmony.eharmony_com.eharmony.login_view_free_personality_profile-01'],
#                                            'scenarioNames': [ 'eHarmony: Login '
#                                                               'and play video',
#                                                               'eHarmony: Login '
#                                                               'and view free '
#                                                               'personality '
#                                                               'profile'],
#                                            'type': 'profile'},
#                                          { 'name': 'CUD-Pandora',
#                                            'percentage': 10.4,
#                                            'scenarioIds': [ '02.2011.05.streaming_media.pandora.pandora_com.pandora.play_songs-01',
#                                                             '02.2011.05.streaming_media.pandora.pandora_com.pandora.share_station_on_facebook-01',
#                                                             '02.2012.09.streaming_media.pandora.pandora_com.pandora.login_play_radio-01'],
#                                            'scenarioNames': [ 'Pandora: Login '
#                                                               'and play new '
#                                                               'station',
#                                                               'Pandora: Share '
#                                                               'station on '
#                                                               'Facebook',
#                                                               'Pandora: Login, '
#                                                               'play radio '
#                                                               '(01)'],
#                                            'type': 'profile'},
#                                          { 'name': 'Netflix',
#                                            'percentage': 23.87,
#                                            'scenarioIds': [ '02.2011.05.streaming_media.netflix_browsing.netflix_com.netflixbrowsing.browse-01',
#                                                             '02.2011.09.streaming_media.netflix_adding_movie.netflix_com.netflix_adding_movie.select_add_movie-01',
#                                                             '02.2011.09.streaming_media.netflix_adding_movie.netflix_com.netflix_adding_movie.select_add_movie-02',
#                                                             '02.2011.09.streaming_media.netflix_browsing_see_all.netflix_com.netflix_browsing_see_all.browse_options-01',
#                                                             '02.2011.09.streaming_media.netflix_browsing_see_all.netflix_com.netflix_browsing_see_all.browse_options-02',
#                                                             '02.2011.09.streaming_media.netflix_search.netflix_com.netflix_search.search_movie-01',
#                                                             '02.2011.09.streaming_media.netflix_search.netflix_com.netflix_search.search_movie-02',
#                                                             '02.2011.09.streaming_media.netflix_signout.netflix_com.netflix_signout.signout_account-01',
#                                                             '02.2011.09.streaming_media.netflix_signout.netflix_com.netflix_signout.signout_account-02',
#                                                             '02.2011.09.streaming_media.netflix_streaming.netflix_com.netflix_streaming.start_streaming_movie-01',
#                                                             '02.2011.09.streaming_media.netflix_streaming.netflix_com.netflix_streaming.start_streaming_movie-02',
#                                                             '02.2011.09.streaming_media.netflix_streaming_resuming.netflix_com.netflix_streaming_resuming.resume_streaming_movie-01',
#                                                             '02.2011.09.streaming_media.netflix_streaming_resuming.netflix_com.netflix_streaming_resuming.resume_streaming_movie-02',
#                                                             '02.2011.09.streaming_media.netflix_typing_search.netflix_com.netflix_typing_search.search_movie-01',
#                                                             '02.2011.09.streaming_media.netflix_typing_search.netflix_com.netflix_typing_search.search_movie-02'],
#                                            'scenarioNames': [ 'Netflix: Browse '
#                                                               'movies',
#                                                               'Netflix: Select '
#                                                               'and add movie',
#                                                               'Netflix: Select '
#                                                               'and add movie '
#                                                               '(02)',
#                                                               'Netflix: Browse '
#                                                               'options',
#                                                               'Netflix: Browse '
#                                                               'options (02)',
#                                                               'Netflix: Search '
#                                                               'for a movie',
#                                                               'Netflix: Search '
#                                                               'for a movie '
#                                                               '(02)',
#                                                               'Netflix: Sign '
#                                                               'out of account',
#                                                               'Netflix: Sign '
#                                                               'out of account '
#                                                               '(02)',
#                                                               'Netflix: Start '
#                                                               'streaming movie',
#                                                               'Netflix: Start '
#                                                               'streaming movie '
#                                                               '(02)',
#                                                               'Netflix: Resume '
#                                                               'streaming movie',
#                                                               'Netflix: Resume '
#                                                               'streaming movie '
#                                                               '(02)',
#                                                               'Netflix: Search '
#                                                               'for a movie',
#                                                               'Netflix: Search '
#                                                               'for a movie '
#                                                               '(02)'],
#                                            'type': 'profile'},
#                                          { 'name': 'Instagram-cud',
#                                            'percentage': 4.02,
#                                            'scenarioIds': [ '02.2015.02.social_networking.instagram.apple_com.instagram.login_share_photo_add_comment_logout-04'],
#                                            'scenarioNames': [ 'Instagram: '
#                                                               'Login, share '
#                                                               'photo, add '
#                                                               'comment and '
#                                                               'logout (04)'],
#                                            'type': 'profile'}],
#                               'type': 'emix'},
#               'trafficPattern': 'Pair',
#               'virtualRouters': {}},
#   'createdAt': '2020-06-11T17:41:41.289Z',
#   'description': '',
#   'id': '35944c8982613d3a08ed5d5ebf841fcf',
#   'lastRunBy': {'email': 'N/A', 'firstName': 'N/A', 'lastName': 'N/A'},
#   'name': 'CUD-Throughput-IPv6 with Mixed Traffic Mod',
#   'projectId': None,
#   'updatedAt': '2020-06-12T23:54:27.021Z',
#   'updatedBy': 'matthew.jefferson@spirent.com'}


print("Done!")
exit()
