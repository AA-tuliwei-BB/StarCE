import pickle
import time
import numpy as np
import pandas as pd
import os


def test_on_stats(model_path, query_file, save_res=None):
	with open(model_path, "rb") as f:
		bound_ensemble = pickle.load(f)

	for table in bound_ensemble.bns:
		bn = bound_ensemble.bns[table]
		bn.init_inference_method()

	with open(query_file, "r") as f:
		queries = f.readlines()

	#qerror = []
	latency = []
	pred = []
	for i, query_str in enumerate(queries):
		query = query_str.split("||")[0][:-1]
		#true_card = int(query_str.split("||")[-1])
		t = time.time()
		res = bound_ensemble.get_cardinality_bound_one(query)
		pred.append(res)
		latency.append(time.time() - t)
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

def test_on_imdb_light(model_path, query_file, true_cardinality_file, save_file=None, test_indices=None):
	with open(model_path, "rb") as f:
		bound_ensemble = pickle.load(f)

	for table in bound_ensemble.bns:
		bn = bound_ensemble.bns[table]
		bn.init_inference_method()

	with open(query_file, "r") as f:
		queries = f.readlines()

	# Read true cardinality from either CSV or txt format
	if true_cardinality_file.endswith('.csv'):
		true_card = pd.read_csv(true_cardinality_file)
		true_card = true_card["True cardinality"].values
	else:
		# Assume txt format with one cardinality per line
		with open(true_cardinality_file, "r") as f:
			true_card = [float(line.strip()) for line in f.readlines() if line.strip()]
		true_card = np.array(true_card)

	q_errors = []
	latency = []
	predictions = []
	zero_indices = []  # Track queries that return 0.0
	
	# If test_indices specified, only test those queries
	if test_indices is not None:
		print(f"\n[INFO] Testing only {len(test_indices)} specific queries: {test_indices}")
		query_range = test_indices
	else:
		query_range = range(len(queries))
	
	for i in query_range:
		query = queries[i]
		t = time.time()
		pred = bound_ensemble.get_cardinality_bound_one(query)
		latency.append(time.time() - t)
		predictions.append(pred)
		
		print(f"\n{'='*80}")
		print(f"Query {i+1} (index {i}):")
		print(f"  SQL: {query.strip()[:150]}...")
		print(f"  True cardinality: {true_card[i]}")
		print(f"  Predicted: {pred}")
		
		# Track zero predictions for debugging
		if pred == 0.0:
			zero_indices.append(i)
			print(f"  *** ZERO PREDICTION ***")
		
		if pred <= 1:
			pred = 1
		true = true_card[i]
		if true <= 1:
			true = 1
		error = max(true / pred, pred / true)
		q_errors.append(error)
		print(f"  Q-error: {error:.2f}")
	
	if test_indices is None:
		print(f"\n[INFO] Total queries: {len(queries)}, Zero predictions: {len(zero_indices)} ({100*len(zero_indices)/len(queries):.2f}%)")

	print(f"Average query inference latency is {np.mean(latency)}s")
	for i in [50, 90, 95, 99, 100]:
		print(f"q-error {i}% percentile is {np.percentile(q_errors, i)}")
	
	# Save predictions to file if save_file is specified
	if save_file:
		with open(save_file, "w") as f:
			for pred in predictions:
				f.write(str(pred) + "\n")


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
				 save_res=None):
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

	if not derived_query_file:
		all_queries, all_sub_plan_queries_str = get_job_sub_plan_queires(query_folder)
	else:
		with open(derived_query_file, "rb") as f:
			all_queries, all_sub_plan_queries_str = pickle.load(f)

	res = dict()
	t = time.time()
	for q_name in all_queries:
		# print(q_file_id, q_file_names[q_file_id])
		temp = bound_ensemble.get_cardinality_bound_all(all_queries[q_name], all_sub_plan_queries_str[q_name],
														q_name + ".pkl")
		res[q_name] = temp
	print("total estimation latency is: ", time.time() - t)

	if save_res:
		# save the sub-plan estimates according to the query execution order (1a, 1b, ..., 33c)
		f = open(save_res, "w")
		for query_no in range(1, 34):
			for suffix in ['a', 'b', 'c', 'd', 'e', 'f', 'g']:
				q_name = f"{query_no}{suffix}"
				if q_name in res:
					for pred in res[q_name]:
						f.write(str(pred) + "\n")
		f.close()


def test_on_jobm(model_path, query_file, jobm_mapping_file, SPERCENTAGE=None, query_sample_location=None, save_res=None):
	"""
	Evaluate on JOBM using the mapping from subqueries to main query materializations.
	"""
	with open(model_path, "rb") as f:
		bound_ensemble = pickle.load(f)
	if SPERCENTAGE:
		bound_ensemble.SPERCENTAGE = SPERCENTAGE
	if query_sample_location:
		bound_ensemble.query_sample_location = query_sample_location

	with open(jobm_mapping_file, "rb") as f:
		mapping = pickle.load(f)

	with open(query_file, "r") as f:
		subqueries = [line.strip() for line in f.readlines() if line.strip()]

	assert len(subqueries) == len(mapping), f"Subquery count mismatch: {len(subqueries)} != {len(mapping)}"

	preds = []
	t_start = time.time()
	for i, sql in enumerate(subqueries):
		main_id = mapping[i]
		if main_id is None:
			print(f"Warning: subquery {i} has no mapping, using 1.0")
			preds.append(1.0)
			continue
		
		# Use main_id.pkl for materialization lookup
		# get_cardinality_bound_one expects sql without trailing semicolon sometimes, 
		# but parse_query_simple handles it.
		res = bound_ensemble.get_cardinality_bound_one(sql, query_name=f"{main_id}.pkl")
		preds.append(res)
		if (i + 1) % 500 == 0:
			print(f"Estimated {i+1}/{len(subqueries)} queries...")

	print(f"Total JOBM estimation latency: {time.time() - t_start}s")

	if save_res:
		with open(save_res, "w") as f:
			for p in preds:
				f.write(str(p) + "\n")


def test_on_jobjoin(model_path, query_file, mapping_file, SPERCENTAGE=None, query_sample_location=None, save_res=None):
	"""
	Evaluate on JobJoin (完整 21 表、无谓词的纯 join workload)，主查询级评估。
	复用已修复的 get_cardinality_bound_one（恒等映射，逐条主查询）。
	无谓词场景下 load_sample 回退到 ground_truth_factors_no_filter，不连 PG。
	对 FactorJoin 架构无法处理的查询（如环形自连接 Q31）写 "MISSING"，不引入 fallback 假数据。
	"""
	with open(model_path, "rb") as f:
		bound_ensemble = pickle.load(f)
	if SPERCENTAGE:
		bound_ensemble.SPERCENTAGE = SPERCENTAGE
	if query_sample_location:
		bound_ensemble.query_sample_location = query_sample_location

	with open(mapping_file, "rb") as f:
		mapping = pickle.load(f)

	with open(query_file, "r") as f:
		queries = [line.strip() for line in f.readlines() if line.strip()]

	assert len(queries) == len(mapping), f"Query count mismatch: {len(queries)} != {len(mapping)}"

	preds = []
	failed = []
	t_start = time.time()
	for i, sql in enumerate(queries):
		main_id = mapping[i]
		try:
			res = bound_ensemble.get_cardinality_bound_one(sql, query_name=f"{main_id}.pkl")
			preds.append(res)
		except Exception as e:
			preds.append("MISSING")
			failed.append((i + 1, type(e).__name__, str(e)))

	print(f"Total JobJoin estimation latency: {time.time() - t_start}s")
	if failed:
		print(f"{len(failed)} query(ies) FactorJoin 无法估计，标记 MISSING:")
		for qid, etype, emsg in failed:
			print(f"  Q{qid}: {etype}: {emsg}")

	if save_res:
		with open(save_res, "w") as f:
			for p in preds:
				f.write(str(p) + "\n")

