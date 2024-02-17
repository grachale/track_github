# GitHub Event Statistics Flask App

This Flask application collects and displays statistics on GitHub events for specified repositories. It includes functionalities to load configuration from a JSON file, establish a connection to a PostgreSQL database, retrieve GitHub events, and calculate statistics on the average time between events for every type of event.

## How to Run 
To run the script go to the `app/src` directory, provide it with a configuration file path as a command-line argument:

```bash
python main.py <config_file>
```

The configuration file should be in JSON format. It contains the necessary settings and information required for the app to run, such as PostgreSQL database information like host, user and name of database. (check an example - `app/configs/config.json`) Before starting the app, make sure that you have started provided database.

Example of usage (must be executed in the `app/src` directory):

```bash
python main.py ../configs/config.json
```

## Access the API Endpoints
   - Once the application is running, you can access the following endpoints:

     - **Statistics API Endpoint:**
       - Endpoint: `http://localhost:5000/statistics`
       - Method: GET

     - **Updating Data:**
       - Endpoint: `http://localhost:5000/update`
       - Method: GET

## Example of Usage

- Starting the app

![starting.png](images%2Fstarting.png)

- Simulating of accessing the API Endpoints with scripts from `app/helpers`

![using.png](images%2Fusing.png)