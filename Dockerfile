# Use an official Python runtime as a parent image.
# Using python:3.9-slim is a best practice as it creates smaller container images
# than -bullseye, leading to faster deployments and lower storage costs.
FROM python:3.9-slim

# Allow statements and log messages to be sent straight to the logs
# without being buffered.
ENV PYTHONUNBUFFERED TRUE

# Set the working directory inside the container.
WORKDIR /app

# The psycopg2 library has C dependencies, so we need to install build-essential
# which contains the necessary compilers (like gcc).
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

# Copy the requirements file first to take advantage of Docker's layer caching.
# The pip install step will only be re-run if this file changes.
COPY requirements.txt .

# --- DEBUGGING STEP ---
# Print the contents of requirements.txt to the build log.
RUN echo "--- Contents of requirements.txt ---" && cat requirements.txt && echo "------------------------------------"

# Install the dependencies from your requirements.txt file.
RUN pip install --no-cache-dir -r requirements.txt

# --- DEBUGGING STEP ---
# Print the list of installed packages to the build log.
RUN echo "--- Installed packages ---" && pip freeze && echo "--------------------------"

# Copy the rest of your application's code into the container.
COPY . .

# Define the command that will be run when the container starts.
# The PORT environment variable is automatically set by Cloud Run.
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 wsgi:app