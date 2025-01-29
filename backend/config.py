# Description: This file contains the configuration for the Flask app.
#Importing the required libraries
from dotenv import load_dotenv
import os
from flask_jwt_extended import JWTManager
from app import app
# import workers
import smtplib
from email.mime.multipart import MIMEMultipart, MIMEBase
from email.mime.text import MIMEText
from cache import cache
#Loading the environment variables
load_dotenv()

#Setting the configuration for the app
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = os.getenv('SQLALCHEMY_TRACK_MODIFICATIONS')
app.secret_key = os.getenv('SECRET_KEY')
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY') 
app.config['CELERY_BROKER_URL'] = os.getenv('CELERY_BROKER_URL')
app.config['CELERY_RESULT_BACKEND'] = os.getenv('CELERY_RESULT_BACKEND')
app.config['CACHE_TYPE'] = os.getenv('CACHE_TYPE')
app.config['CACHE_REDIS_URL'] = os.getenv('CACHE_REDIS_URL')
app.config['CACHE_DEFAULT_TIMEOUT'] = os.getenv('CACHE_DEFAULT_TIMEOUT')
app.config['REDIS_URL'] = os.getenv('REDIS_URL')
app.config['BROKER_URL'] = os.getenv('BROKER_URL')
app.config['RESULT_BACKEND'] = os.getenv('RESULT_BACKEND')
app.config['BROKER_CONNECTION_RETRY_ON_STARTUP'] = os.getenv('BROKER_CONNECTION_RETRY_ON_STARTUP')

SMTP_SERVER_HOST = 'localhost'
SMTP_SERVER_PORT = 1025
SENDER_ADDRESS = 'admin@ticket.com'
SENDER_PASSWORD = ''

def send_email(to, sub, html_content):
    message = MIMEMultipart()
    message["From"] = SENDER_ADDRESS
    message["To"] = to
    message["Subject"] = sub
    message.attach(MIMEText(html_content, 'html'))
    try:
        smtp = smtplib.SMTP(host = SMTP_SERVER_HOST, port = SMTP_SERVER_PORT)
        smtp.login(SENDER_ADDRESS, SENDER_PASSWORD)
        smtp.send_message(message)
        smtp.quit()
        return True
    except:
        return False
# Initialize JWT
jwt = JWTManager(app)

cache.init_app(app)

'''
import secrets

# Generate a random secret key with 140 characters
secret_key = secrets.token_hex(70)  

print(f"Random Secret Key: {secret_key}")

'''