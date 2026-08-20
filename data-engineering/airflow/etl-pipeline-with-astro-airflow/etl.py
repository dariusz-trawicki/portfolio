from airflow import DAG
from airflow.providers.http.operators.http import HttpOperator
from airflow.decorators import task
from airflow.providers.postgres.hooks.postgres import PostgresHook
import json
import pendulum

## Define the DAG
with DAG(
    dag_id='nasa_apod_postgres',
    start_date=pendulum.today("UTC").add(days=-1),
    schedule='@daily',
    catchup=False

) as dag:

    ## Step 1: Create the table if it doesn't exist
    @task
    def create_table():
        
        ## initialize the Postgreshook
        postgres_hook=PostgresHook(postgres_conn_id="my_postgres_connection")

        ## SQL query to create the table
        create_table_query="""
        CREATE TABLE IF NOT EXISTS apod_data (
            id SERIAL PRIMARY KEY,
            title VARCHAR(255),
            explanation TEXT,
            url TEXT,
            date DATE,
            media_type VARCHAR(50)
        );
        """

        ## Execute the table creation query
        postgres_hook.run(create_table_query)


    ## Step 2: Extract the NASA API Data(APOD) - Astronomy Picture of the Day[Extract pipeline]
    extract_apod = HttpOperator(
        task_id="extract_apod",
        http_conn_id="nasa_api", # connection id with Airflow Connections
        endpoint="planetary/apod",
        method="GET",
        data={"api_key": "{{ conn.nasa_api.extra_dejson.api_key }}"}, 
        response_filter=lambda response: response.json(),
        log_response=True,
    )


    ## Step 3: Transform the data
    @task
    def transform_apod_data(response):
        apod_data={
            'title': response.get('title', ''),
            'explanation': response.get('explanation', ''),
            'url': response.get('url', ''),
            'date': response.get('date', ''),
            'media_type': response.get('media_type', '')

        }
        return apod_data

    ## Step 4:  Load the data into Postgres SQL
    @task
    def load_data_to_postgres(apod_data):

        # Initialize the PostgresHook
        postgres_hook=PostgresHook(postgres_conn_id='my_postgres_connection')

        ## Define the SQL Insert Query
        insert_query = """
        INSERT INTO apod_data (title, explanation, url, date, media_type)
        VALUES (%s, %s, %s, %s, %s);
        """

        ## Execute the SQL Query
        postgres_hook.run(insert_query,parameters=(
            apod_data['title'],
            apod_data['explanation'],
            apod_data['url'],
            apod_data['date'],
            apod_data['media_type']
        ))

    ## step 5: Define the task dependencies
    
    ## Extract data from NASA APOD API:
    create_table() >> extract_apod  ## Ensure the table is create befor extraction
    api_response=extract_apod.output
    
    ## Transform data:
    transformed_data=transform_apod_data(api_response)
    
    ## Load data into Postgres:
    load_data_to_postgres(transformed_data)
