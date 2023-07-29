# Use the official Python image as the base image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the bot script and other necessary files to the container
COPY bot.py .
COPY requirements.txt .

# Install the required Python packages
RUN pip install -r requirements.txt

# Start the bot
CMD ["python", "bot.py"]
