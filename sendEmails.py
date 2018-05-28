#!/bin/env python
# sendEmails.py Lew Cohen 11/10/2015
# Send automated emails to a list of recipients
# NOTE: It is important to send your email/text through a reputable server. If not, your email will likely
# get spam filtered, or your text will not be delivered. A server on your local machine is not advised.
# one solution is to send from a mail relay

import smtplib
import datetime
import sys

USE_AUTH = 0 # Set to 1 for authentication and TLS
# Port 25 is normal SMTP, port 587 is TLS
mailserver = "9.3.6.0" # Relay From Charles
sender = "alerts_noreply@ingenu.com" # NOTE: sender can be different than the email of the username you log in with
#username = "your_user_name@your_domain.com"
#paswd = "your_password"

def formatMessage(sender_addr, recipient_addr, subject, message):
   message_body = 'From: %s\r\nTo: %s\r\nSubject: %s\r\n\r\n%s' %(sender_addr, recipient_addr, subject, message)
   return message_body

# This Sends an Email, using Authentication to log in to the Email Server
def sendEmail(recipient, subject, message_contents):
   try:
      s = smtplib.SMTP(mailserver)
      res = s.ehlo()
      print res
      if USE_AUTH:
         res = s.starttls() # If 'STARTTLS is not supported' try using port 587 not 25 on mailserver
         res = s.login(username, paswd)

      message_body = formatMessage(sender, recipient, subject, message_contents)
      res = s.sendmail(sender, recipient, message_body)
      res = s.quit()
      print 'sendEmail.py: sent mail message', message_body, ' to', recipient, ' at ', datetime.datetime.now()
   except:
      print 'ERROR: sendEmail.py exception: ', sys.exc_info()[0] 
      print 'sendEmail.py: cant send mail to recipient: ', recipient, datetime.datetime.now()

# Recipients is a list of email addresses (['lew.cohen@ingenu.com','somebody@yahoo.com', etc])
# For Robustness and simplicity, we send a separate mail to each recipient
def sendEmails(recipients, subject, message_contents):
   for recipient in recipients:
      sendEmail(recipient, subject, message_contents)

if __name__ == '__main__':
   sendEmails(['8585551212@vtext.com'], 'Alarm: Set', 'Example text: Alarm8 voltage too high!')
