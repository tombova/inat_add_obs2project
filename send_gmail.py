#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jan  1 13:57:09 2019

@author: Tom
"""
import smtplib
import configparser
import logging

def send_email(config_values, logger, body, subject='Test email'):
    ''' Send an email from a python script '''

    try:
        sent_from = config_values['gmail.com']['username']
        send_to = config_values['gmail.com']['destination_email'].split(',')
    except KeyError:
        return False
    email_text = "From: %s\r\n" \
                "To: %s\r\n" \
                "Subject: %s\r\n" \
                "\r\n" \
                "%s\n\r" % \
                (sent_from, ", ".join(send_to), subject, body)

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.ehlo()
        logger.debug("Sent Hello")
        server.starttls()
        server.login(config_values['gmail.com']['username'],
                     config_values['gmail.com']['password'])
        logger.debug("Logged in")
        server.sendmail(sent_from, send_to, email_text)
        logger.info("Sent email")
        server.close()
        return True
    except smtplib.SMTPException as e_value:
        logger.error('Something went wrong, %s', str(e_value))
        return False


if __name__ == "__main__":
    CONFIG = configparser.ConfigParser()
    CONFIG.read('inat_add_obs2project.ini')
    LOGGER = logging.getLogger()

    LOG_FORMATTER = logging.Formatter("[%(levelname)-5.5s]  %(message)s")
    CONSOLE_HANDLER = logging.StreamHandler()
    CONSOLE_HANDLER.setFormatter(LOG_FORMATTER)
    LOGGER.addHandler(CONSOLE_HANDLER)
    LOGGER.setLevel(CONFIG['DEFAULT']['loggingLevel'])


    send_email(CONFIG, LOGGER, "Test body", subject="test subject")
