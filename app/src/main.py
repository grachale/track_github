"""
This module implements a Flask application for collecting and displaying statistics
on GitHub events for specified repositories.

Imports are organized according to PEP 8 guidelines. The main functionalities include:
- Loading configuration from a JSON file specified as a command-line argument.
- Establishing a connection to a PostgreSQL database.
- Retrieving GitHub events for specified repositories and updating the database.
- Calculating and displaying statistics on average time between events.

Usage:
    python main.py <config_file>

Author: Aleksei Grachev
"""
import json
import sys
from datetime import datetime
from collections import defaultdict

import psycopg2
import requests
from flask import Flask, jsonify

GITHUB_API_URL = 'https://api.github.com/repos/{owner}/{repo}/events'
TIMEOUT = 10
PORT = 5000


def date_transform_to(date, delta):
    """
    Transform a timedelta object to the specified time unit.

    Args:
        date (timedelta): The timedelta object to transform.
        delta (str): The desired time unit ('second', 'minute', 'hour').

    Returns:
        float: Transformed time value.

    Raises:
        Exception: If an invalid delta is provided.
    """
    if delta == 'second':
        return date.total_seconds()
    if delta == 'minute':
        return date.total_seconds() / 60
    if delta == 'hour':
        return date.total_seconds() / 3600

    raise Exception(f"Not existed delta provided in {sys.argv[1]}")


def load_config(path):
    """
        Load configuration data from a JSON file.

        Parameters:
        - path (str): The path to the JSON configuration file.

        Returns:
        - dict: A dictionary containing the configuration data.

        Raises:
        - FileNotFoundError: If the specified configuration file is not found.
        - json.JSONDecodeError: If there is an issue parsing the JSON data.

        The function attempts to open and read the specified JSON file at the given path.
        If successful, it parses the JSON content and returns the configuration data as a dictionary.
        """
    try:
        with open(path, encoding='utf-8') as config_file:
            config_data = json.load(config_file)
        return config_data
    except FileNotFoundError:
        print(f"Error: Configuration file '{path}' not found.")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Unable to parse JSON in '{path}'.")
        sys.exit(1)


# Checking number of arguments
if len(sys.argv) != 2:
    print("Usage: python main.py <config_file>")
    sys.exit(1)

# getting configuration from the inputted as CLI parameter json file
config_path = sys.argv[1]
config = load_config(config_path)

app = Flask(__name__)

# Establish a connection to the database
conn = psycopg2.connect(dbname=config.get('database'), user=config.get('user'), host=config.get('host'))
# Create a cursor object to execute SQL queries
cur = conn.cursor()

repositories = config.get('repositories')

if len(repositories) > 5:
    print("Server does not support more than 5 repositories.")
    sys.exit(1)


def get_github_events(owner, repo):
    """
    Retrieve GitHub events for a specified repository.

    Args:
        owner (str): The owner of the GitHub repository.
        repo (str): The name of the GitHub repository.

    Returns:
        dict: A dictionary representing the JSON response containing GitHub events.

    Raises:
        requests.exceptions.RequestException: If an error occurs during the HTTP request.
        ValueError: If the response is not in JSON format.
    """
    try:
        response = requests.get(GITHUB_API_URL.format(owner=owner, repo=repo), timeout=TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as ex:
        raise ex
    except ValueError as ve:
        raise ValueError("Invalid JSON format in the response from GitHub.") from ve


def calculate_average_time(events):
    """
    Calculate the average time between events for each event type.

    Args:
        events (list): A list of events, where each event is represented as a tuple with at least
                       two elements: event type and event timestamp.

    Returns:
        dict: A dictionary containing event types as keys and their corresponding average time
              between events as values.
    """
    # Check is it is not empty
    if not events:
        return None

    # Getting type and date of event
    timestamps = [(event[4], event[3]) for event in events]
    # Creating dictionary (key - type, value - List of dates)
    type_times = defaultdict(list)
    for timestamp in timestamps:
        type_times[timestamp[0]].append(timestamp[1])

    result = {}
    for typ, times in type_times.items():
        if len(times) < 2:
            result[typ] = 0
        else:
            deltas = [times[i] - times[i - 1] for i in range(1, len(times))]
            sum_of_deltas = sum(map(lambda x: date_transform_to(x, config.get('delta')), deltas))
            average_time = sum_of_deltas / (len(times) - 1)
            result[typ] = round(average_time, 3)

    return result


def get_db_statistics(owner, repo):
    """
       Retrieve GitHub events from a database and calculate the average time between events for each type.

       Args:
           owner (str): The owner of the GitHub repository.
           repo (str): The name of the GitHub repository.

       Returns:
           dict: A dictionary containing event types as keys and their corresponding average time
                 between events as values.
       """
    cur.execute(
        f"SELECT * FROM github_events "
        f"WHERE owner = '{owner}' AND repo = '{repo}' ORDER BY event_timestamp ASC;"
    )
    events = cur.fetchall()
    return calculate_average_time(events)


@app.route('/statistics')
def get_api_statistics():
    """
    Retrieve and expose GitHub event statistics as a JSON API endpoint.

    Returns:
        Response: A JSON-formatted response containing statistics on the average time between
                  events for each event type, organized by repository.

    """
    result = defaultdict(dict)

    for repository in repositories:
        owner = repository['owner']
        repo = repository['repo']
        statistics = get_db_statistics(owner, repo)
        # no events for repository
        if not statistics:
            result[repo] = {}
            continue

        for typ, average_time in statistics.items():
            result[repo][typ] = average_time

    return jsonify(result)


@app.route('/update')
def update_data():
    """
    Update the database with the latest 500 GitHub events for specified repositories.

    Returns:
        str: A message indicating that the data have been updated.
    """
    cur.execute("DROP TABLE github_events;")
    conn.commit()
    create_events_table()

    # Number of rows in the table
    current_count = 0

    for repository in repositories:
        events = get_github_events(repository['owner'], repository['repo'])
        if events:
            for event in events:
                # Check if the event is older than 7 days, if so, we do not need it
                event_datetime = datetime.strptime(event['created_at'], '%Y-%m-%dT%H:%M:%SZ')
                time_difference = datetime.now() - event_datetime
                if time_difference.days > 7:
                    continue

                # Check if the count exceeds 500
                if current_count >= 500:
                    # Delete the oldest row from the db
                    cur.execute(
                        "DELETE FROM github_events "
                        "WHERE event_timestamp = ("
                        "   SELECT event_timestamp FROM github_events "
                        "   ORDER BY event_timestamp ASC LIMIT 1"
                        ") LIMIT 1;"
                    )
                    current_count -= 1
                    conn.commit()

                current_count += 1
                cur.execute(
                    f"INSERT INTO github_events (owner, repo, event_timestamp, type) "
                    f"VALUES ('{repository['owner']}', '{repository['repo']}', '{event_datetime}', '{event['type']}')"
                )
                conn.commit()
    return "Data were updated."


def create_events_table():
    """
    Create the 'github_events' table in the database if it does not already exist.
    """
    cur.execute("""
    CREATE TABLE IF NOT EXISTS github_events (
        id SERIAL PRIMARY KEY,
        owner VARCHAR(255),
        repo VARCHAR(255),
        event_timestamp TIMESTAMP,
        type VARCHAR(255)
    );
    """)
    conn.commit()


if __name__ == '__main__':
    try:
        create_events_table()
        app.run(debug=True, port=PORT)
    except Exception as e:
        print(f"An exception occurred: {e}")
