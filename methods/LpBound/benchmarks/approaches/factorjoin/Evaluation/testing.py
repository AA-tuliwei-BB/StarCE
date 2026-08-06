import pickle
import time
import numpy as np
import os
import sys

def test_on_stats(model_path, query_file, save_res=None):
	with open(model_path, "rb") as f:
		bound_ensemble = pickle.load(f)

	with open(query_file, "r") as f:
		queries = f.readlines()

	#qerror = []
	latency = []
	pred = []
	log_file = "checkpoints/timing.txt"
	with open(log_file, "w") as f:
		f.write("query_id,estimate,runtime\n")
  
	for i, query_str in enumerate(queries):
		query = query_str.split("||")[0][:-1]
		print(query)
		#true_card = int(query_str.split("||")[-1])
		t = time.time()
		res = bound_ensemble.get_cardinality_bound_one(query)
		pred.append(res)
		latency.append(time.time() - t)
		with open(log_file, "a") as f:
			f.write(f"{i},{res},{latency[-1]}\n")
		#qerror.append(max(res/true_card, true_card/res))

	#qerror = np.asarray(qerror)
	#for i in [50, 90, 95, 99, 100]:
	#	print(f"q-error {i}% percentile is {np.percentile(qerror, i)}")
	print(f"average latency per query is {np.mean(latency)}")
	print(f"total estimation time is {np.sum(latency)}")

	if save_res:
		with open(save_res, "w") as f:
			for p in pred:
				f.write(str(p) + "\n")

def get_job_sub_plan_queires(query_folder):
	"""
	This is a helper function for extracting the sub-plan query string from the postgres analyzed results.
	More details on how to derive the "job_sub_plan_queries.txt" can be found at:
	https://github.com/Nathaniel-Han/End-to-End-CardEst-Benchmark#how-to-generate-sub-plan-queries
	"""
	with open(os.path.join(query_folder, "job_sub_plan_queries.txt"), "r") as f:
		sub_plan_queries = f.read()
	psql_raw = sub_plan_queries.split("query: 0")[1:]
	queries = []
	q_file_names = []

	for file in os.listdir(query_folder):
		if file.endswith(".sql") and file[0].isnumeric():
			q_file_names.append(file.split(".sql")[0] + ".pkl")
			with open(query_folder + file, "r") as f:
				q = f.readline()
				queries.append(q)

	psql_raw = sub_plan_queries.split("query: 0")[1:]
	sub_plan_queries_str_all = []
	for per_query in psql_raw:
		sub_plan_queries = []
		sub_plan_queries_str = []
		num_sub_plan_queries = len(per_query.split("query: "))
		all_info = per_query.split("RELOPTINFO (")[1:]
		assert num_sub_plan_queries * 2 == len(all_info)
		for i in range(num_sub_plan_queries):
			idx = i * 2
			table1 = all_info[idx].split("): rows=")[0]
			table2 = all_info[idx + 1].split("): rows=")[0]
			table_str = (table1, table2)
			sub_plan_queries_str.append(table_str)
		sub_plan_queries_str_all.append(sub_plan_queries_str)

	all_queries = dict()
	all_sub_plan_queries_str = dict()
	for i in range(len(q_file_names)):
		name = q_file_names[i].split(".pkl")[0]
		all_queries[name] = queries[i]
		all_sub_plan_queries_str[name] = sub_plan_queries_str_all[i]

	return all_queries, all_sub_plan_queries_str


def test_on_imdb(model_path, query_folder=None, derived_query_file=None, SPERCENTAGE=None, query_sample_location=None,
				 save_res=None, db_conn_kwargs=None):
	"""
	Evaluate the trained FactorJoin model on the IMDB-JOB workload.
	:param model_path: the trained model
	:param query_file: a dictionary of queries, e.g. '1a': SQL query string for query '1a'
	:param SPERCENTAGE: the sampling rate for doing base table cardinality estimation
	:param query_sample_location: if there exist a materialized sample that we can directly load from.
	"""
	with open(model_path, "rb") as f:
		bound_ensemble = pickle.load(f)
	if SPERCENTAGE:
		bound_ensemble.SPERCENTAGE = SPERCENTAGE
	if query_sample_location:
		bound_ensemble.query_sample_location = query_sample_location
	if db_conn_kwargs:
		bound_ensemble.db_conn_kwargs = db_conn_kwargs

	if not derived_query_file:
		all_queries, all_sub_plan_queries_str = get_job_sub_plan_queires(query_folder)
	else:
		with open(derived_query_file, "rb") as f:
			all_queries, all_sub_plan_queries_str = pickle.load(f)

	res = dict()
	t = time.time()

	for q_name in all_queries:
		# print(q_file_id, q_file_names[q_file_id])
		t_q = time.time()
		#temp = bound_ensemble.get_cardinality_bound_one(all_queries[q_name])
		temp = bound_ensemble.get_cardinality_bound_all(all_queries[str(q_name)], all_sub_plan_queries_str[q_name],
														q_name + ".pkl")
		runtime_q = time.time() - t_q
		res[q_name] = (q_name, temp)
		# append to the existing results in file 
		with open(save_res, "a") as f:
			for pred in temp:
				f.write(str(q_name) + "," + str(pred) + "," + str(runtime_q) + "\n")
		
	print(f"total estimation time is {time.time() - t}")
	if False:
		# save the sub-plan estimates according to the query execution order (1a, 1b, ..., 33c)
		f = open(save_res, "a")
		for query_no in range(1, 71):
			for suffix in ['a', 'b', 'c', 'd', 'e', 'f', 'g']:
				q_name = f"{query_no}{suffix}"
				if q_name in res:
					for pred in res[q_name]:
						f.write(str(pred) + "\n")
		f.close()

