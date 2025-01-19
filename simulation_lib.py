import subprocess
import shutil
import os
import sqlite3
import pandas as pd

def write_workflow(weather_file, weather_id, seed_file, path_to_workflow, path_to_weather, base_path="."):
    array_of_strings = []
    with open(path_to_workflow, "r") as file:
        for line in file:
            if '  "weather_file"' in line.split(":"):
                array_of_strings.append(":".join([line.split(":")[0], f' "{path_to_weather}\\\\{weather_file}",\n']))

            elif '  "seed_file"' in line.split(":"):
                array_of_strings.append(":".join([line.split(":")[0], f'"archtype.osm",\n']))
            else:
                array_of_strings.append(line)

    dir_path = f"{base_path}\\\\simulation_results\\\\{weather_id}_{seed_file}"
    os.makedirs(dir_path, exist_ok=True)
    shutil.copy(f"{base_path}\\\\d_btap\\{seed_file}.osm", f"{dir_path}\\\\archtype.osm")
    path_writing = f"{dir_path}\\\\worflow.osw"
    with open(path_writing, "w") as file:
        # Write each string to the file on a new line
        file.writelines(array_of_strings)  # Add a newline character
    return path_writing


def solve(folder_name, software_path):
    # Path to the executable file
    # Arguments for the software
    arguments = [
        "run",
        "--workflow",
        folder_name,
    ]
    print(arguments)
    # Run the software with arguments
    result = subprocess.run([software_path] + arguments, capture_output=True, text=True, shell=True)
    return result

def query_eletricity(db_path):
    # Connect to the SQLite database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    print(db_path)

    # Query to fetch the entire dataset for "Electricity:Facility"
    query_full_data = """
    SELECT TimeIndex, Value 
    FROM ReportData 
    WHERE ReportDataDictionaryIndex IN (
        SELECT ReportDataDictionaryIndex 
        FROM ReportDataDictionary 
        WHERE Name = 'ElectricityNet:Facility'
    );
    """
    # Execute the query and fetch the data
    cursor.execute(query_full_data)
    full_data = cursor.fetchall()
    # Create a DataFrame from the data
    full_df = pd.DataFrame(full_data, columns=['TimeIndex', 'Value (Joules)'])
    cursor.close()
    return full_df

def query_eletricity(db_path):
    # Connect to the SQLite database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    print(db_path)

    # Query to fetch the entire dataset for "Electricity:Facility"
    query_full_data = """
    SELECT TimeIndex, Value 
    FROM ReportData 
    WHERE ReportDataDictionaryIndex IN (
        SELECT ReportDataDictionaryIndex 
        FROM ReportDataDictionary 
        WHERE Name = 'ElectricityNet:Facility'
    );
    """

    # Execute the query and fetch the data
    cursor.execute(query_full_data)
    full_data = cursor.fetchall()
    # Create a DataFrame from the data
    full_df = pd.DataFrame(full_data, columns=['TimeIndex', 'Value (Joules)'])
    cursor.close()
    return full_df

# Read CSV file into a DataFrame
def get_stations_data(weather_station_data,weather_folder, stations):
    df = pd.read_csv(weather_station_files)
    quebec_stations_reference = df[df["prov"] == "QC"]

    id_strings = np.array(quebec_stations_reference.loc[weather_zones]["climate_ID"])
    filenames = os.listdir(weather_folder)

    weather_file_paths = []
    for elements in filenames:
        mini_array = elements.split("_")
        for elem in id_strings:
            if elem in mini_array:
                weather_file_paths.append(("_".join(mini_array), elem))
    return weather_file_paths