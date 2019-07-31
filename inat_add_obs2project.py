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
import pprint
from datetime import datetime
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

# pylint: disable=too-many-locals,too-many-statements
def get_project(project_id, config):
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
            LOGGER.debug("Number of rules: %d",
                         len(result['project_observation_rules']))
            LOGGER.info("Taxon Rules:")
            for a_rule in result['project_observation_rules']:
                if a_rule['operand_type'] == 'Taxon':
                    taxon = a_rule['taxon']
                    LOGGER.info("  Taxon: %s", taxon['name'])
            LOGGER.info("----------------------------------")
    else:
        return project_species

    prev_observation_count = config.getint('last run', 'observation_count', fallback=0)

    get_url = '%sobservations?project_id=%s' % (INAT_NODE_API_BASE_URL, project_id)
    get_req = requests.get(get_url)
    #LOGGER.info("GET project request status code: %d", get_req.status_code)
    #LOGGER.info("GET project request response: '%s'", get_req.text)
    if get_req.status_code == 200:
        response_data = json.loads(get_req.text)
        observation_count = int(response_data['total_results'])
        LOGGER.debug(pprint.pformat(response_data))
        LOGGER.info("Project %s observation count: %d, previously: %d",
                    project_id, observation_count, prev_observation_count)
    else:
        LOGGER.info("GET failed, status = %d", get_req.status_code)

    prev_species_count = config.getint('last run', 'species_count', fallback=0)
    LOGGER.info("\nGet project stats for %s", project_id)
    get_stats_url = '%sobservations/species_counts' \
                    '?project_id=%s&place_id=any' \
                    '&verifiable=any&captive=any' % \
                    (INAT_NODE_API_BASE_URL, project_id)
    get_stats_req = requests.get(get_stats_url)
    if get_stats_req.status_code == 200:
        response_data = json.loads(get_stats_req.text)
        LOGGER.debug(pprint.pformat(response_data))
        species_count = int(response_data['total_results'])
        LOGGER.info("\nTotal species: %d, previous: %d\n------------",
                    species_count, prev_species_count)
        results = response_data['results']
        for a_result in results:
            try:
                rank = a_result['taxon']['rank']
            except KeyError:
                rank = '<none>'
            taxon = a_result['taxon']['iconic_taxon_name']
            if config.getboolean('inaturalist.org', 'showspecies'):
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
        LOGGER.error("Stats request '%s' failed: %d", get_stats_url,
                     get_stats_req.status_code)

    # Save counts to config file
    config['last run']['species_count'] = str(species_count)
    config['last run']['observation_count'] = str(observation_count)

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
        LOGGER.debug("add_ob_2_proj_v1 POST successful")
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
        LOGGER.debug("add_ob_2_proj POST successful")
        return True

    LOGGER.error("POST request status code: %d", post_req.status_code)
    response_data = json.loads(post_req.text)
    for error in response_data['errors']:
        LOGGER.error("POST request response: '%s'", error)

    return False

def _build_auth_header(access_token: str) -> Dict[str, str]:
    ''' This function takes the access_token and creates the Authorization
        header needed by the non-V1 interface'''

    return {"Authorization": "Bearer %s" % access_token}



LOG_FILE_NAME = "/tmp/results.log"
with open(LOG_FILE_NAME, "w"):
    pass

LOG_FORMATTER = logging.Formatter("%(asctime)s [%(threadName)-12.12s]"
                                  " [%(levelname)-5.5s] %(message)s")
LOGGER = logging.getLogger()

FILE_HANDLER = logging.FileHandler("{0}".format(LOG_FILE_NAME))
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


# pylint: disable=too-many-branches
def search_new_obs(config, project_id, project_species):
    ''' Search for new observations for project '''

    place_id = config['inaturalist.org']['place_id']
    place_name = get_place_name(place_id)
    if place_name is None:
        LOGGER.error("Failed to find place id: '%s'", place_id)
        sys.exit(6)

    taxon_list = [x.strip() for x in config['inaturalist.org']['taxon_list'].split(',')]
    taxon_response_count = {}
    # As we find new species, put in this list
    new_species = []
    new_species_count = 0
    new_species_add = 0
    observations_added = 0
    observations_add_failures = 0

    # Get token information to access iNaturalist.org from config file
    try:
        access_token = get_access_token(config['inaturalist.org']['username'],
                                        config['inaturalist.org']['password'],
                                        config['inaturalist.org']['app_id'],
                                        config['inaturalist.org']['app_secret'])
    except KeyError:
        config_filename = config.get('DEFAULT', 'config_filename')
        LOGGER.warning("Need to define username, password, app_id, and "
                       "app_secret in [inaturalist.org] section of "
                       "configuration file: %s",
                       config_filename)
        sys.exit(7)

    excluded_observations = [x.strip() for x in \
                             config['last run']['excluded_observations'].split(',')]

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
        page_size = 100
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


            LOGGER.info("Observation Request Status: %d", req_resp.status_code)

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
                    if str(result['id']) in excluded_observations:
                        continue

                    new_species_flag = True
                    # Try to add observation to project using access_token for
                    # authentication

                    add_obs_flag = config.getboolean('inaturalist.org',
                                                     'addobservations')
                    if add_obs_flag:
                        if  add_ob_2_proj(result['id'],
                                          project_id,
                                          access_token):
                            if new_species_flag:
                                new_species_add += 1
                            observations_added += 1
                        else:
                            observations_add_failures += 1
                            excluded_observations.append(str(result['id']))
                            continue

                    # If taxon ID is not in list of species already in
                    # project and not is list of new species we have
                    # already found
                    # print banner, increment counter, and set flag
                    new_species_flag = False
                    taxon_id = result['taxon']['id']
                    if taxon_id not in project_species and \
                       taxon_id not in new_species:
                        new_species.append(taxon_id)
                        LOGGER.info("=== NEW SPECIES FOR PROJECT, %d ===", taxon_id)
                        new_species_flag = True
                        print_obs(result)
                    else:
                        print_obs(result)

                page += 1
            else:
                done = True
                LOGGER.info("Observation response: %s", req_resp.text)

    for a_taxon in taxon_response_count:
        LOGGER.info("Taxon: %s, total results: %d",
                    a_taxon, taxon_response_count[a_taxon])

    if add_obs_flag:
        # Get some project information and a list of current species
        project_species = get_project(project_id, config)

        LOGGER.info("\nNew Species: %d", new_species_count)
        LOGGER.info("New Species Added: %d", new_species_add)
        LOGGER.info("Observations Added: %d", observations_added)
        LOGGER.info("Observations Add Failures: %d", observations_add_failures)

    # Save excluded observations for next time
    config['last run']['excluded_observations'] = ",".join(excluded_observations)

    return new_species

############################################
# Main program                             #
############################################
# pylint: disable=too-many-statements,too-many-branches,too-many-locals
def main():
    ''' Main function '''

    config = configparser.ConfigParser()
    config['DEFAULT'] = {'loggingLevel': 'INFO'}
    config['inaturalist.org'] = {'addobservations': True}
    config['inaturalist.org'] = {'showspecies': True}
    config['inaturalist.org'] = {'searchnew': True}
    config['gmail.com'] = {'send_email': False}
    config['last run'] = {'excluded_observations': ''}
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
    config['DEFAULT']['config_filename'] = config_filename

    LOGGER.setLevel(config['DEFAULT']['loggingLevel'])

    LOGGER.info("Adding observations: %s",
                str(config.getboolean('inaturalist.org', 'addobservations')))
    LOGGER.info("Show species: %s",
                str(config.getboolean('inaturalist.org', 'showspecies')))

    now = datetime.utcnow()

    try:
        last_run = config['last run']['timestamp']
        LOGGER.info("This configuration file last run at: '%s'", last_run)
    except KeyError:
        LOGGER.info("This configuration file has not been used before")

    # Update timestamp
    config['last run']['timestamp'] = str(now)


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
    project_species = get_project(project_id, config)

    if project_species is None:
        LOGGER.warning("Failed to get species list ")
        return 4


    # These are some variables used for counting things and keeping track
    # of states
    search_new = config.getboolean('inaturalist.org',
                                   'searchnew')


    if search_new:
        new_species = search_new_obs(config, project_id, project_species)

    # Read results file into a buffer
    with open(LOG_FILE_NAME, "r") as results_file:
        results_buffer = results_file.read()

    # Send results to the following email addresses
    if config.getboolean('gmail.com',
                         'send_email'):
        try:
            dummy_gmail_config = config['gmail.com']
            if send_gmail.send_email(config, LOGGER, results_buffer,
                                     subject="inat_add_obs2project results"):
                LOGGER.info("Email sent")
            else:
                LOGGER.error("Failed to send email")
        except KeyError:
            LOGGER.warning("gmail.com configuration not defined")


    # Write possibly update to configuration file
    config_filename = config.get('DEFAULT', 'config_filename')
    try:
        with open(config_filename, 'w') as config_file:
            config.write(config_file)
    except OSError:
        LOGGER.error("Failed to write config file, '%s'", config_filename)

    return 0


if __name__ == "__main__":
    sys.exit(main())
