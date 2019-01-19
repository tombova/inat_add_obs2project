#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jan  1 13:57:09 2019

@author: Tom
"""
import smtplib
import configparser

def send_email(config, body, subject='Test email'):
    ''' Send an email from a python script '''

    sent_from = config['gmail.com']['username']  
    send_to = config['gmail.com']['destination_email'].split(',')
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
        server.login(config['gmail.com']['username'], 
                     config['gmail.com']['password'])
        print("Logged in")
        server.sendmail(sent_from, send_to, email_text)
        print("Sent email")
        server.close()

        print('Email sent!')
    except Exception:  
        print ('Something went wrong, %s', Exception)


if __name__ == "__main__":
    config = configparser.ConfigParser()
    config.read('inat_add_obs2project.ini')
    send_email(config, "Test body", subject="test subject")
