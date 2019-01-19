#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jan  1 13:57:09 2019

@author: Tom
"""
import smtplib
import configparser

def send_email(config_values, body, subject='Test email'):
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
        print("Sent Hello")
        server.starttls()
        server.login(config_values['gmail.com']['username'],
                     config_values['gmail.com']['password'])
        print("Logged in")
        server.sendmail(sent_from, send_to, email_text)
        print("Sent email")
        server.close()

        print('Email sent!')
        return True
    except smtplib.SMTPException as e_value:
        print('Something went wrong, %s', str(e_value))
        return False


if __name__ == "__main__":
    CONFIG = configparser.ConfigParser()
    CONFIG.read('inat_add_obs2project.ini')
    send_email(CONFIG, "Test body", subject="test subject")
