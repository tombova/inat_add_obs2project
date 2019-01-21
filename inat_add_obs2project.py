#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jan  1 13:57:09 2019

@author: Tom
"""
import sys
import json
import logging
import configparser
#import pprint
#import time
from typing import Dict
import requests
import send_gmail



INAT_NODE_API_BASE_URL = "https://api.inaturalist.org/v1/"
INAT_BASE_URL = "https://www.inaturalist.org"

class AuthenticationError(Exception):
    ''' Exception for an Authentication error '''


class ObservationNotFound(Exception):
    ''' Exception for an Observation not found error '''


def get_access_token(username: str,
                     password: str,
                     app_id: str,
                     app_secret: str) -> str:
    """
    Get an access token using the user's iNaturalist username and password.

    (you still need an iNaturalist app to do this)

    :param username:
    :param password:
    :param app_id:
    :param app_secret:
    :return: the access token, example use:
           headers = {"Authorization": "Bearer %s" % access_token}
    """
    payload = {
        'client_id': app_id,
        'client_secret': app_secret,
        'grant_type': "password",
        'username': username,
        'password': password
    }

    response = requests.post("{base_url}/oauth/token".\
            format(base_url=INAT_BASE_URL), payload)
    try:
        #LOGGER.info("Access token: '%s'" % response.json()["access_token"])
        return response.json()["access_token"]

    except KeyError:
        raise AuthenticationError("Authentication error, "
                                  " please check credentials.")

def get_place_name(place_id):
    ''' Get Place name from ID '''

    LOGGER.info("Looking up place: %s", place_id)
    place_name = None
    place = requests.get("https://api.inaturalist.org/v1/places/%s" \
                           % place_id)
    if place.status_code == 200:
        response_data = json.loads(place.text)
        try:
            place_name = response_data['results'][0]['display_name']
        except KeyError:
            LOGGER.error("place_id '%s' not found", place_id)
    else:
        LOGGER.error("response status = %d", place.status_code)
    return place_name

def get_project_id(project_slug):
    ''' Get Project ID from slug (short name) '''

    project_id = None
    project = requests.get("https://api.inaturalist.org/v1/projects/%s" \
                           % project_slug)
    if project.status_code == 200:
        response_data = json.loads(project.text)
        try:
            project_id = response_data['results'][0]['id']
        except KeyError:
            LOGGER.error("Project ID not found")
    else:
        LOGGER.error("Project %s not found", project_slug)

    return project_id

def get_project(project_id):
    ''' retrieve project information, return a list of species IDs '''

    project_species = []
    project = requests.get(\
            'https://api.inaturalist.org/v1/projects/%s?rule_details=true' % \
            project_id)
    #LOGGER.info("Project Request Status: %d" % project.status_code)

    if project.status_code == 200:
        response_data = json.loads(project.text)
        if int(response_data['total_results']) > 0:
            result = response_data['results'][0]
            LOGGER.info("----------------------------------")
            LOGGER.info("Title: %s", result['title'])
            LOGGER.info("Description: %s", result['description'])
            place = result['place']
            LOGGER.info("  Place: %s (%s)", place['display_name'],
                        place['id'])
            LOGGER.info("Number of rules: %d",
                        len(result['project_observation_rules']))
            for a_rule in result['project_observation_rules']:
                if a_rule['operand_type'] == 'Taxon':
                    taxon = a_rule['taxon']
                    LOGGER.info("  Name: %s,  count: %s", taxon['name'],
                                taxon['observations_count'])
            LOGGER.info("----------------------------------")
    else:
        return project_species

    get_url = '%s/projects/%s.json' % (INAT_BASE_URL, project_id)
    get_req = requests.get(get_url)
    #LOGGER.info("GET project request status code: %d", get_req.status_code)
    #LOGGER.info("GET project request response: '%s'", get_req.text)
    if get_req.status_code == 200:
        response_data = json.loads(get_req.text)
        LOGGER.info("Project %s observation count: %s",
                    project_id,
                    response_data['project_observations_count'])

    LOGGER.info("\nGet project stats for %s", project_id)
    get_stats_url = '%sobservations/species_counts' \
                    '?project_id=%s&place_id=any' \
                    '&verifiable=any&captive=any' % \
                    (INAT_NODE_API_BASE_URL, project_id)
    get_stats_req = requests.get(get_stats_url)
    if get_stats_req.status_code == 200:
        response_data = json.loads(get_stats_req.text)
        #LOGGER.info(response_data)
        LOGGER.info("\nTotal species: %s\n------------",
                    response_data['total_results'])
        results = response_data['results']
        for a_result in results:
            try:
                rank = a_result['taxon']['rank']
            except KeyError:
                rank = '<none>'
            taxon = a_result['taxon']['iconic_taxon_name']
            LOGGER.info("Name:        %s\n"
                        "Common name: %s\n"
                        "Taxon ID:    %s\n"
                        "Rank:        %s\n"
                        "Taxon:       %s\n"
                        "Count: %s\n",
                        a_result['taxon']['name'],
                        a_result['taxon']['preferred_common_name'],
                        a_result['taxon']['id'],
                        rank,
                        taxon,
                        a_result['count'])
            project_species.append(a_result['taxon']['id'])

    else:
        LOGGER.info("Stats request '%s' failed: %d", get_stats_url,
                    get_stats_req.status_code)

    return project_species

# THIS DIDN'T WORK
def add_ob_2_proj_v1(observation_id, project_id, access_token):
    ''' Use V1 API to add an observation to a project '''

    payload = {"observation_id":  observation_id}
    post_url = 'https://api.inaturalist.org/v1/projects/%s/add' % project_id
    post_req = requests.post(post_url,
                             data=json.dumps(payload),
                             headers=_build_auth_header(access_token))
    #LOGGER.info("POST request status code: %d", post_req.status_code)
    #LOGGER.info("POST request response: '%s'", post_req.text)

    if post_req.status_code == 200:
        LOGGER.info("POST successful")
        return True
    return False

def add_ob_2_proj(observation_id, project_id, access_token):
    ''' Use V1 API to add an observation to a project '''

    data = {'project_observation[observation_id]': observation_id,
            'project_observation[project_id]': project_id}

    post_url = '%s/project_observations' % INAT_BASE_URL
    post_req = requests.post(post_url,
                             data=data,
                             headers=_build_auth_header(access_token))
    if post_req.status_code == 200:
        LOGGER.info("POST successful")
        return True
    #LOGGER.info("POST request status code: %d", post_req.status_code)
    #LOGGER.info("POST request response: '%s'", post_req.text)
    return False

def _build_auth_header(access_token: str) -> Dict[str, str]:
    ''' This function takes the access_token and creates the Authorization
        header needed by the non-V1 interface'''

    return {"Authorization": "Bearer %s" % access_token}


############################################
# Main program                             #
############################################

LOG_PATH = "./"
LOG_FILE_NAME = "results.log"
with open(LOG_FILE_NAME, "w"):
    pass

LOG_FORMATTER = logging.Formatter("%(asctime)s [%(threadName)-12.12s]"
                                  " [%(levelname)-5.5s] %(message)s")
LOGGER = logging.getLogger()

FILE_HANDLER = logging.FileHandler("{0}/{1}".format(LOG_PATH, LOG_FILE_NAME))
FILE_HANDLER.setFormatter(LOG_FORMATTER)
LOGGER.addHandler(FILE_HANDLER)

LOG_FORMATTER = logging.Formatter("%(message)s")
CONSOLE_HANDLER = logging.StreamHandler()
CONSOLE_HANDLER.setFormatter(LOG_FORMATTER)
LOGGER.addHandler(CONSOLE_HANDLER)


def print_obs(result):
    ''' print observations '''

    obs_id = result['id']
    taxon_id = result['taxon']['id']

    # Print some information about observation
    LOGGER.info("Observation ID:        %s", obs_id)
    LOGGER.info("Taxon ID:              %s", taxon_id)
    LOGGER.info("Name:                  %s",
                result['taxon']['name'])
    LOGGER.info("Preferred common name: %s",
                result['taxon']['preferred_common_name'])
    #LOGGER.info("Rank:                  %s", rank)
    #LOGGER.info("Taxon:                 %s", taxon)
    LOGGER.info("Grade:                 %s",
                result['quality_grade'])
    LOGGER.info("Observed at:           %s",
                result['time_observed_at'])
    LOGGER.info("Created at:            %s",
                result['created_at'])
    LOGGER.info("User Name:             %s",
                result['user']['name'])
    #LOGGER.info("User ID:               %s",
    #            result['user']['login'])
    #LOGGER.info("Place IDs:             %s",
    # ",".join(str(x) for x in result['place_ids'][:5]))
    #LOGGER.info("Project IDs:           %s",
    # ",".join(str(x) for x in result['project_ids']))
    #LOGGER.info("\n")




# pylint: disable=too-many-statements,too-many-branches,too-many-locals
def main():
    ''' Main function '''

    config = configparser.ConfigParser()
    config['DEFAULT'] = {'loggingLevel': 'INFO'}
    config['inaturalist.org'] = {'addObservations': True}
    if len(sys.argv) > 1:
        config_filename = sys.argv[1]
    else:
        config_filename = 'inat_add_obs2project.ini'

    try:
        dummy_h = open(config_filename, 'r')
        dummy_h.close()
    except FileNotFoundError:
        LOGGER.warning("File: '%s' not found, creating", config_filename)

    # Read config file
    config.read(config_filename)

    # Write possibly update file
    with open(config_filename, 'w') as config_file:
        config.write(config_file)

    LOGGER.setLevel(config['DEFAULT']['loggingLevel'])

    try:
        access_token = get_access_token(config['inaturalist.org']['username'],
                                        config['inaturalist.org']['password'],
                                        config['inaturalist.org']['app_id'],
                                        config['inaturalist.org']['app_secret'])
    except KeyError:
        LOGGER.warning("Need to define username, password, app_id, and "
                       "app_secret in [inaturalist.org] section of "
                       "configuration file: %s",
                       config_filename)
        access_token = ""

    page_size = 100

    # Get project_id from slug name
    try:
        project_id = get_project_id(config['inaturalist.org']['project_slug'])
    except KeyError:
        LOGGER.error("Need to define project_slug "
                     "in [inaturalist.org] section of "
                     "configuration file: %s",
                     config_filename)
        return 3
    if project_id is None:
        LOGGER.error("Need to define project_slug "
                     "in [inaturalist.org] section of "
                     "configuration file: %s",
                     config_filename)
        return 3

    # Get some project information and a list of current species
    project_species = get_project(project_id)

    if project_species is None:
        LOGGER.warning("Failed to get species list ")
        return 4


    # These are some variables used for counting things and keeping track
    # of states
    new_species_count = 0
    new_species_add = 0
    observations_added = 0
    observations_add_failures = 0
    new_species_flag = False
    taxon_response_count = {}

    # As we find new species, put in this list
    new_species = []

    # These are the taxon we are interested in
    taxon_list = ['Reptilia',
                  'Amphibia']

    taxon_list = config['inaturalist.org']['taxon_list'].split(',')

    place_id = config['inaturalist.org']['place_id']
    place_name = get_place_name(place_id)
    if place_name is None:
        LOGGER.error("Failed to find place id: '%s'", place_id)
        return 6

    # Loop for each taxon in list
    # pylint: disable=too-many-nested-blocks
    for a_taxon in taxon_list:
        LOGGER.info("\nQuery for research grade %s in %s "
                    "not in project: %s", a_taxon,
                    config['inaturalist.org']['project_slug'],
                    place_name)

        # Start with page 1
        page = 1
        done = False
        while not done:
            LOGGER.info("Page %d, page size: %d", page, page_size)
            # Query all observations in place ID, with matching Taxon ID,
            # not already in project, is research grade, on desired page
            req_resp = requests.get(\
                    'https://api.inaturalist.org/v1/observations'
                    '?place_id=%s'
                    '&iconic_taxa=%s'
                    '&not_in_project=%s'
                    '&quality_grade=research'
                    '&page=%d'
                    '&per_page=%s'
                    '&order=desc'
                    '&order_by=created_at' % \
                    (config['inaturalist.org']['place_id'],
                     a_taxon, project_id,
                     page, page_size))


            #LOGGER.info("Observation Request Status: %d" % req_resp.status_code)

            # 200 means success
            if req_resp.status_code == 200:
                # convert JSON response to a python dictionary
                response_data = json.loads(req_resp.text)

                #LOGGER.info("----------------------------------")
                if page == 1:
                    LOGGER.info("Total responses: %d",
                                response_data['total_results'])
                    taxon_response_count[a_taxon] = \
                            response_data['total_results']
                # If we get back no results, we are done
                # pylint: disable=len-as-condition
                if len(response_data['results']) == 0:
                    done = True
                for result in response_data['results']:
                    # Try to add observation to project using access_token for
                    # authentication

                    add_obs = config.getboolean('inaturalist.org',
                                                'addObservations')
                    if add_obs:
                        if  add_ob_2_proj(result['id'],
                                          project_id,
                                          access_token):
                            if new_species_flag:
                                new_species_add += 1
                            observations_added += 1
                            # If taxon ID is not in list of species already in
                            # project and not is list of new species we have
                            # already found
                            # print banner, increment counter, and set flag
                            new_species_flag = False
                            taxon_id = result['taxon']['id']
                            if taxon_id not in project_species and \
                               taxon_id not in new_species:
                                new_species.append(taxon_id)
                                LOGGER.info("=== NEW SPECIES FOR PROJECT ===")
                                new_species_count += 1
                                new_species_flag = True
                            print_obs(result)
                        else:
                            observations_add_failures += 1

                    #LOGGER.info("----------------------------------")

                page += 1
            else:
                done = True
                LOGGER.info("Observation response: %s", req_resp.text)

    LOGGER.info("\nNew Species: %d", new_species_count)
    LOGGER.info("New Species Added: %d", new_species_add)
    LOGGER.info("Observations Added: %d", observations_added)
    LOGGER.info("Observations Add Failures: %d", observations_add_failures)
    for a_taxon in taxon_response_count:
        LOGGER.info("Taxon: %s, total results: %d",
                    a_taxon, taxon_response_count[a_taxon])

    # Read results file into a buffer
    with open("results.log", "r") as results_file:
        results_buffer = results_file.read()

    # Send results to the following email addresses
    try:
        dummy_gmail_config = config['gmail.com']
        if send_gmail.send_email(config, LOGGER, results_buffer,
                                 subject="inat_add_objs2project results"):
            LOGGER.info("Email sent")
        else:
            LOGGER.error("Failed to send email")
    except KeyError:
        LOGGER.warning("gmail.com configuration not defined")


if __name__ == "__main__":
    sys.exit(main())
