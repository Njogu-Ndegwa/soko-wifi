# Base image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# Install pipenv
RUN pip install --no-cache-dir pipenv

# Copy only the Pipfile and Pipfile.lock first to leverage Docker caching
COPY Pipfile Pipfile.lock /app/

# Install dependencies
RUN pipenv install --system --deploy

# Copy the entire Django project into the container
COPY . /app/

# Expose the port the app runs on
EXPOSE 7000

# Run the Django development server
CMD ["python", "manage.py", "runserver", "0.0.0.0:7000"]
