# Description: This file is the main file for the application. It imports all the other files and runs the application.
# Importing the required libraries
from flask import Flask
from workers import make_celery
from flask_cors import CORS

# Creating the app variable
app = Flask(__name__)

# Importing the config file, models and routes file
import config 
import models
import routes

# Initialize Celery here
celery = make_celery(app)
CORS(app)
from tasks import daily_reminder, monthly_report