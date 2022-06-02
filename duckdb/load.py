import sys
import os
import duckdb
import getopt
import logging
import timeit
from datetime import date
import multiprocessing

lane_limits = [16, 32, 64, 128, 256, 512, 1024]
threads = [2, 4, 6, 8]



def sort_results(result, timing_dict, params, query, sf, subquery, workload):
    output_file = open(f'output/results-{sf}-{subquery}-{workload}.csv', 'w')
    timing_output = open(f'output/timings-{sf}-{subquery}-{workload}.csv', 'w')
    timing_output.write(f"sf|q|parameters|time\n")

    filtered_param_headers = extract_headers(params)
    for idx, param in enumerate(params[1:]):
        param = param.strip().split("|")
        r = [r for r in result if str(r[-2]) == param[0] and str(r[-1]) == param[-1]]
        formatted_parameters = f"<{';'.join(str(parameter) for parameter in param)}>"
        formatted_output = []
        for entry in r:
            formatted_entry = f"<{','.join(str(result) for result in entry[:len(entry) - len(filtered_param_headers)])}>"
            formatted_output.append(formatted_entry)
        formatted_output_string = f"[{';'.join(entry for entry in formatted_output)}]"
        output_file.write(
            f"{query}|{subquery}|{formatted_parameters}|{formatted_output_string}\n")
        full_timing = timing_dict['precompute_timing'] + timing_dict['csr_timing'] + timing_dict['parameter_timing'][
            idx] + timing_dict['result_timing']

        timing_output.write(f"DuckDB|{sf}|{subquery}|{formatted_parameters}|{full_timing}\n")
    # for idx, row in result.iterrows():
    #     formatted_parameters = f"<{';'.join(str(parameter) for parameter in row[filtered_param_headers])}>"
    #     formatted_output = f"[<{','.join(str(result) for result in row.drop(labels=filtered_param_headers))}>]"
    #     output_file.write(
    #         f"{query}|{query}|{formatted_parameters}|{formatted_output}\n")
    # timing_output.write(f"DuckDB|{sf}|{query}|{formatted_parameters}|{timing_dict[idx]}\n")
    output_file.close()
    timing_output.close()


def extract_headers(params):
    param_headers = params[0]
    param_headers_formatted = param_headers.split("|")
    filtered_param_headers = [param.split(":")[0].lower() for param in param_headers_formatted]
    return filtered_param_headers


def run_script(con, filename, params=None, sf=None, lane=1024, thread=8):
    queries = open(filename).read().split(";")
    csr_timing = 0
    precompute_timing = 0
    parameter_timing = []
    total_timing = 0
    timing = 0
    path_timing = 0
    for query in queries:
        logging.debug(query)
        if "-- PRECOMPUTE" in query:
            start = timeit.default_timer()
            con.execute(query)
            stop = timeit.default_timer()
            timing = stop - start
            precompute_timing += timing
        elif "-- CSR CREATION" in query:
            start = timeit.default_timer()
            con.execute(query)
            stop = timeit.default_timer()
            timing = stop - start
            csr_timing += timing
        elif "-- PARAMS" in query:
            original_query = query
            filtered_param_headers = extract_headers(params)
            for line in params[1:]:
                custom_query = original_query
                line = line.strip("\n")
                split_line = line.split("|")
                for i in range(len(filtered_param_headers)):
                    custom_query = custom_query.replace(f":{filtered_param_headers[i]}", f"{split_line[i]}")
                logging.debug(f"Starting {line}")
                start = timeit.default_timer()

                con.execute(custom_query)
                stop = timeit.default_timer()

                timing = stop - start
                total_timing += timing

                parameter_timing.append(timing)
            timing = 0
        elif "-- RESULTS" in query:
            start = timeit.default_timer()
            final_result = con.execute(query).fetchall()
            stop = timeit.default_timer()
            timing = (stop - start)
            result_timing = timing
            total_timing += timing
            timing_dict = {"precompute_timing": precompute_timing, "csr_timing": csr_timing,
                           "average_parameter_timing": sum(parameter_timing) / len(parameter_timing),
                           "result_timing": result_timing, "total_timing": total_timing,
                           "parameter_timing": parameter_timing, "path_timing": path_timing}
            return final_result, timing_dict
        elif "-- DEBUG" in query:
            result = con.execute(query).fetchdf()
            logging.debug(result)
        elif "-- PRAGMA" in query:
            if "set_lane_limit" in query:
                query = query.replace(":param", str(lane))
            elif "threads" in query:
                query = query.replace(":param", str(thread))
            logging.debug(query)
            con.execute(query)
        elif "-- PATH" in query:
            start = timeit.default_timer()
            con.execute(query)
            stop = timeit.default_timer()
            timing = stop - start
            path_timing += timing
        else:
            start = timeit.default_timer()
            con.execute(query)
            stop = timeit.default_timer()
            timing = stop - start
        if timing == 0:
            logging.critical(f"TIMING WAS 0 for query: {query}")
        total_timing += timing
        logging.debug(total_timing)


def process_arguments(argv):
    sf = ''
    query = ''
    only_load = False
    workload = ''
    threads = multiprocessing.cpu_count()
    lanes = 1024
    experimental_mode = False
    try:
        opts, args = getopt.getopt(argv, "hs:q:l:w:a:t:e:",
                                   ["scalefactor=", "query=", "load=", "workload=", "lanes=", "threads=", "experiment="])
    except getopt.GetoptError:
        logging.info('load.py -s <scalefactor> -q <query> -l <load only> -w <workload> -a <lanes> -t <threads>')
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            logging.info(
                'load.py -s <scalefactor> -q <query> -l <load only database (1 or 0)> '
                '-w <workload (bi or interactive)> -a <number of lanes> -t <number of threads>')
            sys.exit()
        elif opt in ('-l', "--load"):
            only_load = bool(int(arg))
            if only_load:
                logging.info("Loading only the database")
        elif opt in ('-w', '--workload'):
            if arg == 'bi' or arg == 'interactive':
                workload = arg
            else:
                logging.critical("Unrecognized workload detected. Options are (bi, interactive)")
                sys.exit()
        elif opt in ("-s", "--scalefactor"):
            sf = arg
        elif opt in ("-a", "--lanes"):
            lanes = arg
        elif opt in ("-t", "--threads"):
            threads = arg
        elif opt in ("-q", "--query"):
            query = arg
        elif opt in ("-e", "--experiment"):
            experimental_mode = bool(int(arg))
    return sf, query, only_load, workload, lanes, threads, experimental_mode


def write_timing_dict(timing_dict, sf, query, workload, lane=1024, thread=8):
    filename = f'benchmark/timings.csv'
    if not os.path.exists(filename):
        with open(filename, 'w') as f:
            f.write(
                "sf|query|total_timing|result_timing|csr_timing|precompute_timing|average_parameter_timing|total_parameter_timing|path_timing|lanes|threads|workload|date|parameter_timing\n")

    today = date.today().strftime("%b-%d-%Y")
    with open(filename, 'a') as f:
        f.write(
            f"{sf}|{query}|{timing_dict['total_timing']}|{timing_dict['result_timing']}|{timing_dict['csr_timing']}|{timing_dict['precompute_timing']}|{timing_dict['average_parameter_timing']}|{sum(timing_dict['parameter_timing'])}|{timing_dict['path_timing']}|{lane}|{thread}|{workload}|{today}|{timing_dict['parameter_timing']}\n")


def main(argv):
    sf, query, only_load, workload, lanes, num_threads, experimental_mode = process_arguments(argv)
    file_location = validate_input(query, workload)
    if experimental_mode:
        for lane in lane_limits:
            for thread in threads:
                timing_dict, subquery = run_duckdb(file_location, lane, only_load, query, sf, thread, workload)
                write_timing_dict(timing_dict, sf, subquery, workload, lane, thread)
    else:
        run_duckdb(file_location, lanes, only_load, query, sf, num_threads, workload)


def run_duckdb(file_location, lanes, only_load, query, sf, threads, workload):
    con = duckdb.connect("snb_benchmark.duckdb", read_only=False)
    run_script(con, "ddl/drop-tables.sql")
    run_script(con, "ddl/schema-composite-merged-fk.sql")
    data_dir = f'../../ldbc_snb_datagen_spark/out-sf{sf}/graphs/csv/bi/composite-merged-fk'
    params = open(f'../parameters/parameters-sf{sf}/{workload}-{query}.csv').readlines()  # parameters-sf{sf}/
    load_entities(con, data_dir, query)
    if not only_load:
        subquery = query
        if query == '19a' or query == '19b':
            query = '19'

        result, timing_dict = run_script(con, file_location, params, sf, lanes, threads)
        sort_results(result, timing_dict, params, query, sf, subquery, workload)
        return timing_dict, subquery


def validate_input(query, workload):
    try:
        if query.isnumeric():
            assert (1 <= int(query) <= 20), "Invalid query number, should be in range (1,20)."
        else:
            assert (query == '19a' or query == '19b')
    except AssertionError as msg:
        logging.critical(msg)
        sys.exit(1)
    except ValueError as msg:
        logging.critical(msg)
        sys.exit(1)
    file_location = None
    if query == '19a' or query == '19b':
        file_location = f"queries/{workload}/q19.sql"
    else:
        file_location = f"queries/{workload}/q{query}.sql"
    try:
        open(file_location)
    except FileNotFoundError:
        logging.critical(f"File at {file_location} not found, possibly not implemented yet.")
        sys.exit(1)
    return file_location


def load_entities(con, data_dir: str, query: str):
    static_path = f"{data_dir}/initial_snapshot/static"
    dynamic_path = f"{data_dir}/initial_snapshot/dynamic"
    static_entities = ["Organisation", "Place", "Tag", "TagClass"]
    dynamic_entities = ["Comment", "Comment_hasTag_Tag", "Forum", "Forum_hasMember_Person", "Forum_hasTag_Tag",
                        "Person", "Person_hasInterest_Tag", "Person_knows_Person", "Person_likes_Comment",
                        "Person_likes_Post", "Person_studyAt_University", "Person_workAt_Company", "Post",
                        "Post_hasTag_Tag"]
    if query == "20":
        # Query 20
        static_entities = ["Organisation"]
        dynamic_entities = ["Person", "Person_knows_Person", "Person_studyAt_University", "Person_workAt_Company"]
    elif query == "19a" or query == "19b":
        # Query 19
        static_entities = ["Place"]
        dynamic_entities = ["Comment", "Person", "Person_knows_Person", "Post"]
    elif query == '13':
        # Query 13 Interactive
        static_entities = []
        dynamic_entities = ["Person", "Person_knows_Person"]
    logging.info("## Static entities")
    for entity in static_entities:
        for csv_file in [f for f in os.listdir(f"{static_path}/{entity}") if
                         f.startswith("part-") and (f.endswith(".csv") or f.endswith(".csv.gz"))]:
            csv_path = f"{entity}/{csv_file}"
            logging.debug(f"- {csv_path}")
            con.execute(
                f"COPY {entity} FROM '{data_dir}/initial_snapshot/static/{entity}/{csv_file}' (DELIMITER '|', HEADER, FORMAT csv)")
            logging.info("Loaded static entities.")
    logging.info("## Dynamic entities")
    for entity in dynamic_entities:
        for csv_file in [f for f in os.listdir(f"{dynamic_path}/{entity}") if
                         f.startswith("part-") and f.endswith(".csv")]:
            csv_path = f"{entity}/{csv_file}"
            logging.debug(f"- {csv_path}")
            con.execute(
                f"COPY {entity} FROM '{data_dir}/initial_snapshot/dynamic/{entity}/{csv_file}' (DELIMITER '|', HEADER, FORMAT csv)")
            if entity == "Person_knows_Person":
                con.execute(
                    f"COPY {entity} (creationDate, Person2id, Person1id) FROM '{data_dir}/initial_snapshot/dynamic/{entity}/{csv_file}' (DELIMITER '|', HEADER, FORMAT csv)")
    logging.info("Loaded dynamic entities.")
    logging.info("Load initial snapshot")


if __name__ == "__main__":
    logging.basicConfig(format='%(process)d-%(levelname)s-%(message)s', level=logging.DEBUG)
    main(sys.argv[1:])
