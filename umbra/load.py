import psycopg2
import sys
import os
import re
import time
import argparse


parser = argparse.ArgumentParser()
parser.add_argument('--data_dir', type=str, help='Directory with the initial_snapshot, insert, and delete directories', required=True)
parser.add_argument('--local', type=bool, help='Local run (outside of a container)', required=False)
args = parser.parse_args()
data_dir = args.data_dir
local = args.local


pg_con = psycopg2.connect(host="localhost", user="postgres", password="mysecretpassword", port=8000)
pg_con.autocommit = True
cur = pg_con.cursor()

def run_script(pg_con, cur, filename):
    with open(filename, "r") as f:
        queries_file = f.read()
        # strip comments
        queries_file = re.sub(r"\n--.*", "", queries_file)
        queries = queries_file.split(";")
        for query in queries:
            if query.isspace():
                continue

            sql_statement = re.findall(r"^((CREATE|INSERT|DROP|DELETE|SELECT|COPY|UPDATE|ALTER) [A-Za-z0-9_ ]*)", query, re.MULTILINE)
            print(f"{sql_statement[0][0].strip()} ...")
            start = time.time()
            cur.execute(query)
            pg_con.commit()
            end = time.time()
            duration = end - start
            print(f"-> {duration:.4f} seconds")

run_script(pg_con, cur, "ddl/drop-tables.sql")
run_script(pg_con, cur, "ddl/schema-composite-merged-fk.sql")
run_script(pg_con, cur, "ddl/schema-delete-candidates.sql")

print("Load initial snapshot")

# initial snapshot
static_path = f"{data_dir}/initial_snapshot/static"
dynamic_path = f"{data_dir}/initial_snapshot/dynamic"
static_entities = ["Organisation", "Place", "Tag", "TagClass"]
dynamic_entities = ["Comment", "Comment_hasTag_Tag", "Forum", "Forum_hasMember_Person", "Forum_hasTag_Tag", "Person", "Person_hasInterest_Tag", "Person_knows_Person", "Person_likes_Comment", "Person_likes_Post", "Person_studyAt_University", "Person_workAt_Company", "Post", "Post_hasTag_Tag"]

if local:
    dbs_data_dir = data_dir
else:
    dbs_data_dir = '/data'

print("## Static entities")
for entity in static_entities:
    for csv_file in [f for f in os.listdir(f"{static_path}/{entity}") if f.startswith("part-") and f.endswith(".csv")]:
        csv_path = f"{entity}/{csv_file}"
        print(f"- {csv_path}")
        #print(f"- {csv_path}", end='\r')
        cur.execute(f"COPY {entity} FROM '{dbs_data_dir}/initial_snapshot/static/{entity}/{csv_file}' (DELIMITER '|', HEADER, NULL '', FORMAT text)")
        #print(" " * 120, end='\r')
        pg_con.commit()
print("Loaded static entities.")

print("## Dynamic entities")
for entity in dynamic_entities:
    for csv_file in [f for f in os.listdir(f"{dynamic_path}/{entity}") if f.startswith("part-") and f.endswith(".csv")]:
        csv_path = f"{entity}/{csv_file}"
        print(f"- {csv_path}")
        #print(f"- {csv_path}", end='\r')
        cur.execute(f"COPY {entity} FROM '{dbs_data_dir}/initial_snapshot/dynamic/{entity}/{csv_file}' (DELIMITER '|', HEADER, NULL '', FORMAT text)")
        if entity == "Person_knows_Person":
            cur.execute(f"COPY {entity} (creationDate, Person2id, Person1id) FROM '{dbs_data_dir}/initial_snapshot/dynamic/{entity}/{csv_file}' (DELIMITER '|', HEADER, NULL '', FORMAT text)")
        #print(" " * 120, end='\r')
        pg_con.commit()
print("Loaded dynamic entities.")

print("Maintain materialized views . . . ")
run_script(pg_con, cur, "dml/maintain-views.sql")
print("Done.")

print("Create static materialized views . . . ")
run_script(pg_con, cur, "dml/create-static-materialized-views.sql")
print("Done.")

print("Apply precomputation . . . ")
run_script(pg_con, cur, "dml/precomp/bi-4.sql")
run_script(pg_con, cur, "dml/precomp/bi-6.sql")
run_script(pg_con, cur, "dml/precomp/bi-19.sql")
run_script(pg_con, cur, "dml/precomp/bi-20.sql")
print("Done.")

print("Loaded initial snapshot to Umbra.")
