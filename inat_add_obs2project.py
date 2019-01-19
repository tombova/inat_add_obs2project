#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jan  1 13:57:09 2019

@author: Tom
"""
import sys
import json
import requests
import pprint
#import time
from typing import Dict, Any, List, BinaryIO, Union  # noqa: F401
import send_gmail
import logging
import configparser

config = configparser.ConfigParser()
config.read('inat_add_obs2project.ini')


INAT_NODE_API_BASE_URL = "https://api.inaturalist.org/v1/"
INAT_BASE_URL = "https://www.inaturalist.org"

class AuthenticationError(Exception):
    ''' Exception for an Authentication error '''
    pass


class ObservationNotFound(Exception):
    ''' Exception for an Observation not found error '''
    pass


def get_access_token(username: str, password: str, app_id: str, app_secret: str) -> str:
    """
    Get an access token using the user's iNaturalist username and password.

    (you still need an iNaturalist app to do this)

    :param username:
    :param password:
    :param app_id:
    :param app_secret:
    :return: the access token, example use: headers = {"Authorization": "Bearer %s" % access_token}
    """
    payload = {
        'client_id': app_id,
        'client_secret': app_secret,
        'grant_type': "password",
        'username': username,
        'password': password
    }

    response = requests.post("{base_url}/oauth/token".format(base_url=INAT_BASE_URL), payload)
    try:
        #rootLogger.info("Access token: '%s'" % response.json()["access_token"])
        return response.json()["access_token"]

    except KeyError:
        raise AuthenticationError("Authentication error, please check credentials.")


def getProject(projectID):
    ''' retrieve project information, return a list of species IDs '''
 
    project = requests.get('https://api.inaturalist.org/v1/projects/%s?rule_details=true' % \
                           projectID)
    #rootLogger.info("Project Request Status: %d" % project.status_code)

    if project.status_code == 200:
        response_data = json.loads(project.text)
        if int(response_data['total_results']) > 0:
            result = response_data['results'][0]
            rootLogger.info("----------------------------------")            
            rootLogger.info("Title: %s" % result['title'])
            rootLogger.info("Description: %s" % result['description'])
            place = result['place']
            rootLogger.info("  Place: %s" % place['display_name'])
            rootLogger.info("Number of rules: %d" % len(result['project_observation_rules']))
            for aRule in result['project_observation_rules']:
                if aRule['operand_type'] == 'Taxon':
                    taxon = aRule['taxon']
                    rootLogger.info("  Name: %s,  count: %s" % (taxon['name'], taxon['observations_count']))
            rootLogger.info("----------------------------------")   
      
    getURL='%s/projects/%s.json' % (INAT_BASE_URL, projectID)
    getReq = requests.get(getURL)
    #rootLogger.info("GET project request status code: %d" % getReq.status_code)    
    #rootLogger.info("GET project request response: '%s'" % getReq.text)
    if getReq.status_code == 200:    
        response_data = json.loads(getReq.text)
        rootLogger.info("Project observation count: %s" % response_data['project_observations_count'])

    rootLogger.info("\nGet project stats")
    project_species = []
    getStatsURL='%sobservations/species_counts' \
                '?project_id=%s&place_id=any' \
                '&verifiable=any&captive=any' % (INAT_NODE_API_BASE_URL, projectID)
    getStatsReq = requests.get(getStatsURL)
    if getStatsReq.status_code == 200:    
        response_data = json.loads(getStatsReq.text)
        #rootLogger.info(response_data)
        rootLogger.info("Total species: %s" % response_data['total_results'])
        results = response_data['results']
        for aResult in results:
            try:
                rank = aResult['taxon']['rank']
            except KeyError: 
                rank = '<none>'
            taxon = aResult['taxon']['iconic_taxon_name']
            rootLogger.info("Name: %s, Common name: %s id: %s\n"
                  "  rank: %s taxon: %s count: %s" % \
                  (aResult['taxon']['name'], 
                   aResult['taxon']['preferred_common_name'], 
                   aResult['taxon']['id'],
                   rank,
                   taxon,
                   aResult['count']))
            project_species.append(aResult['taxon']['id'])

    else:
        rootLogger.info("Stats request '%s' failed: %d" % (getStatsURL,
                                                 getStatsReq.status_code))
        

    return project_species
     
# THIS DIDN'T WORK
def addOb2ProjV1(observationId, projectId, accessToken):
    ''' Use V1 API to add an observation to a project '''
    
    payload = {"observation_id":  observationId}
    postURL='https://api.inaturalist.org/v1/projects/%s/add' % projectId
    postReq = requests.post(postURL,
                            data=json.dumps(payload),
                            headers=_build_auth_header(accessToken))
    rootLogger.info("POST request status code: %d" % postReq.status_code)
    rootLogger.info("POST request response: '%s'" % postReq.text)


def addOb2Proj(observationId, projectId, accessToken):
    ''' Use V1 API to add an observation to a project '''
    
 
    data = {'project_observation[observation_id]': observationId,
            'project_observation[project_id]': projectId}
    
              

    postURL='%s/project_observations' % INAT_BASE_URL
    postReq = requests.post(postURL,
                            data=data,
                            headers=_build_auth_header(accessToken))
    if postReq.status_code == 200:
        rootLogger.info("POST successful")
        return True
    else:    
        rootLogger.info("POST request status code: %d" % postReq.status_code)
        rootLogger.info("POST request response: '%s'" % postReq.text)
        return False

    
    
    
def _build_auth_header(access_token: str) -> Dict[str, str]:
    ''' This function takes the access_token and creates the Authorization 
        header needed by the non-V1 interface'''

    return {"Authorization": "Bearer %s" % access_token}


############################################
# Main program                             #
############################################
       

logPath = "./"
fileName = "results"
with open(fileName, "w"):
	pass

logFormatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s\r\n")
rootLogger = logging.getLogger()
rootLogger.setLevel(config['DEFAULT']['loggingLevel'])

fileHandler = logging.FileHandler("{0}/{1}.log".format(logPath, fileName))
fileHandler.setFormatter(logFormatter)
rootLogger.addHandler(fileHandler)

logFormatter = logging.Formatter("[%(levelname)-5.5s]  %(message)s")
consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(logFormatter)
rootLogger.addHandler(consoleHandler)

# Get Access Token using username and password

def main():
    # TODO: Need to put user name and password in config file or make
    #       command line arguments    
    access_token = get_access_token(config['inaturalist.org']['username'], 
                                    config['inaturalist.org']['password'], 
                                    config['inaturalist.org']['app_id'], 
                                    config['inaturalist.org']['app_secret'])

    page_size = 100

    # Get some project information and a list of current species
    project_species = getProject(config['inaturalist.org']['project_id'])        

    # These are some variables used for counting things and keeping track 
    # of states
    newSpeciesCount = 0
    newSpeciesAdded = 0
    observationsAdded = 0
    observationsAddFailures = 0
    newSpeciesFlag = False
    taxonResponseCount = {}

    # As we find new species, put in this list
    new_species = []

    # These are the taxon we are interested in
    taxon_list = ['Reptilia', 
                 'Amphibia']

    # Loop for each taxon in list
    for aTaxon in taxon_list:
        rootLogger.info("\nQuery for research grade %s in New York State "
                        "not in project: %s" % (aTaxon, config['inaturalist.org']['project_id']))

        # Start with page 1
        page = 1
        done = False
        while not done:
            rootLogger.info("Page %d, page size: %d" % (page, page_size))
            # Query all observations in New York State, with matching Taxon ID,
            # not already in project, is research grade, on desired page
            r = requests.get('https://api.inaturalist.org/v1/observations'
                             '?place_id=48'
                             '&iconic_taxa=%s'
                             '&not_in_project=%s'
                             '&quality_grade=research'
                             '&page=%d'
                             '&per_page=%s'
                             '&order=desc'
                             '&order_by=created_at' % \
                             (aTaxon, config['inaturalist.org']['project_id'], page, page_size))


            #rootLogger.info("Observation Request Status: %d" % r.status_code)

            # 200 means success
            if r.status_code == 200:
                # convert JSON response to a python dictionary 
                response_data = json.loads(r.text)

                #rootLogger.info("----------------------------------")        
                if page == 1:
                    rootLogger.info("Total responses: %d" % (response_data['total_results']))
                    taxonResponseCount[aTaxon] = response_data['total_results']
                # If we get back no results, we are done
                if len(response_data['results']) == 0:
                    done = True
                rootLogger.debug(pprint.pformat(response_data['results'][0]))  
                #sys.exit(1)
                for result in response_data['results']:
                    newSpeciesFlag = False
                    id = result['id']
                    taxon_id = result['taxon']['id']
                    try:
                        rank = result['taxon']['rank']
                    except KeyError: 
                        rank = '<none>'
                    taxon = result['taxon']['iconic_taxon_name']
    
                    # If taxon ID is not in list of species already in
                    # project and not is list of new species we have already found
                    # print banner, increment counter, and set flag
                    if taxon_id not in project_species and \
                       taxon_id not in new_species:
                        new_species.append(taxon_id)
                        rootLogger.info("===== NEW SPECIES FOR PROJECT =====")
                        newSpeciesCount += 1 
                        newSpeciesFlag = True
                        
                    # Print some information about observation
                    rootLogger.info("Observation ID:        %s" % id)    
                    rootLogger.info("Taxon ID:              %s" % taxon_id)
                    rootLogger.info("Name:                  %s" % result['taxon']['name'])
                    rootLogger.info("Preferred common name: %s" % result['taxon']['preferred_common_name'])
                    #rootLogger.info("Rank:                  %s" % rank)
                    #rootLogger.info("Taxon:                 %s" % taxon)
                    rootLogger.info("Grade:                 %s" % result['quality_grade'])
                    rootLogger.info("Observed at:           %s" % result['time_observed_at'])
                    rootLogger.info("Created at:            %s" % result['created_at'])
                    rootLogger.info("User Name:             %s" % result['user']['name'])
                    #rootLogger.info("User ID:               %s" % result['user']['login'])
                    #rootLogger.info("Place IDs:             %s" % ",".join(str(x) for x in result['place_ids'][:5]))
                    #rootLogger.info("Project IDs:           %s" % ",".join(str(x) for x in result['project_ids']))
                    #rootLogger.info("\n")
    
                
                    # Try to add observation to project using access_token for
                    # authentication
                    if addOb2Proj(result['id'], config['inaturalist.org']['project_id'], access_token):
                        if newSpeciesFlag:
                            newSpeciesAdded += 1
                        observationsAdded += 1
                    else:
                        observationsAddFailures += 1
                        
                    rootLogger.info("----------------------------------")        
                
                page += 1
            else:
                done = True
                rootLogger.info("Observation response: %s" % r.text)
        
    rootLogger.info("\nNew Species: %d" % newSpeciesCount)
    rootLogger.info("New Species Added: %d" % newSpeciesAdded)
    rootLogger.info("Observations Added: %d" % observationsAdded)
    rootLogger.info("Observations Add Failures: %d" % observationsAddFailures)      
    for aTaxon in taxonResponseCount:
        rootLogger.info("Taxon: %s, total results: %d" % (aTaxon, taxonResponseCount[aTaxon]))
    
    # Read results file into a buffer
    with open("results.log", "r") as resultsFile:
        resultsBuffer = resultsFile.read()

    # Send results to the following email addresses
    send_gmail.send_email(config, resultsBuffer, subject="inat_add_objs2project results")


if __name__ == "__main__":
    sys.exit(main())

