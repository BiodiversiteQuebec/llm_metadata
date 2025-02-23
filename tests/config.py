import os
import pathlib
from dotenv import load_dotenv

# Set the path to the project root
PROJECT_ROOT = pathlib.Path(__file__).parent

# Load the .env file
load_dotenv()