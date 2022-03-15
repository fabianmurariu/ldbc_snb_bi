import psycopg2
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import sys
import os

def run_script(con, filename):
    with open(filename, "r") as f:
        queries_file = f.read()
        queries = queries_file.split(";")
        for query in queries:
            if query.isspace():
                continue
            #print(f"{query}")
            con.execute(query)

print("Datagen / apply batches using SQL")

data_dir = sf = os.environ.get("UMBRA_DATA_DIR")

insert_nodes = ["Comment", "Forum", "Person", "Post"]
insert_edges = ["Comment_hasTag_Tag", "Forum_hasMember_Person", "Forum_hasTag_Tag", "Person_hasInterest_Tag", "Person_knows_Person", "Person_likes_Comment", "Person_likes_Post", "Person_studyAt_University", "Person_workAt_Company",  "Post_hasTag_Tag"]
insert_entities = insert_nodes + insert_edges

# set the order of deletions to reflect the dependencies between node labels (:Comment)-[:REPLY_OF]->(:Post)<-[:CONTAINER_OF]-(:Forum)-[:HAS_MODERATOR]->(:Person)
delete_nodes = ["Comment", "Post", "Forum", "Person"]
delete_edges = ["Forum_hasMember_Person", "Person_knows_Person", "Person_likes_Comment", "Person_likes_Post"]
delete_entities = delete_nodes + delete_edges


pg_con = psycopg2.connect(database="ldbcsnb", host="localhost", user="postgres", password="mysecretpassword", port=8000)
con = pg_con.cursor()

run_script(con, f"ddl/schema-delete-candidates.sql");

network_start_date = date(2012, 9, 13)
network_end_date = date(2012, 12, 31)
# smaller range for testing
#network_end_date = date(2012, 9, 15)
batch_size = relativedelta(days=1)

batch_start_date = network_start_date
while batch_start_date < network_end_date:
    # format date to yyyy-mm-dd
    batch_id = batch_start_date.strftime('%Y-%m-%d')
    batch_dir = f"batch_id={batch_id}"
    print(f"#################### {batch_dir} ####################")

    print("## Inserts")
    for entity in insert_entities:
        batch_path = f"{data_dir}/inserts/dynamic/{entity}/{batch_dir}"
        if not os.path.exists(batch_path):
            continue

        print(f"--> {entity}:")
        for csv_file in [f for f in os.listdir(batch_path) if f.endswith(".csv")]:
            csv_path = f"{batch_path}/{csv_file}"
            print(f"- {csv_path}")
            con.execute(f"COPY {entity} FROM '/data/inserts/dynamic/{entity}/{batch_dir}/{csv_file}' (DELIMITER '|', HEADER, FORMAT csv)")
            pg_con.commit()

    print("## Deletes")
    # Deletes are implemented using a SQL script which use auxiliary tables.
    # Entities to be deleted are first put into {entity}_Delete_candidate tables.
    # These are cleaned up before running the delete script.
    for entity in delete_entities:
        #print(f"DELETE FROM {entity}_Delete_candidates");
        con.execute(f"DELETE FROM {entity}_Delete_candidates")
        # print(f"====> DROP TABLE IF EXISTS {entity}_Delete_candidates");
        # con.execute(f"DROP TABLE IF EXISTS {entity}_Delete_candidates")
        # print(f"====> recreate table {entity}_Delete_candidates")
        # if entity in delete_nodes:
        #     con.execute(f"CREATE TABLE {entity}_Delete_candidates(deletionDate timestamp with time zone not null, id bigint not null)")
        # else:
        #     con.execute(f"CREATE TABLE {entity}_Delete_candidates(deletionDate timestamp with time zone not null, src bigint not null, trg bigint not null)")

        batch_path = f"{data_dir}/deletes/dynamic/{entity}/{batch_dir}"
        if not os.path.exists(batch_path):
            continue

        print(f"--> {entity}:")
        for csv_file in [f for f in os.listdir(batch_path) if f.endswith(".csv")]:
            csv_path = f"{batch_path}/{csv_file}"
            print(f"> {csv_path}")
            con.execute(f"COPY {entity}_Delete_candidates FROM '/data/deletes/dynamic/{entity}/{batch_dir}/{csv_file}' (DELIMITER '|', HEADER, FORMAT csv)")
            pg_con.commit()

    print()
    print("<running delete script>")
    # Invoke delete script which makes use of the {entity}_Delete_candidates tables
    run_script(con, "dml/snb-deletes.sql")
    print("<finished delete script>")
    print()

    batch_start_date = batch_start_date + batch_size

con.close()
